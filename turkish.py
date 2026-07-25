"""Turkce'ye uygun buyuk/kucuk harf katlama.

Python'un str.lower()/upper() ve re.IGNORECASE, Turkce'nin noktali/noktasiz
"i" ciftini dogru katlamiyor: "I".lower() -> "i" (noktasiz "i" DEGIL) ve
"İ".lower() -> "i̇" (birlesik nokta isaretiyle 2 karakter). Sonuc: kullanici
"İbrahim" yazip kaydeder, sohbette "Ibrahim" gecerse (ya da tersi)
eslesme kurulmaz.

Amac gramatik olarak dogru Turkce cekim degil, guvenilir eslesme oldugu
icin dort "I" varyanti (I, İ, ı, i) tek bir harfe indirilip esitleniyor.
str.translate() harf sayisini degistirmedigi icin (1 karakter -> 1
karakter) sonuc string'deki pozisyonlar orijinaliyle hizali kalir - bu
sayede regex eslesme araligi orijinal metne uygulanabilir.
"""
_I_FOLD = str.maketrans({"İ": "i", "I": "i", "ı": "i", "i": "i"})


def tr_fold(s: str) -> str:
    if not s:
        return s
    return s.translate(_I_FOLD).lower()
