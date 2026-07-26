import json

import requests
import websocket
from PyQt6.QtCore import QThread, pyqtSignal

import sub_badges
from emote_cache import precache_emotes
from logger import get_logger

log = get_logger("kick")

# Kick'in tarayicidan kullandigi genel Pusher app key / cluster.
PUSHER_APP_KEY = "32cbd69e4b950bf97679"
PUSHER_CLUSTER = "us2"
PUSHER_WS_URL = (
    f"wss://ws-{PUSHER_CLUSTER}.pusher.com/app/{PUSHER_APP_KEY}"
    "?protocol=7&client=py&version=7.6.0&flash=false"
)

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

    def _subscribe_all(self, ws):
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
        seen = set()
        for name in candidates:
            if "None" in name or name in seen:
                continue
            seen.add(name)
            ws.send(json.dumps({"event": "pusher:subscribe", "data": {"channel": name}}))
        log.debug("pusher kanallarina abone olundu: %s", sorted(seen))

    def _run_websocket(self):
        def on_open(ws):
            log.info("websocket acildi")

        def on_message(ws, message):
            try:
                payload = json.loads(message)
            except json.JSONDecodeError:
                log.debug("cozulemeyen websocket mesaji atlandi (%s bayt)", len(message or ""))
                return

            raw_event = payload.get("event") or ""
            # Kick bazi olaylari "App\Events\X" onekiyle, bazilarini ciplak
            # "X" olarak yolluyor (gozlemlendi: SubscriptionEvent/UserBannedEvent
            # onekli, GiftedSubscriptionsEvent/KicksGifted/RewardRedeemedEvent
            # ciplak). Oneki atip tek koldan eslestirmek ikisini de kapsar.
            prefix = "App\\Events\\"
            event = raw_event[len(prefix):] if raw_event.startswith(prefix) else raw_event

            if event == "pusher:connection_established":
                self._subscribe_all(ws)
                self._connected_ok = True
                self.connected.emit()
                self.status_changed.emit("Baglandi, sohbet dinleniyor.")

            elif event == "pusher:ping":
                ws.send(json.dumps({"event": "pusher:pong", "data": {}}))

            elif event == "ChatMessageEvent":
                try:
                    data = json.loads(payload.get("data", "{}"))
                except json.JSONDecodeError:
                    log.debug("ChatMessageEvent icerigi cozulemedi")
                    return
                try:
                    precache_emotes(data.get("content", ""))
                except Exception as exc:
                    log.warning("emote onbellege alinamadi: %s", exc)
                self.message_received.emit(data)

            elif event == "MessageDeletedEvent":
                try:
                    data = json.loads(payload.get("data", "{}"))
                except json.JSONDecodeError:
                    log.debug("MessageDeletedEvent icerigi cozulemedi")
                    return
                message_id = (data.get("message") or {}).get("id")
                if message_id:
                    log.debug("mesaj silindi (id=%s)", message_id)
                    self.message_deleted.emit(message_id)

            elif event == "UserBannedEvent":
                try:
                    data = json.loads(payload.get("data", "{}"))
                except json.JSONDecodeError:
                    log.debug("UserBannedEvent icerigi cozulemedi")
                    return
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
                try:
                    data = json.loads(payload.get("data", "{}"))
                except json.JSONDecodeError:
                    log.debug("UserUnbannedEvent icerigi cozulemedi")
                    return
                username = (data.get("user") or {}).get("username")
                if username:
                    info = {
                        "username": username,
                        "unbanned_by": (data.get("unbanned_by") or {}).get("username"),
                    }
                    log.debug("kullanicinin bani kaldirildi: %s", username)
                    self.user_unbanned.emit(info)

            elif event == "SubscriptionEvent":
                try:
                    data = json.loads(payload.get("data", "{}"))
                except json.JSONDecodeError:
                    log.debug("SubscriptionEvent icerigi cozulemedi")
                    return
                username = data.get("username")
                if username:
                    info = {"username": username, "months": data.get("months") or 1}
                    log.debug("abonelik: %s (%s ay)", username, info["months"])
                    self.subscription_event.emit(info)

            elif event == "GiftedSubscriptionsEvent":
                try:
                    data = json.loads(payload.get("data", "{}"))
                except json.JSONDecodeError:
                    log.debug("GiftedSubscriptionsEvent icerigi cozulemedi")
                    return
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
                try:
                    data = json.loads(payload.get("data", "{}"))
                except json.JSONDecodeError:
                    log.debug("KicksGifted icerigi cozulemedi")
                    return
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

        def on_error(ws, error):
            log.error("websocket hatasi: %s: %s", type(error).__name__, error)
            self.error_occurred.emit(str(error))

        def on_close(ws, code, reason):
            log.info("websocket kapandi (code=%s reason=%r)", code, reason)
            self.disconnected.emit()

        self._ws = websocket.WebSocketApp(
            PUSHER_WS_URL,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
        )
        self._ws.run_forever(ping_interval=60, ping_timeout=10)
        log.debug("run_forever dondu (running=%s)", self._running)
