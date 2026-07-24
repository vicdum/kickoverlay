import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QColor, QIcon, QPixmap
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from config import load_config, save_config
from kick_client import KickChatWorker
from overlay_window import OverlayWindow
from settings_window import SettingsWindow


def make_tray_icon() -> QIcon:
    pixmap = QPixmap(32, 32)
    pixmap.fill(QColor(83, 249, 129))
    return QIcon(pixmap)


class App:
    def __init__(self):
        self.qapp = QApplication(sys.argv)
        self.qapp.setQuitOnLastWindowClosed(False)

        self.config = load_config()
        self.settings_window = SettingsWindow(self.config)
        self.overlay = None
        self.worker = None

        self._build_tray()

        self.settings_window.start_requested.connect(self.start_overlay)
        self.settings_window.stop_requested.connect(self.stop_overlay)
        self.settings_window.settings_changed.connect(self.apply_settings)
        self.settings_window.move_mode_toggled.connect(self.set_move_mode)
        self.settings_window.quit_requested.connect(self.quit)

        self.settings_window.show()

    def _build_tray(self):
        self.tray = QSystemTrayIcon(make_tray_icon())
        self.tray.setToolTip("Kick Chat Overlay")

        menu = QMenu()
        self.action_toggle_settings = QAction("Ayarlari Goster/Gizle")
        self.action_toggle_settings.triggered.connect(self.toggle_settings)
        self.action_toggle_move = QAction("Tasima Modu")
        self.action_toggle_move.setCheckable(True)
        self.action_toggle_move.toggled.connect(self.set_move_mode)
        self.action_quit = QAction("Cikis")
        self.action_quit.triggered.connect(self.quit)

        menu.addAction(self.action_toggle_settings)
        menu.addAction(self.action_toggle_move)
        menu.addSeparator()
        menu.addAction(self.action_quit)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.toggle_settings()

    def toggle_settings(self):
        if self.settings_window.isVisible():
            self.settings_window.hide()
        else:
            self.settings_window.setWindowState(
                self.settings_window.windowState() & ~Qt.WindowState.WindowMinimized
            )
            self.settings_window.show()
            self.settings_window.raise_()
            self.settings_window.activateWindow()

    def set_move_mode(self, enabled: bool):
        self.action_toggle_move.blockSignals(True)
        self.action_toggle_move.setChecked(enabled)
        self.action_toggle_move.blockSignals(False)

        self.settings_window.move_mode_checkbox.blockSignals(True)
        self.settings_window.move_mode_checkbox.setChecked(enabled)
        self.settings_window.move_mode_checkbox.blockSignals(False)

        if self.overlay is not None:
            self.overlay.set_click_through(not enabled)

    def apply_settings(self, settings: dict):
        self.config.update(settings)
        save_config(self.config)
        if self.overlay is not None:
            self.overlay.update_settings(self.config)

    def start_overlay(self, settings: dict):
        self.config.update(settings)
        save_config(self.config)

        if self.overlay is None:
            self.overlay = OverlayWindow(self.config)
            self.overlay.position_saved.connect(self._on_position_saved)
            self.overlay.size_saved.connect(self._on_size_saved)
            self.overlay.show()
            self.overlay.set_click_through(True)
        else:
            self.overlay.update_settings(self.config)
            self.overlay.show()

        if self.worker is not None:
            self.worker.stop()
            self.worker.wait(2000)

        self.worker = KickChatWorker(settings["username"])
        self.worker.status_changed.connect(self.settings_window.set_status)
        self.worker.error_occurred.connect(self._on_worker_error)
        self.worker.message_received.connect(self._on_chat_message)
        self.worker.start()

    def stop_overlay(self):
        if self.worker is not None:
            self.worker.stop()
            self.worker.wait(2000)
            self.worker = None
        if self.overlay is not None:
            self.overlay.hide()
        self.settings_window.on_stopped()
        self.settings_window.show()

    def _on_position_saved(self, x: int, y: int):
        self.config["overlay_x"] = x
        self.config["overlay_y"] = y
        save_config(self.config)

    def _on_size_saved(self, width: int, height: int):
        self.config["overlay_width"] = width
        self.config["overlay_height"] = height
        save_config(self.config)

    def _on_worker_error(self, message: str):
        self.settings_window.set_status(f"Hata: {message}")

    def _on_chat_message(self, data: dict):
        if self.overlay is None:
            return
        sender = data.get("sender", {}) or {}
        username = sender.get("username", "???")
        identity = sender.get("identity", {}) or {}
        color = identity.get("color") or "#63f5c2"
        badges = [b.get("type", "") for b in (identity.get("badges") or [])]
        content = data.get("content", "")
        msg_type = data.get("type", "message")
        self.overlay.add_message(username, content, color, badges, msg_type)

    def quit(self):
        if self.worker is not None:
            self.worker.stop()
            self.worker.wait(2000)
        self.tray.hide()
        self.qapp.quit()

    def run(self):
        return self.qapp.exec()


if __name__ == "__main__":
    app = App()
    sys.exit(app.run())
