import html
import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel

import mentions
import sub_badges
from badge_icons import get_badge_icon_data_uri, normalize_badges, role_color
from emote_cache import EMOTE_TOKEN_RE, emote_path
from turkish import tr_fold

BORDER_MODES = ("none", "custom", "username", "role")
FONT_WEIGHTS = (100, 200, 300, 400, 500, 600, 700, 800, 900)


def hex_to_rgba(hex_color: str, alpha: int) -> str:
    raw = (hex_color or "#000000").lstrip("#")
    if len(raw) == 3:
        raw = "".join(c * 2 for c in raw)
    try:
        # 6 karakter olup hex olmayan degerler ("orange" gibi) ValueError
        # firlatirdi; bir slot icindeki bu hata uygulamayi kapatabilir.
        r, g, b = int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)
    except (ValueError, IndexError):
        r, g, b = 0, 0, 0
    try:
        alpha = int(alpha)
    except (TypeError, ValueError):
        alpha = 140
    return f"rgba({r},{g},{b},{max(0, min(255, alpha))})"


def clamped_int(value, low: int, high: int, default: int) -> int:
    """Ayar dosyasi elle duzenlenebiliyor; bozuk deger cokme sebebi olmamali."""
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


def font_size(settings: dict) -> int:
    return clamped_int(settings.get("font_size", 16), 8, 48, 16)


def font_weight(settings: dict) -> int:
    """Qt stylesheet'i sayisal font-weight'i (100..900) destekliyor."""
    return clamped_int(settings.get("font_weight", 400), 100, 900, 400)


def font_family_css(settings: dict) -> str:
    """font-family CSS'i. Bos ise Qt varsayilan yazi tipine dokunulmaz.

    Aile adi CSS'e gomuldugu icin tirnak ve noktali virgul temizlenir;
    aksi halde bozuk bir config butun stylesheet'i gecersiz kilar.
    """
    family = str(settings.get("font_family") or "").strip()
    family = family.replace('"', "").replace("'", "").replace(";", "").replace("}", "")
    if not family:
        return ""
    return f'font-family: "{family}";'


def font_css(settings: dict) -> str:
    css = font_family_css(settings)
    css += f"font-size: {font_size(settings)}px;"
    css += f"font-weight: {font_weight(settings)};"
    if settings.get("font_italic"):
        css += "font-style: italic;"
    return css


def username_weight(settings: dict) -> int:
    """Kullanici adi metinden bir tik daha kalin, ama en az 600."""
    return max(600, min(900, font_weight(settings) + 200))


def border_width(settings: dict) -> int:
    return clamped_int(settings.get("highlight_border_width", 3), 0, 12, 3)


def mention_border_width(settings: dict) -> int:
    return clamped_int(settings.get("mention_border_width", 3), 0, 12, 3)


def highlight_border_color(settings: dict, username_color: str, badges: list) -> str | None:
    """Vurgulanan mesajin cerceve rengi. None ise cerceve cizilmez.

    Kaynak ayardan gelir: sabit secilen renk, kullanici adi rengi ya da
    rozetten turetilen rol rengi.
    """
    mode = settings.get("highlight_border_mode", "custom")
    fallback = settings.get("highlight_border_color") or "#ff9900"

    if mode == "none":
        return None
    if mode == "username":
        return username_color or fallback
    if mode == "role":
        # rozeti olmayan (orn. isme gore vurgulanan) kullanicida secilen
        # renge duser
        return role_color(badges, fallback)
    return fallback


def build_border_css(color: str | None, width: int, sides: str) -> str:
    """Cerceve CSS'i. color None ise ayni kalinlikta seffaf cerceve
    uretir; boylece vurgulu ve vurgusuz mesajlar ayni hizada durur."""
    css_color = color or "transparent"
    if width <= 0:
        return ""
    if sides == "full":
        return f"border: {width}px solid {css_color};"
    return f"border-left: {width}px solid {css_color};"


def message_border(settings: dict, mentioned: bool, is_highlighted: bool,
                   username_color: str, badges: list) -> tuple:
    """(renk, kalinlik, konum) dondurur; renk None ise seffaf cizilir.

    Etiket cercevesi vurgu cercevesini ezer: mesajda benim adim geciyorsa
    bu, mesaji yazanin rolunden daha onemli.
    """
    hl_w = border_width(settings)
    mention_on = bool(settings.get("mention_border_enabled"))
    mn_w = mention_border_width(settings) if mention_on else 0

    if mentioned and mention_on:
        return (settings.get("mention_border_color") or "#ffd400",
                mn_w, settings.get("mention_border_sides", "left"))

    if is_highlighted:
        color = highlight_border_color(settings, username_color, badges)
        if color:
            return color, hl_w, settings.get("highlight_border_sides", "left")

    # cerceve cizilmiyor: iki modun en genisi kadar yer ayrilir, boylece
    # cerceveli ve cercevesiz mesajlarin metni ayni hizada kalir
    return None, max(hl_w, mn_w), settings.get("highlight_border_sides", "left")


def message_background(settings: dict, mentioned: bool, is_highlighted: bool) -> str:
    """Mesaj arka plani. Etiket arka plani vurgu arka planini ezer."""
    if mentioned and settings.get("mention_bg_enabled"):
        return hex_to_rgba(settings.get("mention_bg_color", "#5a3d00"),
                           settings.get("mention_bg_alpha", 210))
    if is_highlighted and settings.get("highlight_bg_enabled", True):
        return hex_to_rgba(settings.get("highlight_color", "#ff9900"),
                           settings.get("highlight_alpha", 200))
    return hex_to_rgba(settings.get("bg_color", "#000000"),
                       settings.get("bg_darkness", 140))


def render_badges_html(badges, size: int) -> str:
    """Rozetleri <img> etiketlerine cevirir.

    Abone rozeti kanala ozel bir PNG oldugu icin once diske inmis gercek
    gorsel aranir; kanal rozet tanimlamamissa ya da indirme henuz
    bitmediyse gomulu ikona dusulur.
    """
    parts = []
    for badge in normalize_badges(badges):
        src = None
        if badge["type"] == "subscriber":
            path = sub_badges.path_for_months(badge.get("count"))
            if path:
                src = "file:///" + path.replace("\\", "/")
        if src is None:
            src = get_badge_icon_data_uri(badge["type"], size)
        if src:
            parts.append(
                f'<img src="{src}" width="{size}" height="{size}" '
                f'style="vertical-align:middle;margin-right:3px;">'
            )
    return "".join(parts)


def escape_with_mentions(text: str, mention_pattern=None, mention_css: str = "") -> str:
    """Metni escape eder, etiketlere denk gelen parcalari <span> ile boyar.

    Eslesme, katlanmis (tr_fold) bir kopya uzerinde aranir ama goruntulenen
    parca ORIJINAL metinden dilimlenir - boylece kullanicinin yazdigi
    buyuk/kucuk harf ve Turkce I/İ/ı bicimi degismeden kalir. tr_fold()
    harf sayisini degistirmedigi icin (1 karakter -> 1 karakter) katlanmis
    metindeki pozisyonlar orijinaliyle hizali kalir.

    Escape ETMEDEN once eslesme aranir: once escape edilirse "&" gibi
    karakterler "&amp;" olup isim sinirlarini kaydirabilir.
    """
    if not text:
        return ""
    if mention_pattern is None:
        return html.escape(text)
    parts = []
    last = 0
    for m in mention_pattern.finditer(tr_fold(text)):
        parts.append(html.escape(text[last:m.start()]))
        parts.append(f'<span style="{mention_css}">{html.escape(text[m.start():m.end()])}</span>')
        last = m.end()
    parts.append(html.escape(text[last:]))
    return "".join(parts)


def render_content_html(content: str, img_size: int, mention_pattern=None,
                        mention_css: str = "") -> str:
    """Metni HTML-escape eder, [emote:ID:NAME] tokenlarini onceden
    diske inmis gorsellere (bkz. emote_cache) <img> olarak cevirir.

    Etiket araması emote tokenlarinin DISINDA kalan parcalarda yapilir,
    boylece bir emote adi kullanici ismiyle ayni olsa bile bozulmaz.
    """
    content = content or ""
    parts = []
    last_end = 0
    for m in EMOTE_TOKEN_RE.finditer(content):
        parts.append(escape_with_mentions(content[last_end:m.start()],
                                          mention_pattern, mention_css))
        emote_id, name = m.group(1), m.group(2)
        path = emote_path(emote_id)
        if os.path.exists(path):
            uri = "file:///" + path.replace("\\", "/")
            parts.append(f'<img src="{uri}" height="{img_size}" style="vertical-align:middle;">')
        else:
            parts.append(html.escape(f":{name}:"))
        last_end = m.end()
    parts.append(escape_with_mentions(content[last_end:], mention_pattern, mention_css))
    return "".join(parts)


class ChatMessageWidget(QLabel):
    def __init__(self, username: str, content: str, sender_color: str, badges: list,
                 settings: dict, is_highlighted: bool, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setWordWrap(True)
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        size = font_size(settings)
        text_color = settings.get("message_text_color", "#ffffff")
        if settings.get("username_color_mode") == "custom":
            user_color = settings.get("username_color_custom") or "#63f5c2"
        else:
            user_color = sender_color or "#63f5c2"

        pattern = mentions.pattern_for(settings)
        self.mentioned = mentions.contains(content, pattern)

        badge_size = max(size, 14)
        badge_html = render_badges_html(badges, badge_size)

        safe_user = html.escape(username or "???")
        content_html = render_content_html(content, max(size + 4, 18),
                                          pattern, mentions.text_css(settings))

        text = (
            f'{badge_html}'
            f'<span style="color:{user_color};font-weight:{username_weight(settings)};">'
            f'{safe_user}</span>'
            f'<span style="color:{text_color};">: {content_html}</span>'
        )
        self.setText(text)

        # Arka plan ve cerceve bagimsiz: vurgulu mesajda arka plan
        # degistirilmeden sadece cerceve de verilebilir.
        bg = message_background(settings, self.mentioned, is_highlighted)
        border_color, width, sides = message_border(
            settings, self.mentioned, is_highlighted, user_color, badges)
        border_css = build_border_css(border_color, width, sides)

        self.setStyleSheet(
            "QLabel {"
            f"background-color: {bg};"
            f"{border_css}"
            f"{font_css(settings)}"
            "padding: 6px 10px;"
            "border-radius: 8px;"
            "}"
        )
