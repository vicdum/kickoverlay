import ctypes

from PyQt6.QtCore import QEvent, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication, QLabel, QScrollArea, QVBoxLayout, QWidget

import mentions
import notify_sound
from badge_icons import badge_types
from chat_message_widget import ChatMessageWidget
from logger import get_logger
from turkish import tr_fold

log = get_logger("overlay")

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
MAX_MESSAGES = 60
RESIZE_MARGIN = 18
MIN_WIDTH = 220
MIN_HEIGHT = 160


class OverlayWindow(QWidget):
    position_saved = pyqtSignal(int, int)
    size_saved = pyqtSignal(int, int)

    def __init__(self, settings: dict):
        super().__init__()
        self.settings = settings
        self._click_through = False
        self._drag_pos = None
        self._resizing = False
        self._resize_start_pos = None
        self._resize_start_size = None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setStyleSheet("background: transparent;")

        self.resize(settings["overlay_width"], settings["overlay_height"])
        self.move(settings["overlay_x"], settings["overlay_y"])

        self.container = QWidget(self)
        self.container.setStyleSheet("background: transparent;")
        self.messages_layout = QVBoxLayout(self.container)
        self.messages_layout.setAlignment(Qt.AlignmentFlag.AlignBottom)
        self.messages_layout.setSpacing(6)
        self.messages_layout.setContentsMargins(4, 4, 4, 4)

        self.scroll = QScrollArea(self)
        self.scroll.setWidget(self.container)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll.setStyleSheet("background: transparent; border: none;")
        self.scroll.viewport().setStyleSheet("background: transparent;")
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.scroll)

        self.resize_grip = QLabel("◢", self)
        self.resize_grip.setFixedSize(RESIZE_MARGIN, RESIZE_MARGIN)
        self.resize_grip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.resize_grip.setStyleSheet(
            "background: rgba(83,252,24,180); color:#0b0c0e;"
            "border-top-left-radius:6px; font-weight:bold;"
        )
        self.resize_grip.hide()
        self._position_resize_grip()

        self.apply_window_opacity()

        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    def _position_resize_grip(self):
        self.resize_grip.move(self.width() - RESIZE_MARGIN, self.height() - RESIZE_MARGIN)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_resize_grip()

    # ---- click-through (fare tiklamasini gecirme) ----------------------
    def set_click_through(self, enabled: bool):
        self._click_through = enabled
        try:
            hwnd = int(self.winId())
            user32 = ctypes.windll.user32
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            if enabled:
                style |= WS_EX_LAYERED | WS_EX_TRANSPARENT
            else:
                style |= WS_EX_LAYERED
                style &= ~WS_EX_TRANSPARENT
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
            log.debug("click_through=%s hwnd=%s style=0x%08x", enabled, hwnd, style)
        except Exception as exc:
            log.error("click-through ayarlanamadi (enabled=%s): %s", enabled, exc, exc_info=True)

        if enabled:
            self.container.setStyleSheet("background: transparent;")
            self.resize_grip.hide()
        else:
            # tasima modunda pencere sinirlarini gorunur yap
            self.container.setStyleSheet(
                "background: rgba(83,252,24,25);"
                "border: 2px dashed rgba(83,252,24,180);"
                "border-radius: 6px;"
            )
            self.resize_grip.show()
            self.resize_grip.raise_()

    def is_click_through(self) -> bool:
        return self._click_through

    def _hit_resize_corner(self, global_pos) -> bool:
        local_x = global_pos.x() - self.x()
        local_y = global_pos.y() - self.y()
        return (self.width() - RESIZE_MARGIN <= local_x <= self.width()
                and self.height() - RESIZE_MARGIN <= local_y <= self.height())

    # ---- surukleyerek tasima / boyutlandirma ----------------------------
    # Tasima modunda tum mouse eventleri QApplication seviyesinde
    # yakalanir. Eskiden bu mantik OverlayWindow.mousePressEvent
    # icindeydi ama pencereyi tamamen kaplayan QScrollArea/mesaj
    # etiketleri eventi once kendileri yuttugu icin hic tetiklenmiyordu.
    def eventFilter(self, obj, event):
        if self._click_through:
            return super().eventFilter(obj, event)

        et = event.type()
        if et in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseMove, QEvent.Type.MouseButtonRelease):
            if not (isinstance(obj, QWidget) and obj.window() is self):
                return super().eventFilter(obj, event)

            if et == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                gp = event.globalPosition().toPoint()
                if self._hit_resize_corner(gp):
                    self._resizing = True
                    self._resize_start_pos = gp
                    self._resize_start_size = self.size()
                else:
                    self._drag_pos = gp - self.pos()
                return True

            if et == QEvent.Type.MouseMove:
                gp = event.globalPosition().toPoint()
                if self._resizing:
                    delta = gp - self._resize_start_pos
                    new_w = max(MIN_WIDTH, self._resize_start_size.width() + delta.x())
                    new_h = max(MIN_HEIGHT, self._resize_start_size.height() + delta.y())
                    self.resize(new_w, new_h)
                    return True
                if self._drag_pos is not None:
                    self.move(gp - self._drag_pos)
                    return True

            if et == QEvent.Type.MouseButtonRelease:
                if self._resizing:
                    self._resizing = False
                    self.size_saved.emit(self.width(), self.height())
                    return True
                if self._drag_pos is not None:
                    self._drag_pos = None
                    self.position_saved.emit(self.x(), self.y())
                    return True

        return super().eventFilter(obj, event)

    # ---- ayar uygulama ---------------------------------------------------
    def apply_window_opacity(self):
        self.setWindowOpacity(self.settings["overlay_opacity"] / 100)

    def update_settings(self, settings: dict):
        self.settings = settings
        self.apply_window_opacity()

    # ---- vurgulama (highlight) -----------------------------------------
    def _is_highlighted(self, username: str, badges: list) -> bool:
        s = self.settings
        if not s.get("highlight_enabled"):
            return False
        uname = tr_fold(username or "")
        if uname in {tr_fold(u) for u in (s.get("highlight_users") or [])}:
            return True
        roles = set(s.get("highlight_roles") or [])
        # rozetler Kick'ten sozluk olarak gelir, sadece "type" alani onemli
        if roles and any(b in roles for b in badge_types(badges)):
            return True
        return False

    # ---- etiketlenme (mention) ------------------------------------------
    def _is_mentioned(self, content: str) -> bool:
        return mentions.contains(content, mentions.pattern_for(self.settings))

    def _play_mention_sound(self):
        s = self.settings
        if not s.get("mention_sound_enabled"):
            return
        notify_sound.play(s.get("mention_sound_path"),
                          s.get("mention_sound_cooldown", 3))

    # ---- filtreleme -----------------------------------------------------
    def _is_filtered(self, username: str, content: str, msg_type: str) -> bool:
        s = self.settings
        uname = tr_fold(username or "")

        if uname in {tr_fold(u) for u in (s.get("blocked_users") or [])}:
            return True

        if s.get("hide_bot_messages") and uname in {tr_fold(u) for u in (s.get("bot_users") or [])}:
            return True

        if s.get("hide_bot_commands"):
            prefix = s.get("bot_command_prefix") or "!"
            if content and content.strip().startswith(prefix):
                return True

        if s.get("hide_notifications") and msg_type not in ("message", "reply"):
            return True

        keywords = s.get("blocked_keywords") or []
        if keywords:
            low = tr_fold(content or "")
            if any(tr_fold(kw) in low for kw in keywords):
                return True

        return False

    # ---- sohbet mesajlari --------------------------------------------
    def add_message(self, username: str, content: str, color: str, badges: list,
                     msg_type: str = "message"):
        if self._is_filtered(username, content, msg_type):
            return

        highlighted = self._is_highlighted(username, badges)
        try:
            widget = ChatMessageWidget(username, content, color, badges, self.settings, highlighted)
        except Exception as exc:
            log.error("mesaj olusturulamadi (user=%r): %s", username, exc, exc_info=True)
            return

        # Ses filtreden SONRA calar: gizlenen mesaj icin bildirim olmaz.
        if self._is_mentioned(content):
            self._play_mention_sound()

        self.messages_layout.addWidget(widget)

        # Zamanlayici widget'a parent edilir: MAX_MESSAGES tasmasi yuzunden
        # widget once silinirse timer da onunla birlikte yok olur ve
        # silinmis C++ nesnesi uzerinde tetiklenmez. Eskiden burada
        # QTimer.singleShot(...) kullaniliyordu; yogun sohbette widget
        # deleteLater() ile silindikten sonra timer atesleniyor ve
        # "wrapped C/C++ object ... has been deleted" RuntimeError'i
        # olusuyordu. Bir slot icindeki yakalanmayan bu hata PyQt'de
        # qFatal() cagirtip uygulamayi sessizce kapatiyordu.
        timer = QTimer(widget)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda w=widget: self._remove_message(w))
        timer.start(max(1, int(self.settings.get("message_duration", 12)) * 1000))

        trimmed = 0
        while self.messages_layout.count() > MAX_MESSAGES:
            item = self.messages_layout.takeAt(0)
            if item is None:
                break
            if item.widget():
                item.widget().deleteLater()
                trimmed += 1
        if trimmed:
            log.debug("%s eski mesaj kirpildi (limit=%s)", trimmed, MAX_MESSAGES)

        QTimer.singleShot(0, self._scroll_to_bottom)

    def _remove_message(self, widget):
        if widget is None:
            return
        try:
            self.messages_layout.removeWidget(widget)
            widget.deleteLater()
        except RuntimeError:
            # widget zaten silinmis - zararsiz
            pass

    def _scroll_to_bottom(self):
        try:
            bar = self.scroll.verticalScrollBar()
            bar.setValue(bar.maximum())
        except RuntimeError:
            pass
