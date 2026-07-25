"""Gomulu kaynak dosyalarina (icon.ico gibi) yol bulur.

Gelistirme ortaminda dosya main.py'nin yaninda; PyInstaller onefile'da
her calistirmada %TEMP%'e acilan gecici klasorde (sys._MEIPASS), onedir'de
ise exe ile ayni klasorde. Spec dosyalari icon.ico'yu "datas" olarak
pakete ekliyor (sadece EXE() icon= parametresi exe simgesini ayarlar,
QIcon calisma zamaninda diskten okuyacagi bir dosyaya ihtiyac duyar).
"""
import os
import sys

from logger import get_logger

log = get_logger("resources")

_BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


def resource_path(name: str) -> str:
    return os.path.join(_BASE_DIR, name)


_icon_cache = None


def app_icon():
    """QIcon dondurur; bulunamaz ya da yuklenemezse None (cagiran varsayilana duser).

    QSystemTrayIcon'a null bir QIcon verilirse Windows'ta sessizce
    gorunmez/tiklanamaz olur ("No Icon set" uyarisi) - bir kere boyle
    kirilip tray'e geri donulemedigi icin isNull() burada mutlaka
    kontrol ediliyor.
    """
    global _icon_cache
    if _icon_cache is not None:
        return _icon_cache
    from PyQt6.QtGui import QIcon
    path = resource_path("icon.ico")
    if not os.path.isfile(path):
        log.warning("icon.ico bulunamadi (%s) - varsayilan pencere ikonu kullanilacak", path)
        return None
    icon = QIcon(path)
    if icon.isNull():
        log.warning("icon.ico yuklenemedi (bos QIcon, %s) - "
                    "Qt'nin ICO gorsel eklentisi (qico.dll) eksik olabilir", path)
        return None
    _icon_cache = icon
    return icon
