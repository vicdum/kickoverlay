import logging
import os
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QColor, QIcon, QPixmap
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from config import load_config, save_config
from kick_client import KickChatWorker
from logger import flush, get_logger, setup_logging
from overlay_window import OverlayWindow
from resources import app_icon
from settings_window import SettingsWindow

log = get_logger("app")


def make_tray_icon() -> QIcon:
    icon = app_icon()
    if icon is not None:
        return icon
    pixmap = QPixmap(32, 32)
    pixmap.fill(QColor(83, 249, 129))
    return QIcon(pixmap)


class App:
    def __init__(self):
        self.qapp = QApplication(sys.argv)
        self.qapp.setQuitOnLastWindowClosed(False)
        icon = app_icon()
        if icon is not None:
            self.qapp.setWindowIcon(icon)
        self.qapp.aboutToQuit.connect(self._on_about_to_quit)
        self._connect_session_signals()

        self.config = load_config()
        if self.config.get("debug_logs"):
            logging.getLogger("kickoverlay").setLevel(logging.DEBUG)
            log.info("ayrintili (DEBUG) log acik")
        log.info("ayarlar yuklendi: kanal=%r sure=%ss opaklik=%s%%",
                 self.config.get("username"), self.config.get("message_duration"),
                 self.config.get("overlay_opacity"))

        self.settings_window = SettingsWindow(self.config)
        if icon is not None:
            self.settings_window.setWindowIcon(icon)
        self.overlay = None
        self.worker = None
        self._quitting = False

        self._build_tray()

        self.settings_window.start_requested.connect(self.start_overlay)
        self.settings_window.stop_requested.connect(self.stop_overlay)
        self.settings_window.settings_changed.connect(self.apply_settings)
        self.settings_window.move_mode_toggled.connect(self.set_move_mode)
        self.settings_window.quit_requested.connect(self.quit)

        self.settings_window.show()
        log.info("uygulama hazir")

    # ---- kapanis izleme -------------------------------------------------
    def _connect_session_signals(self):
        """Windows oturum kapanisi/yeniden baslatmayi loga yazar.

        Uygulamanin 'kendi kendine kapandigi' vakalarin bir kismi aslinda
        Windows'un oturumu kapatmasi olabilir; bu ayirt edilebilmeli.
        """
        try:
            self.qapp.commitDataRequest.connect(
                lambda _mgr: log.warning("Windows oturum kapatma istegi geldi (commitDataRequest)")
            )
            self.qapp.saveStateRequest.connect(
                lambda _mgr: log.info("Windows durum kaydetme istegi (saveStateRequest)")
            )
        except Exception as exc:
            log.debug("oturum sinyalleri baglanamadi: %s", exc)

    def _on_about_to_quit(self):
        log.info("aboutToQuit - Qt olay dongusu kapaniyor (duzgun kapanis)")
        flush()

    def _build_tray(self):
        self.tray = QSystemTrayIcon(make_tray_icon())
        self.tray.setToolTip("Kick Chat Overlay")

        # QMenu self'te tutulmali: QSystemTrayIcon.setContextMenu sahiplik
        # almaz, yerel degisken olarak kalirsa menu erken silinebilir.
        menu = self.tray_menu = QMenu()
        self.action_toggle_settings = QAction("Ayarları Göster/Gizle")
        self.action_toggle_settings.triggered.connect(self.toggle_settings)
        self.action_toggle_move = QAction("Taşıma Modu")
        self.action_toggle_move.setCheckable(True)
        self.action_toggle_move.toggled.connect(self.set_move_mode)
        self.action_quit = QAction("Çıkış")
        self.action_quit.triggered.connect(self._quit_from_tray)

        menu.addAction(self.action_toggle_settings)
        menu.addAction(self.action_toggle_move)
        menu.addSeparator()
        menu.addAction(self.action_quit)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

        if not QSystemTrayIcon.isSystemTrayAvailable():
            log.warning("sistem tepsisi kullanilamiyor - tray ikonu gorunmeyebilir")

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
        log.info("tasima modu=%s", enabled)
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
        if self.config.get("debug_logs"):
            logging.getLogger("kickoverlay").setLevel(logging.DEBUG)
        else:
            logging.getLogger("kickoverlay").setLevel(logging.INFO)
        if self.overlay is not None:
            self.overlay.update_settings(self.config)

    def start_overlay(self, settings: dict):
        log.info("BASLAT istegi (kanal=%r)", settings.get("username"))
        self.config.update(settings)
        save_config(self.config)

        if self.overlay is None:
            self.overlay = OverlayWindow(self.config)
            self.overlay.position_saved.connect(self._on_position_saved)
            self.overlay.size_saved.connect(self._on_size_saved)
            self.overlay.show()
            self.overlay.set_click_through(True)
            log.info("overlay olusturuldu (%sx%s @ %s,%s)",
                     self.config["overlay_width"], self.config["overlay_height"],
                     self.config["overlay_x"], self.config["overlay_y"])
        else:
            self.overlay.update_settings(self.config)
            self.overlay.show()

        self._shutdown_worker("yeniden baslatma")

        self.worker = KickChatWorker(settings["username"])
        self.worker.status_changed.connect(self.settings_window.set_status)
        self.worker.error_occurred.connect(self._on_worker_error)
        self.worker.message_received.connect(self._on_chat_message)
        self.worker.finished.connect(lambda: log.info("worker QThread sonlandi"))
        self.worker.start()

    def _shutdown_worker(self, reason: str):
        """Worker thread'ini kesin olarak durdurur.

        Thread hala calisirken surec kapanirsa Windows access violation
        (0xC0000005) ile cokuyor - crash.log'da bu boyle tespit edildi.
        Bu yuzden wait() basarisiz olursa terminate() ile zorlaniyor.
        """
        worker = self.worker
        if worker is None:
            return
        self.worker = None
        log.info("worker kapatiliyor (%s)", reason)
        worker.stop()
        if not worker.wait(4000):
            log.warning("worker 4 sn icinde durmadi - terminate() cagiriliyor")
            worker.terminate()
            if not worker.wait(1500):
                log.error("worker terminate() sonrasi da durmadi")

    def stop_overlay(self):
        log.info("DURDUR istegi")
        self._shutdown_worker("durdur")
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
        # Tek bir bozuk mesaj yuzunden uygulamanin kapanmamasi icin
        # bu slot bastan sona korunuyor.
        try:
            msg_type = data.get("type", "message")
            if msg_type == "message_deleted":
                if self.config.get("remove_deleted_messages"):
                    self.overlay.remove_message_by_id(data.get("message_id"))
                return

            sender = data.get("sender", {}) or {}
            username = sender.get("username", "???")
            identity = sender.get("identity", {}) or {}
            color = identity.get("color") or "#63f5c2"
            # rozet sozlukleri oldugu gibi gecirilir: abone rozetinin
            # dogru gorseli icin ay sayisi ("count") gerekiyor
            badges = [b for b in (identity.get("badges") or []) if isinstance(b, dict)]
            content = data.get("content", "")
            message_id = data.get("id")
            self.overlay.add_message(username, content, color, badges, msg_type, message_id)
        except Exception as exc:
            log.error("mesaj islenemedi: %s | veri=%.400r", exc, data, exc_info=True)

    def _quit_from_tray(self):
        log.info("cikis: tepsi menusu")
        self.quit()

    def quit(self):
        if self._quitting:
            return
        self._quitting = True
        log.info("cikis basliyor")
        self._shutdown_worker("cikis")
        if self.overlay is not None:
            self.overlay.close()
        self.tray.hide()
        self.qapp.quit()

    def run(self):
        code = self.qapp.exec()
        log.info("Qt exec() donus kodu=%s", code)
        return code


if __name__ == "__main__":
    setup_logging()
    exit_code = 1
    try:
        app = App()
        exit_code = app.run()
    except Exception:
        log.critical("baslatma sirasinda olumcul hata", exc_info=True)
    finally:
        log.info("surec bitiyor (kod=%s)", exit_code)
        flush()

    # sys.exit() yerine os._exit(): Python'un finalize adimi Qt nesnelerini
    # tanimsiz sirada yok ediyor ve bu access violation (0xC0000005) ile
    # cokebiliyor. exec() zaten dondu, aboutToQuit isledi ve loglar flush
    # edildi - bu noktadan sonra yapilacak is yok. Bu sadece cikisi
    # deterministik yapar; cikistan ONCEKI her cokme faulthandler ile
    # crash.log'a yazilmaya devam eder.
    os._exit(exit_code)
