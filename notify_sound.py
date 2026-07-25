"""Etiketlendiginde ses calar.

QtMultimedia kullanilmiyor: exe boyutunu kucuk tutmak icin spec dosyalarinda
Qt6 Multimedia paketten cikariliyor (bkz. README). Onun yerine stdlib'deki
winsound yeterli - uygulama zaten Windows'a ozel (click-through icin user32
API'leri kullaniliyor).

Sinir: winsound sadece WAV calar ve ses seviyesi ayarlanamaz. Baska bir
uzanti verilirse ya da dosya yoksa Windows sistem sesine dusulur.
"""
import os
import time

from logger import get_logger

log = get_logger("sound")

try:
    import winsound
except ImportError:  # Windows disi ortam (test/CI)
    winsound = None
    log.debug("winsound yok - ses calma devre disi")

_last_played = 0.0
_warned = set()


def _fallback_beep():
    winsound.MessageBeep(winsound.MB_ICONASTERISK)


def play(path: str | None = None, cooldown: float = 3.0, force: bool = False) -> bool:
    """Ses calar, hata firlatmaz. Caldiysa True doner.

    cooldown: iki ses arasindaki en kisa sure (sn). Yogun sohbette her
    etikette ses calmak uygulamayi kullanilamaz hale getiriyor.
    force: "Dene" dugmesi icin bekleme suresini atlar.
    """
    global _last_played
    if winsound is None:
        return False

    try:
        cooldown = max(0.0, float(cooldown))
    except (TypeError, ValueError):
        cooldown = 3.0

    now = time.monotonic()
    if not force and now - _last_played < cooldown:
        return False
    _last_played = now

    # Bu fonksiyon bir Qt slotu icinden cagriliyor: buradan firlayan hata
    # qFatal() tetikleyip uygulamayi sessizce kapatabilir.
    try:
        path = (path or "").strip()
        if not path:
            _fallback_beep()
            return True
        if os.path.isfile(path) and path.lower().endswith(".wav"):
            winsound.PlaySound(
                path,
                winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
            )
            return True
        if path not in _warned:
            _warned.add(path)
            log.warning("ses dosyasi kullanilamadi (%r) - sistem sesi calinacak "
                        "(sadece var olan .wav dosyalari desteklenir)", path)
        _fallback_beep()
        return True
    except Exception as exc:
        log.error("ses calinamadi (%r): %s", path, exc, exc_info=True)
        return False
