import json
import os

APPDATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "KickOverlay")
CONFIG_PATH = os.path.join(APPDATA_DIR, "config.json")

DEFAULTS = {
    "username": "",
    "font_size": 16,
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

    "blocked_keywords": [],
    "blocked_users": [],
    "hide_bot_messages": False,
    "bot_users": ["botrix", "kicklet", "streamelements", "fossabot", "wizebot", "moobot"],
    "hide_bot_commands": False,
    "bot_command_prefix": "!",
    "hide_notifications": False,
}


def load_config() -> dict:
    cfg = DEFAULTS.copy()
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            saved = json.load(f)
        cfg.update(saved)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return cfg


def save_config(cfg: dict) -> None:
    os.makedirs(APPDATA_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
