import os
import re

import requests

from config import APPDATA_DIR

EMOTE_DIR = os.path.join(APPDATA_DIR, "emotes")
EMOTE_TOKEN_RE = re.compile(r"\[emote:(\d+):([^\]]*)\]")

_HEADERS = {"User-Agent": "Mozilla/5.0"}


def emote_path(emote_id: str) -> str:
    return os.path.join(EMOTE_DIR, f"{emote_id}.png")


def ensure_cached(emote_id: str) -> bool:
    """Emote gorselini diske indirir (varsa dokunmaz). Baglanti thread'inden cagrilir."""
    path = emote_path(emote_id)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return True
    os.makedirs(EMOTE_DIR, exist_ok=True)
    url = f"https://files.kick.com/emotes/{emote_id}/fullsize"
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=5)
        resp.raise_for_status()
        with open(path, "wb") as f:
            f.write(resp.content)
        return True
    except Exception:
        return False


def precache_emotes(content: str) -> None:
    for emote_id, _name in EMOTE_TOKEN_RE.findall(content or ""):
        ensure_cached(emote_id)
