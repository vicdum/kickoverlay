"""Sohbet metninde gecen isimleri (etiketleri) bulur.

"One Cikanlar" sekmesindeki vurgulamadan farkli: orada mesaji YAZAN kisiye
bakilir, burada mesajin ICERIGINE. Kick'te etiketler "@ad" seklinde gecer
ama kullanicilar '@' koymadan da yaziyor, o yuzden ikisi de yakalanir.
"""
import re

from logger import get_logger
from turkish import tr_fold

log = get_logger("mentions")

# Derlenen regex onbellegi: her mesaj icin yeniden derlemek gereksiz,
# isim listesi degismedigi surece ayni desen kullanilir.
_cache_key = None
_cache_pattern = None


def compile_names(names) -> "re.Pattern | None":
    """Isim listesinden tek bir regex uretir. Liste bossa None doner.

    Desen tr_fold() ile katlanmis (kucuk harf, I/İ/ı tek harfe indirilmis)
    isimlerden kurulur; re.IGNORECASE KULLANILMAZ çünkü Python'un kendi
    katlamasi Turkce "I" harfini yanlis katlayip eslesmeyi kaçırır - bunun
    yerine aranan metin de tr_fold() ile katlanip bu desene karsi calisir
    (bkz. contains/escape_with_mentions).
    """
    global _cache_key, _cache_pattern
    try:
        cleaned = tuple(sorted({
            tr_fold(str(n).strip()) for n in (names or []) if str(n).strip()
        }))
    except Exception as exc:
        log.warning("etiket isim listesi okunamadi: %s", exc)
        return None
    if not cleaned:
        return None
    if cleaned == _cache_key:
        return _cache_pattern

    # Uzun isim once denenir: "ali" ve "aliveli" birlikte varsa daha uzun
    # olan eslesmeli, yoksa "aliveli" icinde sadece "ali" boyanir.
    alts = "|".join(re.escape(n) for n in sorted(cleaned, key=len, reverse=True))
    # (?<![\w@]) kelime ici ("veliali") ve "x@ali" gibi eslesmeleri engeller,
    # (?!\w) sondan ("ali_veli") engeller. @ isaretli hali de eslesir ve
    # boyamaya dahil olur.
    try:
        pattern = re.compile(rf"(?<![\w@])@?(?:{alts})(?!\w)")
    except re.error as exc:
        log.error("etiket deseni derlenemedi: %s", exc)
        return None

    _cache_key = cleaned
    _cache_pattern = pattern
    return pattern


def pattern_for(settings: dict) -> "re.Pattern | None":
    """Ayarlardan aktif etiket desenini uretir; kapaliysa None."""
    if not settings.get("mention_enabled", True):
        return None
    return compile_names(settings.get("mention_names"))


def contains(text: str, pattern) -> bool:
    if pattern is None or not text:
        return False
    return pattern.search(tr_fold(text)) is not None


def text_css(settings: dict) -> str:
    """Etiketin kendisine uygulanacak inline CSS."""
    color = settings.get("mention_color") or "#ffd400"
    css = f"color:{color};"
    if settings.get("mention_bold", True):
        css += "font-weight:800;"
    return css
