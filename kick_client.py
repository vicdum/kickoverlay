import json
import time

import requests
import websocket
from PyQt6.QtCore import QThread, pyqtSignal

from emote_cache import precache_emotes

# Kick'in tarayicidan kullandigi genel Pusher app key / cluster.
PUSHER_APP_KEY = "32cbd69e4b950bf97679"
PUSHER_CLUSTER = "us2"
PUSHER_WS_URL = (
    f"wss://ws-{PUSHER_CLUSTER}.pusher.com/app/{PUSHER_APP_KEY}"
    "?protocol=7&client=py&version=7.6.0&flash=false"
)

KICK_API_URL = "https://kick.com/api/v1/channels/{username}"

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
    status_changed = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, username: str, parent=None):
        super().__init__(parent)
        self.username = username.strip().lower()
        self._ws = None
        self._running = True
        self._chatroom_id = None

    def stop(self):
        self._running = False
        if self._ws is not None:
            try:
                self._ws.close()
            except Exception:
                pass

    def _fetch_chatroom_id(self) -> int:
        url = KICK_API_URL.format(username=self.username)
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            resp.raise_for_status()
        except requests.exceptions.RequestException as exc:
            raise ValueError(
                f"Kanal bilgisi alinamadi: {exc}. Kullanici adini kontrol edin "
                "(Kick Cloudflare korumasi engelliyorsa 'cloudscraper' paketi ile denenebilir)."
            ) from exc

        data = resp.json()
        chatroom_id = (data.get("chatroom") or {}).get("id")
        if not chatroom_id:
            raise ValueError("chatroom_id bulunamadi, kullanici adini kontrol edin.")
        return chatroom_id

    def run(self):
        while self._running:
            try:
                self.status_changed.emit(f"'{self.username}' kanal bilgisi aliniyor...")
                self._chatroom_id = self._fetch_chatroom_id()
                self.status_changed.emit("Sohbete baglaniliyor...")
                self._run_websocket()
            except Exception as exc:
                self.error_occurred.emit(str(exc))

            if self._running:
                self.status_changed.emit("Baglanti koptu, 5 sn sonra tekrar denenecek...")
                time.sleep(5)

    def _run_websocket(self):
        def on_open(ws):
            pass

        def on_message(ws, message):
            try:
                payload = json.loads(message)
            except json.JSONDecodeError:
                return

            event = payload.get("event")

            if event == "pusher:connection_established":
                channel = f"chatrooms.{self._chatroom_id}.v2"
                ws.send(json.dumps({
                    "event": "pusher:subscribe",
                    "data": {"channel": channel},
                }))
                self.connected.emit()
                self.status_changed.emit("Baglandi, sohbet dinleniyor.")

            elif event == "pusher:ping":
                ws.send(json.dumps({"event": "pusher:pong", "data": {}}))

            elif event == "App\\Events\\ChatMessageEvent":
                try:
                    data = json.loads(payload.get("data", "{}"))
                except json.JSONDecodeError:
                    return
                precache_emotes(data.get("content", ""))
                self.message_received.emit(data)

        def on_error(ws, error):
            self.error_occurred.emit(str(error))

        def on_close(ws, code, reason):
            self.disconnected.emit()

        self._ws = websocket.WebSocketApp(
            PUSHER_WS_URL,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
        )
        self._ws.run_forever(ping_interval=60, ping_timeout=10)
