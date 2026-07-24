import html
import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel

from badge_icons import get_badge_icon_data_uri
from emote_cache import EMOTE_TOKEN_RE, emote_path


def hex_to_rgba(hex_color: str, alpha: int) -> str:
    hex_color = (hex_color or "#000000").lstrip("#")
    if len(hex_color) != 6:
        hex_color = "000000"
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return f"rgba({r},{g},{b},{max(0, min(255, alpha))})"


def render_content_html(content: str, img_size: int) -> str:
    """Metni HTML-escape eder, [emote:ID:NAME] tokenlarini onceden
    diske inmis gorsellere (bkz. emote_cache) <img> olarak cevirir."""
    content = content or ""
    parts = []
    last_end = 0
    for m in EMOTE_TOKEN_RE.finditer(content):
        parts.append(html.escape(content[last_end:m.start()]))
        emote_id, name = m.group(1), m.group(2)
        path = emote_path(emote_id)
        if os.path.exists(path):
            uri = "file:///" + path.replace("\\", "/")
            parts.append(f'<img src="{uri}" height="{img_size}" style="vertical-align:middle;">')
        else:
            parts.append(html.escape(f":{name}:"))
        last_end = m.end()
    parts.append(html.escape(content[last_end:]))
    return "".join(parts)


class ChatMessageWidget(QLabel):
    def __init__(self, username: str, content: str, sender_color: str, badges: list,
                 settings: dict, is_highlighted: bool, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setWordWrap(True)
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        font_size = settings.get("font_size", 16)
        text_color = settings.get("message_text_color", "#ffffff")
        if settings.get("username_color_mode") == "custom":
            user_color = settings.get("username_color_custom") or "#63f5c2"
        else:
            user_color = sender_color or "#63f5c2"

        badge_size = max(font_size, 14)
        badge_html = ""
        for badge in badges or []:
            uri = get_badge_icon_data_uri(badge, badge_size)
            if uri:
                badge_html += (
                    f'<img src="{uri}" width="{badge_size}" height="{badge_size}" '
                    f'style="vertical-align:middle;margin-right:3px;">'
                )

        safe_user = html.escape(username or "???")
        content_html = render_content_html(content, max(font_size + 4, 18))

        text = (
            f'{badge_html}'
            f'<span style="color:{user_color};font-weight:600;">{safe_user}</span>'
            f'<span style="color:{text_color};">: {content_html}</span>'
        )
        self.setText(text)

        if is_highlighted:
            bg = hex_to_rgba(settings.get("highlight_color", "#ff9900"), settings.get("highlight_alpha", 200))
            border = settings.get("highlight_color", "#ff9900")
        else:
            bg = hex_to_rgba(settings.get("bg_color", "#000000"), settings.get("bg_darkness", 140))
            border = "transparent"

        self.setStyleSheet(
            "QLabel {"
            f"background-color: {bg};"
            f"border-left: 3px solid {border};"
            f"font-size: {font_size}px;"
            "padding: 6px 10px;"
            "border-radius: 8px;"
            "}"
        )
