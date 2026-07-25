"""Merkezi log sistemi.

--noconsole ile derlenen bir PyQt uygulamasinda stdout/stderr yoktur, bu
yuzden hicbir hata mesaji kullaniciya ulasmaz: uygulama sessizce kapanir.
Bu modul uc ayri katmani dosyaya yazar:

1. logging  -> kickoverlay.log   (uygulama olaylari + Python traceback'leri)
2. faulthandler -> crash.log     (Qt/C++ tarafindaki segfault gibi sert
                                  cokmeler; Python traceback uretmez)
3. Qt mesajlari -> kickoverlay.log (qWarning/qCritical/qFatal ciktilari)

ONEMLI DAVRANIS: PyQt6'da bir slot icinde yakalanmayan hata olustugunda,
sys.excepthook varsayilan hook ise PyQt qFatal() cagirir ve surec aninda
abort eder (uygulama "kendi kendine kapanir"). Kendi excepthook'umuzu
kurdugumuz icin bu hatalar artik loglanir ve uygulama ayakta kalir.
"""

import faulthandler
import logging
import logging.handlers
import os
import platform
import sys
import threading

from config import APPDATA_DIR

LOG_DIR = os.path.join(APPDATA_DIR, "logs")
LOG_PATH = os.path.join(LOG_DIR, "kickoverlay.log")
CRASH_PATH = os.path.join(LOG_DIR, "crash.log")

LOG_FORMAT = "%(asctime)s [%(levelname)-8s] %(threadName)-12s %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

log = logging.getLogger("kickoverlay")

# faulthandler C seviyesinde yazdigi icin dosya nesnesi surec boyunca
# acik kalmali; kapanirsa cokme aninda hicbir sey yazilamaz.
_crash_file = None
_configured = False


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    global _configured
    if _configured:
        return log

    log.setLevel(level)
    log.propagate = False

    # Log altyapisinin kendisi asla uygulamayi dusurmemeli. Derlenmis
    # --noconsole exe'de stderr yok, bu yuzden logging'in ic hatalarini
    # yazacak yer de yok.
    logging.raiseExceptions = False

    formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)

    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            LOG_PATH, maxBytes=1_000_000, backupCount=3, encoding="utf-8", delay=True
        )
        file_handler.setFormatter(formatter)
        log.addHandler(file_handler)
    except Exception:
        # Diske yazamiyorsak (yetki/disk dolu) uygulama yine de acilmali.
        log.addHandler(logging.NullHandler())

    # Derlenmis --noconsole exe'de sys.stderr None olur, o durumda atla.
    if sys.stderr is not None:
        stream_handler = logging.StreamHandler(sys.stderr)
        stream_handler.setFormatter(formatter)
        log.addHandler(stream_handler)

    _enable_faulthandler()
    _install_excepthooks()
    install_qt_message_handler()

    _configured = True
    _log_environment()
    return log


def _enable_faulthandler():
    global _crash_file
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        # crash.log surekli append edilir; sinirsiz buyumesin.
        mode = "a"
        try:
            if os.path.getsize(CRASH_PATH) > 512_000:
                mode = "w"
        except OSError:
            pass
        _crash_file = open(CRASH_PATH, mode, encoding="utf-8", buffering=1)
        _crash_file.write(f"\n=== oturum basladi (pid {os.getpid()}) ===\n")
        faulthandler.enable(file=_crash_file, all_threads=True)
    except Exception as exc:
        log.warning("faulthandler acilamadi: %s", exc)


def _install_excepthooks():
    def _hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        log.critical(
            "YAKALANMAYAN HATA: %s: %s", exc_type.__name__, exc_value,
            exc_info=(exc_type, exc_value, exc_tb),
        )
        flush()

    sys.excepthook = _hook

    def _thread_hook(args):
        if issubclass(args.exc_type, SystemExit):
            return
        log.critical(
            "THREAD ICINDE YAKALANMAYAN HATA (%s): %s",
            getattr(args.thread, "name", "?"), args.exc_value,
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )
        flush()

    threading.excepthook = _thread_hook


def install_qt_message_handler():
    """Qt'nin kendi uyari/hata mesajlarini log dosyasina yonlendirir."""
    try:
        from PyQt6.QtCore import QtMsgType, qInstallMessageHandler
    except Exception as exc:  # pragma: no cover
        log.warning("Qt mesaj handler kurulamadi: %s", exc)
        return

    levels = {
        QtMsgType.QtDebugMsg: logging.DEBUG,
        QtMsgType.QtInfoMsg: logging.INFO,
        QtMsgType.QtWarningMsg: logging.WARNING,
        QtMsgType.QtCriticalMsg: logging.ERROR,
        QtMsgType.QtFatalMsg: logging.CRITICAL,
    }
    qt_log = logging.getLogger("kickoverlay.qt")

    def handler(mode, context, message):
        where = ""
        if context is not None and context.file:
            where = f" ({context.file}:{context.line})"
        qt_log.log(levels.get(mode, logging.INFO), "%s%s", message, where)
        if mode == QtMsgType.QtFatalMsg:
            flush()

    qInstallMessageHandler(handler)


def _log_environment():
    log.info("=" * 62)
    log.info("Kick Chat Overlay basliyor")
    log.info("surum=%s python=%s", _app_version(), sys.version.split()[0])
    log.info("platform=%s pid=%s", platform.platform(), os.getpid())
    log.info("frozen=%s exe=%s", getattr(sys, "frozen", False), sys.executable)
    log.info("log dosyasi=%s", LOG_PATH)
    try:
        from PyQt6.QtCore import QT_VERSION_STR, PYQT_VERSION_STR
        log.info("Qt=%s PyQt=%s", QT_VERSION_STR, PYQT_VERSION_STR)
    except Exception:
        pass


def _app_version() -> str:
    try:
        from config import APP_VERSION
        return APP_VERSION
    except Exception:
        return "?"


def flush():
    for handler in log.handlers:
        try:
            handler.flush()
        except Exception:
            pass


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"kickoverlay.{name}")


def open_log_folder() -> bool:
    """Log klasorunu Explorer'da acar (ayarlar penceresindeki dugme icin)."""
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QDesktopServices
        return QDesktopServices.openUrl(QUrl.fromLocalFile(LOG_DIR))
    except Exception as exc:
        log.warning("log klasoru acilamadi: %s", exc)
        return False
