import json
import time
import uuid

import requests
import websocket
from PyQt6.QtCore import QThread, pyqtSignal

import sub_badges
from emote_cache import precache_emotes
from logger import get_logger

log = get_logger("kick")

# Kick sohbet altyapisini sabit bir Pusher app key'inden cikardi: artik
# istemci once "realtime descriptor"u soruyor, yanitta hangi saglayicinin
# (Centrifugo ya da Pusher) ve hangi adresin/anahtarin kullanilacagi
# geliyor. Eski sabit anahtar (32cbd69e...) hicbir cluster'da gecerli
# degil ("App key ... not in this cluster"), o yuzden baglanti bilgisi
# her denemede API'den aliniyor.
REALTIME_API_URL = "https://web.kick.com/api/v1/realtime"
PUSHER_WS_URL = (
    "wss://ws-{cluster}.pusher.com/app/{app_key}"
    "?protocol=7&client=py&version=7.6.0&flash=false"
)
# Centrifugo baglanti token'i ~45 dk gecerli; suresi dolmadan bu kadar
# saniye once yenilenir (yenilenmezse sunucu baglantiyi kapatiyor).
TOKEN_REFRESH_MARGIN = 120

KICK_API_URL = "https://kick.com/api/v1/channels/{username}"

# Baglanti kurulamadiginda (yanlis kanal adi, internet yok, Cloudflare
# 403 vb.) yeniden deneme suresi. Sabit 5 sn'de sonsuza kadar denemek
# hem gereksiz agirlik hem de her denemede loglanan hata/bilgi satiriyla
# log dosyasini dakikalar icinde doldurup rotasyonu tetikliyordu - eski
# loglar hizla siliniyordu. Ustel geri cekilme hem agi rahatlatiyor hem
# de log satiri sikligini dogal olarak dusuruyor.
RECONNECT_BASE_DELAY = 5
RECONNECT_MAX_DELAY = 60
# Art arda basarisizlikta tam detayli log sadece ilk birkac denemede
# yazilir, sonrasinda periyodik bir ozet satirina duser (DEBUG'da hala
# her deneme goruluyor, "Ayrintili log" acikken).
LOUD_FAILURE_STREAK = 3
SUMMARY_EVERY = 8

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://kick.com/",
    "x-app-platform": "web",
}


class KickChatWorker(QThread):
    """Kick sohbetine baglanir, arka planda calisir, GUI'yi bloklamaz."""

    connected = pyqtSignal()
    disconnected = pyqtSignal()
    message_received = pyqtSignal(dict)
    message_deleted = pyqtSignal(str)
    user_banned = pyqtSignal(dict)
    user_unbanned = pyqtSignal(dict)
    subscription_event = pyqtSignal(dict)
    gifted_subs_event = pyqtSignal(dict)
    kicks_gifted_event = pyqtSignal(dict)
    status_changed = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, username: str, parent=None):
        super().__init__(parent)
        self.username = username.strip().lower()
        self._ws = None
        self._running = True
        self._chatroom_id = None
        self._channel_id = None
        self._user_id = None
        self._connected_ok = False
        self._consecutive_failures = 0
        # Kick'in anonim ziyaretciye verdigi "ephemeral" kimligin karsiligi
        self._client_id = str(uuid.uuid4())
        self._next_cmd_id = 1
        self._token_deadline = None

    def stop(self):
        log.info("worker durduruluyor (kanal=%s)", self.username)
        self._running = False
        if self._ws is not None:
            try:
                self._ws.close()
            except Exception as exc:
                log.debug("websocket kapatilirken hata (onemsiz): %s", exc)

    def _sleep_interruptible(self, seconds: float):
        """stop() cagrildiginda hemen donen bekleme.

        Duz time.sleep(5) kullanildiginda stop()'tan sonra thread 5 sn daha
        yasiyordu; surec bu arada kapanirsa Qt/Python teardown sirasinda
        access violation olusuyordu (crash.log'da goruldu).
        """
        for _ in range(int(seconds * 10)):
            if not self._running:
                return
            self.msleep(100)

    def _fetch_channel_info(self):
        """chatroom_id / channel_id / user_id'yi cikarir, ayni yanittan
        abone rozetlerini alir.

        Sohbet mesajlari ve ban/silme olaylari chatroom_id kanalinda gelir,
        ama abonelik/hediye/kicks gibi yayinci-seviyesi olaylar Kick'te
        tutarsiz bir sekilde farkli kanallarda (channel_id ya da user_id
        anahtarli) yayinlaniyor - bu yuzden ucu de saklanip _run_websocket
        hepsine birden abone oluyor.
        """
        url = KICK_API_URL.format(username=self.username)
        try:
            resp = requests.get(url, headers=HEADERS, timeout=(5, 10))
            resp.raise_for_status()
        except requests.exceptions.RequestException as exc:
            raise ValueError(
                f"Kanal bilgisi alinamadi: {exc}. Kullanici adini kontrol edin "
                "(Kick Cloudflare korumasi engelliyorsa 'cloudscraper' paketi ile denenebilir)."
            ) from exc

        data = resp.json()
        chatroom = data.get("chatroom") or {}
        chatroom_id = chatroom.get("id")
        if not chatroom_id:
            raise ValueError("chatroom_id bulunamadi, kullanici adini kontrol edin.")
        self._chatroom_id = chatroom_id
        self._channel_id = data.get("id") or chatroom.get("channel_id")
        self._user_id = data.get("user_id")
        log.info("chatroom_id=%s channel_id=%s user_id=%s (kanal=%s)",
                 self._chatroom_id, self._channel_id, self._user_id, self.username)

        # Abone rozetleri kanala ozel; bu adim basarisiz olsa bile sohbet
        # calismaya devam etmeli, o yuzden hata yutuluyor (gomulu yedek
        # ikon kullanilir).
        try:
            sub_badges.set_tiers(data.get("subscriber_badges"))
        except Exception as exc:
            log.warning("abone rozetleri okunamadi: %s", exc)

    def run(self):
        # QThread.run icinde firlayan hata Python'un threading.excepthook'una
        # dusmez; burada elle yakalanip loglanmali.
        log.info("worker thread basladi (kanal=%s)", self.username)
        attempt = 0
        try:
            while self._running:
                attempt += 1
                self._connected_ok = False
                try:
                    self.status_changed.emit(f"'{self.username}' kanal bilgisi aliniyor...")
                    self._fetch_channel_info()
                    # HTTP istegi surerken stop() cagrilmis olabilir; bu
                    # kontrol olmadan websocket stop'tan SONRA aciliyordu.
                    if not self._running:
                        break
                    # rozet gorselleri ilk mesaj gelmeden diske insin
                    sub_badges.precache(should_continue=lambda: self._running)
                    if not self._running:
                        break
                    self.status_changed.emit("Sohbete baglaniliyor...")
                    self._run_websocket()
                except Exception as exc:
                    self._log_connection_failure(attempt, exc)
                    self.error_occurred.emit(str(exc))

                if not self._running:
                    break

                if self._connected_ok:
                    # bir sure calisip sonra kopan baglanti, hic kurulamayan
                    # baglantidan farkli - deneme sikligini sifirla
                    self._consecutive_failures = 0
                    delay = RECONNECT_BASE_DELAY
                else:
                    self._consecutive_failures += 1
                    delay = min(RECONNECT_MAX_DELAY,
                                RECONNECT_BASE_DELAY * (2 ** (self._consecutive_failures - 1)))
                    self._log_retry_backoff(attempt, delay)

                self.status_changed.emit(f"Baglanti koptu, {delay} sn sonra tekrar denenecek...")
                self._sleep_interruptible(delay)
        except Exception as exc:
            log.critical("worker thread coktu: %s", exc, exc_info=True)
            self.error_occurred.emit(f"Baglanti thread'i coktu: {exc}")
        finally:
            log.info("worker thread bitti (kanal=%s)", self.username)

    def _log_connection_failure(self, attempt: int, exc: Exception):
        """Baglanti hatasini loglar; art arda ayni hata log dosyasini
        sismesin diye ilk birkac denemeden sonra sikligi dusurulur."""
        streak = self._consecutive_failures + 1  # bu hata henuz sayilmadi
        if streak <= LOUD_FAILURE_STREAK:
            log.error("baglanti hatasi (deneme %s): %s", attempt, exc, exc_info=True)
        elif streak % SUMMARY_EVERY == 0:
            log.warning("baglanti hala kurulamiyor (deneme %s, art arda %s basarisiz): %s",
                       attempt, streak, exc)
        else:
            log.debug("baglanti hatasi (deneme %s, art arda %s basarisiz): %s",
                     attempt, streak, exc, exc_info=True)

    def _log_retry_backoff(self, attempt: int, delay: int):
        streak = self._consecutive_failures
        if streak <= LOUD_FAILURE_STREAK or streak % SUMMARY_EVERY == 0:
            log.info("baglanti koptu, %s sn sonra yeniden denenecek (deneme %s)", delay, attempt)
        else:
            log.debug("baglanti koptu, %s sn sonra yeniden denenecek (deneme %s)", delay, attempt)

    def _fetch_realtime_app(self) -> dict:
        """Sohbet icin hangi saglayiciya/adrese baglanilacagini Kick'ten alir."""
        body = {
            "client": {"id": self._client_id, "type": "web"},
            "capabilities": {
                "accepted_providers": [{"provider": "centrifugo"}, {"provider": "pusher"}],
            },
        }
        url = f"{REALTIME_API_URL}/channels/{self._channel_id}/chat/connection"
        try:
            resp = requests.post(url, json=body, headers=HEADERS, timeout=(5, 10))
            resp.raise_for_status()
            data = resp.json().get("data") or {}
        except (requests.exceptions.RequestException, ValueError) as exc:
            raise ValueError(f"Sohbet baglanti bilgisi alinamadi: {exc}") from exc

        connections = data.get("connections") or []
        if data.get("mode") == "websocket":
            for conn in connections:
                provider = conn.get("provider")
                creds = conn.get("credentials") or {}
                if provider == "centrifugo" and creds.get("url"):
                    return {"provider": "centrifugo", "url": creds["url"]}
                if provider == "pusher" and creds.get("app_key") and creds.get("cluster"):
                    return {
                        "provider": "pusher",
                        "url": PUSHER_WS_URL.format(cluster=creds["cluster"],
                                                    app_key=creds["app_key"]),
                    }
        raise ValueError(
            "Kick desteklenmeyen bir sohbet baglantisi dondurdu "
            f"(mode={data.get('mode')!r}, saglayicilar="
            f"{[c.get('provider') for c in connections]})"
        )

    def _fetch_centrifugo_token(self) -> str:
        try:
            resp = requests.post(f"{REALTIME_API_URL}/auth/connection",
                                 json={"client_id": self._client_id},
                                 headers=HEADERS, timeout=(5, 10))
            resp.raise_for_status()
            token = (resp.json().get("data") or {}).get("token")
        except (requests.exceptions.RequestException, ValueError) as exc:
            raise ValueError(f"Sohbet baglanti token'i alinamadi: {exc}") from exc
        if not token:
            raise ValueError("Sohbet baglanti token'i bos dondu.")
        return token

    def _channel_names(self) -> list:
        """Sohbet olaylari (mesaj/silme/ban) chatroom kanalinda gelir, ama
        abonelik/hediye/kicks gibi yayinci-seviyesi olaylar Kick'te tutarsiz
        sekilde chatroom'un eski takma adlarinda ya da yayincinin channel_id/
        user_id anahtarli kanallarinda yayinlanabiliyor. Hangisinin gercekte
        kullanildigi olay tipine ve zamana gore degisebildigi icin hepsine
        birden abone olunuyor; var olmayan bir kanala abone olmak zararsiz.
        """
        candidates = [
            f"chatrooms.{self._chatroom_id}.v2",
            f"chatrooms.{self._chatroom_id}",
            f"chatroom_{self._chatroom_id}",
            f"channel.{self._channel_id}",
            f"channel_{self._channel_id}",
            f"channel.{self._user_id}",
        ]
        names = []
        for name in candidates:
            if "None" in name or name in names:
                continue
            names.append(name)
        return names

    def _mark_connected(self):
        self._connected_ok = True
        self.connected.emit()
        self.status_changed.emit("Baglandi, sohbet dinleniyor.")

    def _cmd_id(self) -> int:
        self._next_cmd_id += 1
        return self._next_cmd_id

    # ---- Pusher protokolu -------------------------------------------------

    def _on_pusher_frame(self, ws, message):
        try:
            payload = json.loads(message)
        except json.JSONDecodeError:
            log.debug("cozulemeyen websocket mesaji atlandi (%s bayt)", len(message or ""))
            return

        event = payload.get("event") or ""
        if event == "pusher:connection_established":
            names = self._channel_names()
            for name in names:
                ws.send(json.dumps({"event": "pusher:subscribe", "data": {"channel": name}}))
            log.debug("pusher kanallarina abone olundu: %s", names)
            self._mark_connected()
        elif event == "pusher:ping":
            ws.send(json.dumps({"event": "pusher:pong", "data": {}}))
        elif event == "pusher:error":
            log.error("pusher hatasi: %s", payload.get("data"))
        else:
            self._handle_event(event, payload.get("data"))

    # ---- Centrifugo protokolu ---------------------------------------------

    def _centrifugo_connect(self, ws):
        token = self._fetch_centrifugo_token()
        self._next_cmd_id = 1
        ws.send(json.dumps({"id": 1, "connect": {"token": token, "name": "js"}}))

    def _set_token_deadline(self, info: dict):
        if info.get("expires") and info.get("ttl"):
            self._token_deadline = time.monotonic() + info["ttl"]
        else:
            self._token_deadline = None

    def _refresh_token_if_needed(self, ws):
        if (self._token_deadline is None
                or time.monotonic() < self._token_deadline - TOKEN_REFRESH_MARGIN):
            return
        # basarisiz olursa her ping'de tekrar denenmesin diye once
        # sifirlaniyor; sunucu sure dolunca kapatir, dis dongu yeniden baglar
        self._token_deadline = None
        try:
            token = self._fetch_centrifugo_token()
        except ValueError as exc:
            log.warning("token yenilenemedi, baglanti suresi dolunca yeniden kurulacak: %s", exc)
            return
        ws.send(json.dumps({"id": self._cmd_id(), "refresh": {"token": token}}))
        log.debug("centrifugo token yenileme istegi gonderildi")

    def _on_centrifugo_frame(self, ws, message):
        # tek websocket cercevesinde satir satir birden fazla JSON gelebilir
        for line in (message or "").split("\n"):
            line = line.strip()
            if not line:
                continue
            if line == "{}":
                # sunucu ping'i (25 sn'de bir); yanitlanmazsa baglanti kesilir
                ws.send("{}")
                self._refresh_token_if_needed(ws)
                continue
            try:
                reply = json.loads(line)
            except json.JSONDecodeError:
                log.debug("cozulemeyen websocket mesaji atlandi (%s bayt)", len(line))
                continue

            if "push" in reply:
                push = reply["push"] or {}
                if "pub" in push:
                    envelope = (push["pub"] or {}).get("data") or {}
                    if isinstance(envelope, dict):
                        self._handle_event(envelope.get("event") or "", envelope.get("data"))
                elif "disconnect" in push:
                    log.warning("sunucu baglantiyi kesiyor: %s", push["disconnect"])
                elif "unsubscribe" in push:
                    log.warning("sunucu kanal aboneligini sonlandirdi (%s): %s",
                                push.get("channel"), push["unsubscribe"])
            elif "error" in reply:
                if reply.get("id") == 1:
                    log.error("centrifugo baglanti istegi reddedildi: %s", reply["error"])
                    ws.close()
                    return
                log.warning("centrifugo istegi basarisiz (id=%s): %s",
                            reply.get("id"), reply["error"])
            elif "connect" in reply:
                self._set_token_deadline(reply["connect"] or {})
                names = self._channel_names()
                ws.send("\n".join(
                    json.dumps({"id": self._cmd_id(), "subscribe": {"channel": name}})
                    for name in names
                ))
                log.debug("centrifugo kanallarina abone olundu: %s", names)
                self._mark_connected()
            elif "refresh" in reply:
                self._set_token_deadline(reply["refresh"] or {})
                log.debug("centrifugo token yenilendi")

    # ---- Olaylar (iki saglayicida da ayni) --------------------------------

    def _handle_event(self, raw_event: str, data):
        # Kick bazi olaylari "App\Events\X" onekiyle, bazilarini ciplak
        # "X" olarak yolluyor (gozlemlendi: SubscriptionEvent/UserBannedEvent
        # onekli, GiftedSubscriptionsEvent/KicksGifted/RewardRedeemedEvent
        # ciplak). Oneki atip tek koldan eslestirmek ikisini de kapsar.
        prefix = "App\\Events\\"
        event = raw_event[len(prefix):] if raw_event.startswith(prefix) else raw_event

        # olay icerigi JSON metni olarak sarili geliyor
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                log.debug("%s icerigi cozulemedi", event)
                return
        if not isinstance(data, dict):
            return

        if event == "ChatMessageEvent":
            try:
                precache_emotes(data.get("content", ""))
            except Exception as exc:
                log.warning("emote onbellege alinamadi: %s", exc)
            self.message_received.emit(data)

        elif event == "MessageDeletedEvent":
            message_id = (data.get("message") or {}).get("id")
            if message_id:
                log.debug("mesaj silindi (id=%s)", message_id)
                self.message_deleted.emit(message_id)

        elif event == "UserBannedEvent":
            username = (data.get("user") or {}).get("username")
            if username:
                info = {
                    "username": username,
                    "permanent": bool(data.get("permanent")),
                    "duration": data.get("duration"),
                    "expires_at": data.get("expires_at"),
                    "banned_by": (data.get("banned_by") or {}).get("username"),
                }
                log.debug("kullanici banlandi/susturuldu: %s (kalici=%s)",
                          username, info["permanent"])
                self.user_banned.emit(info)

        elif event == "UserUnbannedEvent":
            username = (data.get("user") or {}).get("username")
            if username:
                info = {
                    "username": username,
                    "unbanned_by": (data.get("unbanned_by") or {}).get("username"),
                }
                log.debug("kullanicinin bani kaldirildi: %s", username)
                self.user_unbanned.emit(info)

        elif event == "SubscriptionEvent":
            username = data.get("username")
            if username:
                info = {"username": username, "months": data.get("months") or 1}
                log.debug("abonelik: %s (%s ay)", username, info["months"])
                self.subscription_event.emit(info)

        elif event == "GiftedSubscriptionsEvent":
            gifted = data.get("gifted_usernames") or []
            info = {
                "gifter_username": data.get("gifter_username") or "Anonim",
                "gifted_usernames": gifted,
                "gifter_total": data.get("gifter_total") or len(gifted),
            }
            log.debug("hediye abonelik: %s -> %s kisi",
                      info["gifter_username"], len(gifted))
            self.gifted_subs_event.emit(info)

        elif event == "KicksGifted":
            sender = data.get("sender") or {}
            gift = data.get("gift") or {}
            info = {
                "sender_username": sender.get("username") or "???",
                "gift_name": gift.get("name") or "Kicks",
                "amount": gift.get("amount") or 0,
            }
            log.debug("kicks hediye: %s x%s (%s)",
                      info["sender_username"], info["amount"], info["gift_name"])
            self.kicks_gifted_event.emit(info)

    def _run_websocket(self):
        app = self._fetch_realtime_app()
        centrifugo = app["provider"] == "centrifugo"
        self._token_deadline = None
        log.info("sohbet saglayicisi=%s url=%s", app["provider"], app["url"].split("?")[0])

        def on_open(ws):
            log.info("websocket acildi")
            if centrifugo:
                try:
                    self._centrifugo_connect(ws)
                except Exception as exc:
                    log.error("centrifugo baglanti istegi gonderilemedi: %s", exc)
                    self.error_occurred.emit(str(exc))
                    ws.close()

        def on_message(ws, message):
            if centrifugo:
                self._on_centrifugo_frame(ws, message)
            else:
                self._on_pusher_frame(ws, message)

        def on_error(ws, error):
            log.error("websocket hatasi: %s: %s", type(error).__name__, error)
            self.error_occurred.emit(str(error))

        def on_close(ws, code, reason):
            log.info("websocket kapandi (code=%s reason=%r)", code, reason)
            self.disconnected.emit()

        self._ws = websocket.WebSocketApp(
            app["url"],
            header=["Origin: https://kick.com"],
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
        )
        self._ws.run_forever(ping_interval=60, ping_timeout=10)
        log.debug("run_forever dondu (running=%s)", self._running)
