import json
import os

APP_VERSION = "1.3.0"

APPDATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "KickOverlay")
CONFIG_PATH = os.path.join(APPDATA_DIR, "config.json")

DEFAULTS = {
    "username": "",
    "font_size": 16,
    "font_family": "",        # bos = Qt/sistem varsayilani
    "font_weight": 400,       # 100..900 (CSS agirlik degeri)
    "font_italic": False,
    "overlay_opacity": 100,
    "message_duration": 12,
    "overlay_width": 420,
    "overlay_height": 500,
    "overlay_x": 80,
    "overlay_y": 80,

    "bg_color": "#000000",
    "bg_darkness": 140,
    "message_text_color": "#ffffff",
    "username_color_mode": "kick",
    "username_color_custom": "#63f5c2",

    "highlight_enabled": True,
    "highlight_users": [],
    "highlight_roles": [],
    "highlight_color": "#ff9900",
    "highlight_alpha": 200,

    # vurgu stili: arka plan boyama ve cerceve birbirinden bagimsiz
    "highlight_bg_enabled": True,
    "highlight_border_mode": "custom",   # none | custom | username | role
    "highlight_border_color": "#ff9900",
    "highlight_border_width": 3,
    "highlight_border_sides": "left",    # left | full

    # etiket (mention) vurgulama: mesajin ICERIGINDE gecen isimler
    "mention_enabled": True,
    "mention_names": [],
    "mention_color": "#ffd400",
    "mention_bold": True,
    "mention_bg_enabled": False,
    "mention_bg_color": "#5a3d00",
    "mention_bg_alpha": 210,
    "mention_border_enabled": False,
    "mention_border_color": "#ffd400",
    "mention_border_width": 3,
    "mention_border_sides": "left",   # left | full
    "mention_sound_enabled": False,
    "mention_sound_path": "",         # bos = Windows sistem sesi (.wav bekler)
    "mention_sound_cooldown": 3,

    "blocked_keywords": [],
    "blocked_users": [],
    "hide_bot_messages": False,
    "bot_users": ["botrix", "kicklet", "streamelements", "fossabot", "wizebot", "moobot"],
    "hide_bot_commands": False,
    "bot_command_prefix": "!",
    "hide_notifications": False,

    "debug_logs": False,
}


def _log():
    # Gecikmeli import: logger modulu config'i import ediyor, dairesel
    # import olmamasi icin fonksiyon icinde cagiriliyor.
    from logger import get_logger
    return get_logger("config")


def load_config() -> dict:
    cfg = DEFAULTS.copy()
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            saved = json.load(f)
        cfg.update(saved)
    except FileNotFoundError:
        pass
    except json.JSONDecodeError as exc:
        _log().warning("config.json bozuk, varsayilanlar kullanilacak: %s", exc)
    except OSError as exc:
        _log().warning("config.json okunamadi: %s", exc)
    return cfg


def save_config(cfg: dict) -> bool:
    """Ayarlari diske yazar. Hata firlatmaz - basari durumunu dondurur.

    Eskiden hata firlatiyordu; bir slot icinde firlayan hata PyQt'de
    qFatal() tetikleyip uygulamayi sessizce kapatabiliyordu.
    """
    try:
        os.makedirs(APPDATA_DIR, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        return True
    except Exception as exc:
        _log().error("config kaydedilemedi (%s): %s", CONFIG_PATH, exc, exc_info=True)
        return False
