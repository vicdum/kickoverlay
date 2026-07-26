"""Etiketlendiginde ses calar.

QtMultimedia kullanilmiyor: exe boyutunu kucuk tutmak icin spec dosyalarinda
Qt6 Multimedia paketten cikariliyor (bkz. README). Onun yerine stdlib'deki
winsound + winmm MCI yeterli - uygulama zaten Windows'a ozel (click-through
icin user32 API'leri kullaniliyor).

Sinir: winsound sadece WAV calar. MP3 icin winmm.dll'in MCI arayuzu
(ctypes uzerinden, ek bagimlilik yok) kullaniliyor. FLAC'in Windows'ta
varsayilan bir MCI/codec destegi olmadigindan calinamiyor - secilirse
sistem sesine dusulur.
"""
import ctypes
import os
import threading
import time

from logger import get_logger
from resources import resource_path

log = get_logger("sound")

try:
    import winsound
except ImportError:  # Windows disi ortam (test/CI)
    winsound = None
    log.debug("winsound yok - ses calma devre disi")

_last_played = 0.0
_warned = set()

BUILTIN_PREFIX = "builtin:"
_PLAYABLE_EXTS = (".wav", ".mp3")

_mci_seq = 0


def _sounds_dir() -> str:
    return resource_path("sounds")


def _friendly_sound_name(filename: str) -> str:
    stem = os.path.splitext(filename)[0]
    parts = stem.split("__")
    core = parts[-1] if len(parts) >= 2 else stem
    core = core.replace("_", " ").replace("-", " ").strip()
    core = core or stem
    return core[0].upper() + core[1:] if core else filename


def list_builtin_sounds() -> list[tuple[str, str]]:
    """(token, gorunen_isim) listesi doner. token = 'builtin:<dosya adi>'."""
    folder = _sounds_dir()
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return []
    result = []
    for name in names:
        if name.lower().endswith(_PLAYABLE_EXTS) and os.path.isfile(os.path.join(folder, name)):
            result.append((BUILTIN_PREFIX + name, _friendly_sound_name(name)))
    return result


def resolve_sound_path(path: str) -> str:
    """'builtin:x.wav' gibi bir token'i gercek dosya yoluna cevirir."""
    if path.startswith(BUILTIN_PREFIX):
        candidate = os.path.join(_sounds_dir(), path[len(BUILTIN_PREFIX):])
        return candidate if os.path.isfile(candidate) else ""
    return path


def _fallback_beep():
    winsound.MessageBeep(winsound.MB_ICONASTERISK)


def _play_via_mci(path: str) -> bool:
    """MP3 gibi winsound'un calamadigi formatlar icin winmm MCI ile calar."""
    global _mci_seq
    _mci_seq += 1
    alias = f"kco_snd_{_mci_seq}"
    try:
        winmm = ctypes.windll.winmm
        if winmm.mciSendStringW(f'open "{path}" alias {alias}', None, 0, None) != 0:
            return False
        length_buf = ctypes.create_unicode_buffer(32)
        winmm.mciSendStringW(f"status {alias} length", length_buf, 32, None)
        try:
            length_ms = int(length_buf.value)
        except ValueError:
            length_ms = 4000
        if winmm.mciSendStringW(f"play {alias}", None, 0, None) != 0:
            winmm.mciSendStringW(f"close {alias}", None, 0, None)
            return False
        timer = threading.Timer(
            length_ms / 1000 + 0.5,
            lambda: winmm.mciSendStringW(f"close {alias}", None, 0, None),
        )
        timer.daemon = True
        timer.start()
        return True
    except Exception as exc:
        log.error("mp3 calinamadi (%r): %s", path, exc, exc_info=True)
        return False


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
        path = resolve_sound_path(path)
        if os.path.isfile(path) and path.lower().endswith(".wav"):
            winsound.PlaySound(
                path,
                winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
            )
            return True
        if os.path.isfile(path) and path.lower().endswith(".mp3") and _play_via_mci(path):
            return True
        if path not in _warned:
            _warned.add(path)
            log.warning("ses dosyasi kullanilamadi (%r) - sistem sesi calinacak "
                        "(sadece var olan .wav/.mp3 dosyalari desteklenir)", path)
        _fallback_beep()
        return True
    except Exception as exc:
        log.error("ses calinamadi (%r): %s", path, exc, exc_info=True)
        return False
