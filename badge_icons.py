import base64

from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PyQt6.QtGui import QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer

import sub_badges

# Kimlik rozetleri (moderator/VIP/kurucu...) Kick frontend'inde vektor
# olarak gomulu; asagidakiler o SVG'lerin birebir kopyasi. Kick ayni
# path'i ust uste 2-3 kez farkli gradyanla ciziyor (tema varyantlari) -
# SVG'de en son cizilen opak katman digerlerini tamamen kapattigi icin
# sadece gorunen katman burada tutuldu, sonuc ayni ama dosya kucuk.
#
# broadcaster/staff/verified/sub_gifter icin orijinal SVG elde
# olmadigindan bunlar hala elle cizilmis yaklastirmalar.
#
# Abone rozeti kanala ozel bir PNG oldugu icin burada yok; bkz.
# sub_badges. Asagidaki "subscriber" ikonu sadece kanal rozet
# tanimlamamissa ya da gorsel henuz inmemisse kullanilan yedek.
BADGE_SVGS = {
    # gercek Kick rozeti - mavi gradyanli tokmak
    "moderator": """
        <svg viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg">
        <defs><linearGradient id="mod" x1="-14.9543" y1="46.9544" x2="32.0001" y2="0"
              gradientUnits="userSpaceOnUse">
        <stop stop-color="#0095FF"/><stop offset="0.99" stop-color="#00C7FF"/>
        </linearGradient></defs>
        <path fill="url(#mod)" d="M30 0C31.1046 0 32 0.895431 32 2V30C32 31.1046 31.1046 32
              30 32H2C0.895431 32 0 31.1046 0 30V2C0 0.895431 0.895431 0 2 0H30ZM16.2197
              2.99316C15.8292 2.60266 15.1962 2.60265 14.8057 2.99316L8.36328 9.43555C7.97294
              9.82608 7.97284 10.4591 8.36328 10.8496L10.0918 12.5781C10.4823 12.9686 11.1153
              12.9685 11.5059 12.5781L11.585 12.499L13.9414 14.8564L3.57129 25.2275C2.70357
              26.0954 2.7035 27.5023 3.57129 28.3701C4.43911 29.2376 5.84612 29.2377 6.71387
              28.3701L17.084 17.999L19.4414 20.3564L19.3633 20.4346C18.9728 20.8251 18.9728
              21.4581 19.3633 21.8486L21.0918 23.5771C21.4823 23.9676 22.1154 23.9676 22.5059
              23.5771L28.9482 17.1348C29.3386 16.7443 29.3386 16.1112 28.9482 15.7207L27.2197
              13.9922C26.8293 13.6017 26.1962 13.6018 25.8057 13.9922L25.7266 14.0703L23.3701
              11.7139C24.2377 10.8461 24.2376 9.4391 23.3701 8.57129C22.5023 7.7035 21.0954
              7.70357 20.2275 8.57129L17.8701 6.21387L17.9482 6.13574C18.3388 5.74522 18.3388
              5.11221 17.9482 4.72168L16.2197 2.99316Z"/>
        </svg>""",
    # gercek Kick rozeti - altin gradyanli tac/yildiz
    "vip": """
        <svg viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg">
        <defs><linearGradient id="vip" x1="15.7467" y1="-4.75575" x2="16.321" y2="39.0672"
              gradientUnits="userSpaceOnUse">
        <stop stop-color="#FFC900"/><stop offset="0.99" stop-color="#FF9500"/>
        </linearGradient></defs>
        <path fill="url(#vip)" d="M30 0C31.1046 0 32 0.895431 32 2V30C32 31.1046 31.1046 32
              30 32H2C0.895431 32 0 31.1046 0 30V2C0 0.895431 0.895431 0 2 0H30ZM15.9648
              5C15.7748 5.00005 15.588 5.05204 15.4238 5.15039C15.2596 5.24878 15.124 5.39057
              15.0303 5.56055L9.82812 15.0176L3.55078 11.8906C3.36913 11.7985 3.16534 11.7607
              2.96387 11.7822C2.76241 11.8038 2.57048 11.8842 2.41113 12.0127C2.25235 12.1408
              2.13185 12.3126 2.06348 12.5078C1.99511 12.7031 1.98143 12.9144 2.02441
              13.1172L4.58301 25.127C4.63544 25.3782 4.77165 25.6034 4.96777 25.7627C5.16376
              25.9217 5.40762 26.0056 5.65723 26H26.251C26.5009 26.0057 26.7453 25.9219 26.9414
              25.7627C27.1376 25.6034 27.2737 25.3782 27.3262 25.127L29.9697 13.1172C30.0187
              12.9103 30.0086 12.6932 29.9404 12.4922C29.8722 12.2912 29.7485 12.1151 29.585
              11.9844C29.4215 11.8537 29.2249 11.7743 29.0186 11.7559C28.8122 11.7374 28.6049
              11.7802 28.4219 11.8799L22.1025 15.0283L16.9004 5.56055C16.8066 5.39054 16.6701
              5.24878 16.5059 5.15039C16.3416 5.05207 16.1549 5 15.9648 5Z"/>
        </svg>""",
    # gercek Kick rozeti - altin madalyon
    "founder": """
        <svg viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg">
        <defs>
        <linearGradient id="ring" x1="15.7467" y1="-4.46667" x2="16.2533" y2="36.6933"
              gradientUnits="userSpaceOnUse">
        <stop stop-color="#FFC900"/><stop offset="0.99" stop-color="#FF9500"/></linearGradient>
        <linearGradient id="gloss" x1="16" y1="0" x2="16" y2="32" gradientUnits="userSpaceOnUse">
        <stop stop-color="white" stop-opacity="0.3"/>
        <stop offset="1" stop-color="white" stop-opacity="0.15"/></linearGradient>
        <linearGradient id="core" x1="15.7936" y1="-0.677142" x2="16.2064" y2="32.8618"
              gradientUnits="userSpaceOnUse">
        <stop stop-color="#FFC900"/><stop offset="0.99" stop-color="#FF9500"/></linearGradient>
        </defs>
        <path fill="url(#ring)" d="M16 32C24.8366 32 32 24.8366 32 16C32 7.16344 24.8366 0 16
              0C7.16344 0 0 7.16344 0 16C0 24.8366 7.16344 32 16 32Z"/>
        <path fill="url(#gloss)" d="M16 32C24.8366 32 32 24.8366 32 16C32 7.16344 24.8366 0 16
              0C7.16344 0 0 7.16344 0 16C0 24.8366 7.16344 32 16 32Z"/>
        <path fill="url(#core)" d="M16 29.0375C23.2004 29.0375 29.0375 23.2004 29.0375
              16C29.0375 8.79958 23.2004 2.96249 16 2.96249C8.79959 2.96249 2.9625 8.79958
              2.9625 16C2.9625 23.2004 8.79959 29.0375 16 29.0375Z"/>
        <path fill="black" fill-opacity="0.05" d="M29.0375 16C29.0375 23.1875 23.1875 29.0375 16
              29.0375C13.6563 29.0375 11.4625 28.4187 9.5625 27.3312C11.3125 28.2062 13.2875
              28.7 15.375 28.7C22.5625 28.7 28.4125 22.85 28.4125 15.6625C28.4125 10.8188 25.75
              6.58125 21.8125 4.3375C26.0938 6.475 29.0375 10.8938 29.0375 16ZM16.8875
              3.575C19.4563 3.575 21.85 4.325 23.8625 5.60625C21.675 3.95625 18.95 2.96875 16
              2.96875C8.8125 2.96875 2.9625 8.8125 2.9625 16.0063C2.9625 20.6437 5.4 24.7313
              9.0625 27.0312C5.9 24.65 3.85 20.8687 3.85 16.6125C3.85 9.425 9.7 3.575 16.8875
              3.575Z"/>
        <path fill="black" fill-opacity="0.8" d="M18.5966 9.45456V24H14.6477V13.0909H14.5625L11.3807
              14.9943V11.6421L14.9602 9.45456H18.5966Z"/>
        </svg>""",
    "broadcaster": """
        <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <rect x="3" y="5" width="18" height="14" rx="3" fill="#f87171"/>
        <path fill="#0b0c0e" d="M10 9l6 3-6 3z"/>
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
    # gercek Kick rozeti - cyan/lacivert gradyanli "OG" harfleri
    "og": """
        <svg viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg">
        <defs>
        <linearGradient id="og1" x1="23.9622" y1="0.695162" x2="24.4274" y2="31.9986"
              gradientUnits="userSpaceOnUse">
        <stop stop-color="#00FFF2"/><stop offset="1" stop-color="#006399"/></linearGradient>
        <linearGradient id="og2" x1="7.77104" y1="0" x2="7.91062" y2="32.567"
              gradientUnits="userSpaceOnUse">
        <stop stop-color="#00FFF2"/><stop offset="1" stop-color="#006399"/></linearGradient>
        </defs>
        <path fill="url(#og1)" d="M22.8226 17.2693V28.0037C22.8226 28.2177 22.8929 28.383
              23.0336 28.4996C23.1742 28.5969 23.3969 28.6455 23.7017 28.6455H24.5104V32H21.838C19.9627
              32 18.6265 31.6694 17.8294 31.0082C17.0559 30.347 16.6691 29.472 16.6691
              28.383V16.8901C16.6691 15.8011 17.0559 14.926 17.8294 14.2648C18.6265 13.6036 19.9627
              13.273 21.838 13.273H24.6511V16.6276H23.7017C23.3969 16.6276 23.1742 16.6859 23.0336
              16.8026C22.8929 16.8998 22.8226 17.0554 22.8226 17.2693ZM32.0002 21.6447V24.8826H24.0885V21.6447H32.0002ZM25.8466
              19.6904V17.2693C25.8466 17.0554 25.7763 16.8998 25.6357 16.8026C25.495 16.6859 25.2723
              16.6276 24.9676 16.6276H24.0182V13.273H26.8312C28.7066 13.273 30.031 13.6036 30.8046
              14.2648C31.6017 14.926 32.0002 15.8011 32.0002 16.8901V19.6904H25.8466ZM25.8466
              28.0037V23.8908H32.0002V28.383C32.0002 29.472 31.6017 30.347 30.8046 31.0082C30.031
              31.6694 28.7066 32 26.8312 32H24.1588V28.6455H24.9676C25.2723 28.6455 25.495 28.5969
              25.6357 28.4996C25.7763 28.383 25.8466 28.2177 25.8466 28.0037Z"/>
        <path fill="#00FFF2" d="M22.8228 3.99625V14.7307C22.8228 14.9446 22.8931 15.1099
              23.0338 15.2266C23.1744 15.3238 23.3971 15.3724 23.7019 15.3724H24.5106V18.727H21.8382C19.9629
              18.727 18.6267 18.3964 17.8296 17.7352C17.056 17.074 16.6693 16.1989 16.6693
              15.1099V3.61704C16.6693 2.52804 17.056 1.65295 17.8296 0.99177C18.6267 0.33059 19.9629
              0 21.8382 0H24.6513V3.35452H23.7019C23.3971 3.35452 23.1744 3.41286 23.0338
              3.52953C22.8931 3.62677 22.8228 3.78234 22.8228 3.99625ZM32.0004 8.37171V11.6095H24.0887V8.37171H32.0004ZM25.8468
              6.41734V3.99625C25.8468 3.78234 25.7765 3.62677 25.6358 3.52953C25.4952 3.41286
              25.2725 3.35452 24.9677 3.35452H24.0183V0H26.8314C28.7067 0 30.0312 0.33059 30.8048
              0.99177C31.6018 1.65295 32.0004 2.52804 32.0004 3.61704V6.41734H25.8468ZM25.8468
              14.7307V10.6178H32.0004V15.1099C32.0004 16.1989 31.6018 17.074 30.8048 17.7352C30.0312
              18.3964 28.7067 18.727 26.8314 18.727H24.159V15.3724H24.9677C25.2725 15.3724 25.4952
              15.3238 25.6358 15.2266C25.7765 15.1099 25.8468 14.9446 25.8468 14.7307Z"/>
        <path fill="url(#og2)" d="M9.38855 7.81748V4.28795C9.38855 4.07404 9.31822 3.91846
              9.17757 3.82123C9.03691 3.70455 8.81421 3.64621 8.50947 3.64621H7.34909V0H10.3731C12.2485
              0 13.573 0.33059 14.3465 0.99177C15.1436 1.65295 15.5421 2.52804 15.5421
              3.61704V7.81748H9.38855ZM9.38855 14.439V7.43828H15.5421V15.1099C15.5421 16.1989 15.1436
              17.074 14.3465 17.7352C13.573 18.3964 12.2485 18.727 10.3731 18.727H7.34909V15.0807H8.50947C8.81421
              15.0807 9.03691 15.0321 9.17757 14.9349C9.31822 14.8182 9.38855 14.6529 9.38855
              14.439ZM6.15354 4.28795V7.81748H0V3.61704C0 2.52804 0.386794 1.65295 1.16038
              0.99177C1.95741 0.33059 3.29361 0 5.16897 0H8.193V3.64621H7.03262C6.72787 3.64621
              6.50517 3.70455 6.36452 3.82123C6.22387 3.91846 6.15354 4.07404 6.15354
              4.28795ZM6.15354 7.43828V14.439C6.15354 14.6529 6.22387 14.8182 6.36452 14.9349C6.50517
              15.0321 6.72787 15.0807 7.03262 15.0807H8.193V18.727H5.16897C3.29361 18.727 1.95741
              18.3964 1.16038 17.7352C0.386794 17.074 0 16.1989 0 15.1099V7.43828H6.15354Z"/>
        <path fill="#00FFF2" d="M9.38839 21.0905V17.561C9.38839 17.3471 9.31807 17.1915
              9.17741 17.0943C9.03676 16.9776 8.81406 16.9193 8.50932 16.9193H7.34893V13.273H10.373C12.2483
              13.273 13.5728 13.6036 14.3464 14.2648C15.1434 14.926 15.5419 15.8011 15.5419
              16.8901V21.0905H9.38839ZM9.38839 27.712V20.7113H15.5419V28.383C15.5419 29.472 15.1434
              30.347 14.3464 31.0082C13.5728 31.6694 12.2483 32 10.373 32H7.34893V28.3538H8.50932C8.81406
              28.3538 9.03676 28.3052 9.17741 28.2079C9.31807 28.0913 9.38839 27.926 9.38839
              27.712ZM6.15339 17.561V21.0905H-0.000152588V16.8901C-0.000152588 15.8011 0.386641
              14.926 1.16023 14.2648C1.95726 13.6036 3.29346 13.273 5.16882 13.273H8.19285V16.9193H7.03247C6.72772
              16.9193 6.50502 16.9776 6.36437 17.0943C6.22371 17.1915 6.15339 17.3471 6.15339
              17.561ZM6.15339 20.7113V27.712C6.15339 27.926 6.22371 28.0913 6.36437 28.2079C6.50502
              28.3052 6.72772 28.3538 7.03247 28.3538H8.19285V32H5.16882C3.29346 32 1.95726 31.6694
              1.16023 31.0082C0.386641 30.347 -0.000152588 29.472 -0.000152588 28.383V20.7113H6.15339Z"/>
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

# Rol renkleri rozet gorsellerindeki baskin renkle ayni tutuluyor: "rol
# rengine gore cerceve" secildiginde cerceve, mesajda gorunen rozetle
# ayni renkte olur. Abone rozeti kanala ozel oldugu icin buradaki deger
# sadece yedek; gercek renk gorselden okunur (sub_badges.dominant_color).
ROLE_COLORS = {
    "broadcaster": "#f87171",
    "moderator": "#00a9ff",
    "vip": "#ffc900",
    "subscriber": "#60a5fa",
    "sub_gifter": "#ec4899",
    "founder": "#feb635",
    "og": "#fb923c",
    "verified": "#38bdf8",
    "staff": "#94a3b8",
}

# Bir mesajda birden fazla rozet olabilir (orn. mod + abone); cerceve
# icin listede once gelen rol kazanir.
ROLE_PRIORITY = [
    "broadcaster", "staff", "moderator", "founder", "vip",
    "og", "verified", "sub_gifter", "subscriber",
]


def normalize_badges(badges) -> list[dict]:
    """Rozet listesini {"type":..., "count":...} sozluklerine cevirir.

    Kick ChatMessageEvent icinde rozetler sozluk gelir (abone rozetinde
    ay sayisi "count" alaninda). Duz string listesi de kabul edilir.
    """
    out = []
    for item in badges or []:
        if isinstance(item, dict):
            out.append({"type": str(item.get("type") or ""), "count": item.get("count")})
        elif item:
            out.append({"type": str(item), "count": None})
    return out


def badge_types(badges) -> list[str]:
    return [b["type"] for b in normalize_badges(badges) if b["type"]]


def role_color(badges, default: str | None = None) -> str | None:
    """Rozet listesindeki en belirleyici rolun rengini dondurur."""
    items = normalize_badges(badges)
    present = {b["type"]: b for b in items}
    for key in ROLE_PRIORITY:
        if key not in present:
            continue
        if key == "subscriber":
            path = sub_badges.path_for_months(present[key].get("count"))
            if path:
                sampled = sub_badges.dominant_color(path)
                if sampled:
                    return sampled
        return ROLE_COLORS[key]
    return default


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
