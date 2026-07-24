# Kick Chat Overlay

Kick.com canlı yayın sohbetini oyunların veya masaüstünün üzerinde şeffaf bir katman olarak gösteren Windows masaüstü uygulaması. PyQt6 ile yazıldı, PyInstaller ile tek dosyalık `.exe`'ye derlenir.

## Özellikler

- **Şeffaf overlay** — çerçevesiz, her zaman en üstte, click-through (chat üzerine tıklayınca tıklama arkadaki oyuna geçer)
- **Sürükle-taşı + yeniden boyutlandırma** — "Pencere Konumunu Ayarla" modunda overlay'i istediğin yere taşı, köşeden boyutlandır
- **Gerçek emote görselleri** — Kick emote'ları indirilip diske cache'lenir, mesajda görsel olarak gösterilir
- **Rozet ikonları** — moderatör, VIP, abone, yayıncı, kurucu vb. için özel çizilmiş ikonlar
- **Renk özelleştirme** — kullanıcı adı rengi (Kick rengi ya da özel), mesaj yazı rengi, arka plan rengi/koyulugu
- **Öne çıkarma (highlight)** — seçtiğin kullanıcıların veya rollerin mesajlarını farklı renkte vurgula
- **Mesaj filtreleme** — yasaklı kelimeler, engellenen kullanıcılar, bot mesajları/komutları, abone-bağış bildirimleri ayrı ayrı gizlenebilir
- **Canlı ayar güncelleme** — hiçbir ayar için başlat/durdur gerekmez, hepsi anında uygulanır
- **Sistem tepsisi** — küçültünce tepsiye gizlenir, kapatınca uygulama tamamen çıkar

## Kurulum (son kullanıcı)

Kurulum gerekmez. [**Releases**](https://github.com/vicdum/kickoverlay/releases/latest) sayfasından `KickChatOverlay.exe` dosyasını indirip doğrudan çalıştır.

## Kullanım

1. Uygulamayı aç, ayarlar penceresine Kick kullanıcı adını gir
2. Genel / Görünüm / Öne Çıkanlar / Filtreler sekmelerinden istediğin gibi düzenle
3. **Başlat**'a bas — overlay ekrana gelir, ayarlar penceresi açık kalır
4. Overlay'i konumlandırmak için "Pencere Konumunu Ayarla"yı işaretle, sürükle/boyutlandır, işareti kaldır
5. Ayarlar penceresini simge durumuna küçültürsen sistem tepsisine gizlenir (tray ikonuna çift tıkla geri aç); **X** ile kapatırsan uygulama tamamen çıkar

## Geliştirici Kurulumu

```bash
pip install -r requirements.txt
python main.py
```

## .exe Derleme

```bash
pip install pyinstaller
pyinstaller KickChatOverlay.spec --distpath .
```

`KickChatOverlay.spec`, PyQt6'nın onefile derlemede varsayılan olarak tüm Qt6 klasörünü (Quick/Qml/Multimedia/Pdf gibi kullanılmayan ~40MB'lik parçalar dahil) pakete koymasını önleyip boyutu küçültüyor. Düz `pyinstaller --onefile --noconsole main.py` de çalışır ama çıktı belirgin şekilde daha büyük olur.

## Notlar / Bilinen Sınırlar

- Kick, rozetler için stabil bir public görsel URL sunmuyor (frontend'de vektörel gömülü); rozet ikonları bu yüzden elle çizilmiş SVG'lerden üretiliyor, gerçek Kick rozet görselleri değil.
- Bot tespiti otomatik değil — Kick mesajlarında "bot" rozeti yok. Filtreler sekmesinde bot kullanıcı adlarını elle listeleyip gizleyebilirsin (yaygın botlar önceden ekli).
- Kick API zaman zaman Cloudflare koruması yüzünden 403 dönebilir. Böyle durumda `pip install cloudscraper` kurup `kick_client.py` içindeki `requests.get` çağrısını `cloudscraper.create_scraper().get(...)` ile değiştirmen yeterli.

---

Made with ❤️ by vicdum
