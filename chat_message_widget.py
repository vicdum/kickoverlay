import html
import os
import re

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QImageReader, QMovie, QTextDocument
from PyQt6.QtWidgets import QFrame, QLabel, QSizePolicy, QTextEdit

import mentions
import sub_badges
from badge_icons import get_badge_icon_pixmap, load_scaled_pixmap, normalize_badges, role_color
from emote_cache import EMOTE_TOKEN_RE, emote_path
from turkish import tr_fold

BORDER_MODES = ("none", "custom", "username", "role")
FONT_WEIGHTS = (100, 200, 300, 400, 500, 600, 700, 800, 900)

MESSAGE_V_PADDING = 6
MESSAGE_H_PADDING = 10

# Yaygin emoji Unicode bloklari (yazi tipi karakterleriyle karisma riski
# olmayan semboller/piktogramlar). Duz ok/noktalama bloklari kasti disarida
# birakildi, normal metinde kullanilan ok/tire karakterleri silinmesin.
EMOJI_RE = re.compile(
    "["
    "\U0001F1E6-\U0001F1FF"
    "\U0001F300-\U0001F5FF"
    "\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF"
    "\U0001F700-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FAFF"
    "\U00002600-\U000026FF"
    "\U00002700-\U000027BF"
    "\U00002B00-\U00002BFF"
    "️‍⃣"
    "]+"
)


def strip_emojis(text: str) -> str:
    return EMOJI_RE.sub("", text or "")


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


def render_badges_html(badges, size: int, dpr: float = 1.0) -> tuple:
    """(html, resources) dondurur; resources = [(resource_adi, QPixmap), ...].

    Abone rozeti kanala ozel bir PNG oldugu icin once diske inmis gercek
    gorsel aranir; kanal rozet tanimlamamissa ya da indirme henuz
    bitmediyse gomulu ikona dusulur.

    Rozetler dogrudan file://data URI yerine cagiran tarafin (bkz.
    ChatMessageWidget) document resource olarak kaydedecegi QPixmap'ler
    halinde donuyor - HiDPI ekranlarda net gorunmeleri icin (bkz.
    badge_icons.get_badge_icon_pixmap / load_scaled_pixmap).
    """
    parts = []
    resources = []
    for idx, badge in enumerate(normalize_badges(badges)):
        pixmap = None
        if badge["type"] == "subscriber":
            path = sub_badges.path_for_months(badge.get("count"))
            if path:
                pixmap = load_scaled_pixmap(path, size, size, dpr)
        if pixmap is None:
            pixmap = get_badge_icon_pixmap(badge["type"], size, dpr)
        if pixmap:
            resource_name = f"badge-{idx}-{badge['type']}"
            resources.append((resource_name, pixmap))
            # width/height OZELLIKLE verilmiyor: QTextDocument, HiDPI (dpr>1)
            # isaretli bir QPixmap resource'una acik width/height verilince
            # gorseli olceklemek yerine sol-ust kosesinden kirpiyor (Qt6.11'de
            # dogrulanmis bug/quirk). Attribute olmadan Qt, pixmap'in kendi
            # (dpr'a bolunmus) doal boyutunu kullaniyor - zaten istedigimiz
            # mantiksal boyutla ayni ve kirpilma olmuyor.
            parts.append(
                f'<img src="{resource_name}" '
                f'style="vertical-align:middle;margin-right:3px;">'
            )
    return "".join(parts), resources


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


def emote_render_info(path: str, target_height: int) -> tuple:
    """(animasyonlu_mu, genislik, yukseklik) dondurur.

    GIF/WEBP emote'lerin oynatilip oynatilmayacagini (kare sayisi > 1) ve
    en-boy orani korunmus hedef boyutunu tek QImageReader okumasiyla verir.
    """
    reader = QImageReader(path)
    reader.setDecideFormatFromContent(True)
    animated = reader.imageCount() > 1
    size = reader.size()
    if size.isValid() and size.height() > 0:
        width = max(1, round(target_height * size.width() / size.height()))
    else:
        width = target_height
    return animated, width, target_height


def render_content_html(content: str, img_size: int, mention_pattern=None,
                        mention_css: str = "", block_emotes: bool = False,
                        block_emojis: bool = False, dpr: float = 1.0) -> tuple:
    """Metni HTML-escape eder, [emote:ID:NAME] tokenlarini onceden
    diske inmis gorsellere (bkz. emote_cache) <img> olarak cevirir.

    Etiket araması emote tokenlarinin DISINDA kalan parcalarda yapilir,
    boylece bir emote adi kullanici ismiyle ayni olsa bile bozulmaz.

    block_emotes acikken emote tokenlari (gorsel ya da ":isim:" yedegi)
    tamamen atlanir. block_emojis acikken duz metindeki Unicode emoji
    karakterleri (emote tokenlarinin DISINDaki kisim) silinir.

    (html, animated_emotes, static_images) dondurur:
    - animated_emotes: [(resource_adi, dosya_yolu, genislik, yukseklik), ...]
      Kick emote'lerinin cogu animasyonlu GIF; QTextDocument <img> tek kareyi
      gosterip animasyonu oynatmiyor. Cagiran taraf (ChatMessageWidget) her
      biri icin bir QMovie acip kareler degistikce ayni resource_adi'ni
      guncelleyerek animasyonu saglar.
    - static_images: [(resource_adi, QPixmap), ...] - dogrudan file:// URI
      yerine HiDPI'de net gorunmesi icin onceden olceklenmis QPixmap
      (bkz. badge_icons.load_scaled_pixmap), cagiran taraf document
      resource'u olarak kaydeder.
    """
    content = content or ""
    parts = []
    animated_emotes = []
    static_images = []
    last_end = 0
    for m in EMOTE_TOKEN_RE.finditer(content):
        segment = content[last_end:m.start()]
        if block_emojis:
            segment = strip_emojis(segment)
        parts.append(escape_with_mentions(segment, mention_pattern, mention_css))
        if not block_emotes:
            emote_id, name = m.group(1), m.group(2)
            path = emote_path(emote_id)
            if os.path.exists(path):
                animated, width, height = emote_render_info(path, img_size)
                resource_name = f"emote-{emote_id}"
                # width/height verilmiyor - bkz. render_badges_html'deki not:
                # DPR isaretli pixmap + acik width/height Qt'de kirpilmaya yol aciyor.
                parts.append(
                    f'<img src="{resource_name}" '
                    f'style="vertical-align:middle;">'
                )
                if animated:
                    animated_emotes.append((resource_name, path, width, height))
                else:
                    pixmap = load_scaled_pixmap(path, width, height, dpr)
                    if pixmap:
                        static_images.append((resource_name, pixmap))
            else:
                parts.append(html.escape(f":{name}:"))
        last_end = m.end()
    tail = content[last_end:]
    if block_emojis:
        tail = strip_emojis(tail)
    parts.append(escape_with_mentions(tail, mention_pattern, mention_css))
    return "".join(parts), animated_emotes, static_images


class ChatMessageWidget(QTextEdit):
    def __init__(self, username: str, content: str, sender_color: str, badges: list,
                 settings: dict, is_highlighted: bool, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # QTextEdit viewport'u varsayilan olarak kendi palet rengini boyar;
        # bu kapatilmazsa asagidaki QSS background-color'u viewport'un
        # altinda kalir ve gorunmez.
        self.viewport().setAutoFillBackground(False)

        size = font_size(settings)
        text_color = settings.get("message_text_color", "#ffffff")
        if settings.get("username_color_mode") == "custom":
            user_color = settings.get("username_color_custom") or "#63f5c2"
        else:
            user_color = sender_color or "#63f5c2"

        pattern = mentions.pattern_for(settings)
        self.mentioned = mentions.contains(content, pattern)

        # HiDPI ekranlarda (%125/%150/%200 Windows olcekleme) mantiksal
        # boyutta rasterize edilen rozet/emote gorselleri bulanik/dusuk
        # cozunurluklu gorunuyordu; fiziksel piksel sayisi bu oranla
        # carpilip pixmap'e isaretleniyor (bkz. badge_icons).
        self._dpr = self.devicePixelRatioF() or 1.0

        badge_size = max(size, 14)
        badge_html, badge_resources = render_badges_html(badges, badge_size, self._dpr)

        safe_user = html.escape(username or "???")
        content_html, animated_emotes, static_images = render_content_html(
            content, max(size + 4, 18), pattern, mentions.text_css(settings),
            block_emotes=settings.get("block_emotes", False),
            block_emojis=settings.get("block_emojis", False),
            dpr=self._dpr,
        )

        # Mesaj SADECE engellenen bir emote/emoji'den olusuyorsa content_html
        # icin gorsel de metin de kalmaz - cagiran taraf (bkz. overlay_window.
        # add_message) bu bayragi gorup bos baloncuk eklemeden atlar.
        visible_text = re.sub(r"<[^>]+>", "", content_html).strip()
        self.content_is_empty = not (animated_emotes or static_images or visible_text)

        text = (
            f'{badge_html}'
            f'<span style="color:{user_color};font-weight:{username_weight(settings)};">'
            f'{safe_user}</span>'
            f'<span style="color:{text_color};">: {content_html}</span>'
        )

        # Butun gorsel resource'lar HTML islenmeden ONCE kaydedilir - aksi
        # halde setHtml() sirasinda kaynagi bulunamayan <img> bir an icin
        # kirik gorunur.
        for resource_name, pixmap in badge_resources:
            self.document().addResource(
                QTextDocument.ResourceType.ImageResource, QUrl(resource_name), pixmap)
        for resource_name, pixmap in static_images:
            self.document().addResource(
                QTextDocument.ResourceType.ImageResource, QUrl(resource_name), pixmap)

        self._movies = []
        for resource_name, path, w, h in animated_emotes:
            movie = QMovie(path, parent=self)
            key = QUrl(resource_name)
            movie.jumpToFrame(0)
            self._register_movie_frame(movie, key, w, h)
            movie.frameChanged.connect(
                lambda _frame, m=movie, k=key, w=w, h=h: self._register_movie_frame(m, k, w, h))
            movie.start()
            self._movies.append(movie)

        self.setHtml(text)

        # Arka plan ve cerceve bagimsiz: vurgulu mesajda arka plan
        # degistirilmeden sadece cerceve de verilebilir.
        bg = message_background(settings, self.mentioned, is_highlighted)
        border_color, width, sides = message_border(
            settings, self.mentioned, is_highlighted, user_color, badges)
        border_css = build_border_css(border_color, width, sides)

        self.setStyleSheet(
            "QTextEdit {"
            f"background-color: {bg};"
            f"{border_css}"
            f"{font_css(settings)}"
            f"padding: {MESSAGE_V_PADDING}px {MESSAGE_H_PADDING}px;"
            "border-radius: 8px;"
            "}"
        )
        # Dikey boyuta yansiyan CSS kutu modeli: ust+alt padding, ve
        # "full" cerceve secildiyse ust+alt kalinlik da yukseklige eklenir
        # ("left" cercevede yukseklik etkilenmez).
        self._vertical_extra = 2 * MESSAGE_V_PADDING + (2 * width if sides == "full" else 0)
        self._sync_height()

    def _register_movie_frame(self, movie: QMovie, key: QUrl, w: int, h: int):
        """QMovie'nin dogal cozunurluklu karesini hedef mantiksal boyuta
        yumusak (smooth) olcekleyip HiDPI icin isaretler.

        QMovie.setScaledSize kullanmiyoruz cunku Qt bunu iceride hizli
        (nearest-neighbor benzeri) olcekliyor ve dpr'den habersiz - ikisi
        de kucuk boyutta pikselli/dusuk cozunurluklu gorunmeye yol aciyordu.
        """
        frame = movie.currentPixmap()
        physical_w = max(1, round(w * self._dpr))
        physical_h = max(1, round(h * self._dpr))
        scaled = frame.scaled(
            physical_w, physical_h,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        scaled.setDevicePixelRatio(self._dpr)
        self.document().addResource(QTextDocument.ResourceType.ImageResource, key, scaled)
        self.document().markContentsDirty(0, self.document().characterCount())

    def _sync_height(self):
        height = int(self.document().size().height()) + getattr(self, "_vertical_extra", 0)
        self.setFixedHeight(max(1, height))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.document().setTextWidth(self.viewport().width())
        self._sync_height()


EVENT_COLORS = {
    "subscription": "#a970ff",
    "gifted_subs": "#ff66c4",
    "kicks": "#53FC18",
    "ban": "#ff4d4d",
    "unban": "#53FC18",
    "timeout": "#ff9900",
}


class EventMessageWidget(QLabel):
    """Abonelik/hediye/kicks/ban gibi sohbet-disi Kick etkinlikleri icin
    sade bildirim satiri - emote/mention/animasyon gerekmedigi icin normal
    ChatMessageWidget yerine duz bir QLabel yeterli."""

    def __init__(self, text: str, kind: str, settings: dict, parent=None):
        super().__init__(parent)
        self.setWordWrap(True)
        self.setTextFormat(Qt.TextFormat.RichText)

        color = EVENT_COLORS.get(kind, "#e8e8ea")
        self.setText(f'<span style="color:{color};font-weight:600;">{html.escape(text)}</span>')

        bg = hex_to_rgba(settings.get("bg_color", "#000000"), settings.get("bg_darkness", 140))
        self.setStyleSheet(
            "QLabel {"
            f"background-color: {bg};"
            f"border-left: 3px solid {color};"
            f"{font_css(settings)}"
            f"padding: {MESSAGE_V_PADDING}px {MESSAGE_H_PADDING}px;"
            "border-radius: 8px;"
            "}"
        )
