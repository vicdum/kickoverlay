import base64

from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PyQt6.QtGui import QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer

# Kick'in rozet gorselleri icin stabil bir public URL yok (frontend'de
# vektor olarak gomulu), o yuzden ayni fikri veren basit SVG ikonlar
# elle tanimlandi ve calisma zamaninda PNG'ye render edilip data-uri
# olarak <img> etiketine gomuluyor. Ag baglantisi gerekmez.
BADGE_SVGS = {
    "moderator": """
        <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <path fill="#4ade80" d="M12 2l8 3v6c0 5-3.5 9-8 11-4.5-2-8-6-8-11V5z"/>
        <path d="M8 12l3 3 5-6" stroke="#0b0c0e" stroke-width="2" fill="none"
              stroke-linecap="round" stroke-linejoin="round"/>
        </svg>""",
    "vip": """
        <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <path fill="#c084fc" d="M2 9l5-7h10l5 7-10 13z"/>
        </svg>""",
    "subscriber": """
        <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <path fill="#60a5fa" d="M12 2l3.09 6.26L22 9.27l-5 4.87L18.18 21 12 17.27
              5.82 21 7 14.14l-5-4.87 6.91-1.01z"/>
        </svg>""",
    "sub_gifter": """
        <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <rect x="4" y="9" width="16" height="11" fill="#f472b6"/>
        <rect x="4" y="6" width="16" height="4" fill="#ec4899"/>
        <rect x="11" y="6" width="2" height="14" fill="#fff0f7"/>
        <path fill="#ec4899" d="M8 6c-2 0-2-4 2-4 1 0 2 2 2 4z"/>
        <path fill="#ec4899" d="M16 6c2 0 2-4-2-4-1 0-2 2-2 4z"/>
        </svg>""",
    "broadcaster": """
        <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <rect x="3" y="5" width="18" height="14" rx="3" fill="#f87171"/>
        <path fill="#0b0c0e" d="M10 9l6 3-6 3z"/>
        </svg>""",
    "founder": """
        <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <path fill="#fbbf24" d="M3 18h18l-1.4-9-4.1 3.2L12 6l-3.5 6.2-4.1-3.2z"/>
        <rect x="4" y="19" width="16" height="2" fill="#fbbf24"/>
        </svg>""",
    "og": """
        <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <circle cx="12" cy="12" r="9" fill="none" stroke="#fb923c" stroke-width="3"/>
        <circle cx="12" cy="12" r="4" fill="#fb923c"/>
        </svg>""",
    "verified": """
        <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <circle cx="12" cy="12" r="10" fill="#38bdf8"/>
        <path d="M7 12l3 3 7-7" stroke="#0b0c0e" stroke-width="2.5" fill="none"
              stroke-linecap="round" stroke-linejoin="round"/>
        </svg>""",
    "staff": """
        <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <path fill="#94a3b8" d="M12 2l9 5v10l-9 5-9-5V7z"/>
        <circle cx="12" cy="12" r="3" fill="#17181c"/>
        </svg>""",
}

_cache: dict = {}


def get_badge_icon_data_uri(badge_key: str, size: int = 18) -> str | None:
    cache_key = (badge_key, size)
    if cache_key in _cache:
        return _cache[cache_key]

    svg = BADGE_SVGS.get(badge_key)
    if not svg:
        _cache[cache_key] = None
        return None

    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()

    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    pixmap.save(buf, "PNG")
    b64 = base64.b64encode(bytes(buf.data())).decode("ascii")
    uri = f"data:image/png;base64,{b64}"
    _cache[cache_key] = uri
    return uri
