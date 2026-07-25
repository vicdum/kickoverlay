"""Kanala ozel abone rozetleri.

Kimlik rozetleri (moderator/VIP/kurucu...) her kanalda ayni ve vektorel
oldugu icin uygulamaya gomulu (bkz. badge_icons). Abone rozetlerini ise
her yayinci kendisi yukler ve ay sayisina gore farkli gorsel tanimlar;
bunlar kanal API'sinden gelen PNG'ler. Emote'lar gibi bir kez indirilip
diske cache'lenir.

Yazma islerini (set_tiers/precache) baglanti thread'i, okuma islerini
(path_for_months/dominant_color) GUI thread'i yapar - bu yuzden kademe
listesi kilitli.
"""
import os
import threading

import requests

from config import APPDATA_DIR
from logger import get_logger

log = get_logger("sub_badge")

SUB_BADGE_DIR = os.path.join(APPDATA_DIR, "sub_badges")
_HEADERS = {"User-Agent": "Mozilla/5.0"}

_lock = threading.Lock()
_tiers: list = []          # [(months, badge_id, url)] - aya gore artan
_color_cache: dict = {}


def badge_file(badge_id) -> str:
    return os.path.join(SUB_BADGE_DIR, f"{badge_id}.png")


def set_tiers(raw) -> int:
    """Kanal API'sindeki subscriber_badges listesini kaydeder.

    Beklenen yapi: [{"id": 97968, "months": 1,
                     "badge_image": {"src": "https://files.kick.com/..."}}]
    """
    parsed = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        badge_id = item.get("id")
        url = ((item.get("badge_image") or {}).get("src") or "").strip()
        if not badge_id or not url:
            continue
        try:
            months = int(item.get("months") or 0)
        except (TypeError, ValueError):
            continue
        parsed.append((months, badge_id, url))

    parsed.sort(key=lambda tier: tier[0])
    with _lock:
        _tiers[:] = parsed
    log.info("%s abone rozet kademesi bulundu (aylar=%s)",
             len(parsed), [tier[0] for tier in parsed])
    return len(parsed)


def clear():
    with _lock:
        _tiers.clear()


def precache(should_continue=None) -> int:
    """Kademe gorsellerini diske indirir. Baglanti thread'inden cagrilir.

    should_continue: False donerse indirme birakilir (kapanis sirasinda
    thread'in bos yere ag beklemesini onler).
    """
    with _lock:
        snapshot = list(_tiers)
    done = 0
    for _months, badge_id, url in snapshot:
        if should_continue is not None and not should_continue():
            log.debug("abone rozeti indirme yarida birakildi")
            break
        if _download(badge_id, url):
            done += 1
    return done


def _download(badge_id, url) -> bool:
    path = badge_file(badge_id)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return True
    try:
        os.makedirs(SUB_BADGE_DIR, exist_ok=True)
        resp = requests.get(url, headers=_HEADERS, timeout=(5, 10))
        resp.raise_for_status()
        with open(path, "wb") as f:
            f.write(resp.content)
        log.debug("abone rozeti indirildi id=%s (%s bayt)", badge_id, len(resp.content))
        return True
    except Exception as exc:
        log.debug("abone rozeti indirilemedi id=%s: %s", badge_id, exc)
        return False


def path_for_months(months) -> str | None:
    """Abonelik ayina karsilik gelen, diske inmis rozet dosyasi.

    Ay sayisini gecmeyen en yuksek kademe secilir (Kick de boyle yapar:
    7 aylik abone, 6 ay rozetini tasir). Kanal rozet tanimlamamissa ya
    da gorsel henuz inmediyse None doner; cagiran taraf gomulu ikona
    duser.
    """
    try:
        months = int(months)
    except (TypeError, ValueError):
        months = 0

    with _lock:
        snapshot = list(_tiers)
    if not snapshot:
        return None

    chosen = None
    for tier_months, badge_id, _url in snapshot:
        if tier_months <= months:
            chosen = badge_id
        else:
            break
    if chosen is None:
        # count gelmemis ya da en dusuk kademenin altinda: ilk kademe
        chosen = snapshot[0][1]

    path = badge_file(chosen)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path
    return None


def dominant_color(path: str) -> str | None:
    """Rozet gorselinin baskin rengi (#rrggbb).

    "Rol rengine gore cerceve" secildiginde abone rozetleri icin sabit
    bir renk yok - her kanalin rozeti farkli. Cerceve gercekten gorunen
    rozetle uyusmasi icin renk gorselden okunuyor. Doygunluga gore
    agirliklandirilir, yoksa beyaz kenarlik/golge ortalamayi griye
    cekiyor.
    """
    if not path:
        return None
    if path in _color_cache:
        return _color_cache[path]

    color = None
    try:
        from PyQt6.QtGui import QColor, QImage

        img = QImage(path)
        if not img.isNull():
            img = img.convertToFormat(QImage.Format.Format_ARGB32).scaled(8, 8)
            r = g = b = 0.0
            weight_sum = 0.0
            for y in range(img.height()):
                for x in range(img.width()):
                    px = img.pixelColor(x, y)
                    if px.alpha() < 128:
                        continue
                    weight = 1.0 + px.saturation()
                    r += px.red() * weight
                    g += px.green() * weight
                    b += px.blue() * weight
                    weight_sum += weight
            if weight_sum > 0:
                out = QColor(int(r / weight_sum), int(g / weight_sum), int(b / weight_sum))
                if out.value() < 70:
                    # cok koyu renk ince cercevede siyaha benziyor
                    out = out.lighter(170)
                color = out.name()
    except Exception as exc:
        log.debug("rozet rengi okunamadi (%s): %s", path, exc)

    _color_cache[path] = color
    return color
