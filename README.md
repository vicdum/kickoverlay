# Kick Chat Overlay

Kick.com canlı yayın sohbetini oyunların veya masaüstünün üzerinde şeffaf bir katman olarak gösteren Windows masaüstü uygulaması. PyQt6 ile yazıldı, PyInstaller ile tek dosyalık `.exe`'ye derlenir.

## Özellikler

- **Şeffaf overlay** — çerçevesiz, her zaman en üstte, click-through (chat üzerine tıklayınca tıklama arkadaki oyuna geçer)
- **Sürükle-taşı + yeniden boyutlandırma** — "Pencere Konumunu Ayarla" modunda overlay'i istediğin yere taşı, köşeden boyutlandır
- **Gerçek emote görselleri** — Kick emote'ları indirilip diske cache'lenir, mesajda görsel olarak gösterilir
- **Gerçek Kick rozetleri** — moderatör/VIP/kurucu/OG rozetleri Kick'in kendi vektörel ikonları; abone rozetleri kanalın kendi yüklediği görsellerden, abonelik ayına göre doğru kademe seçilerek indirilip cache'lenir
- **Renk özelleştirme** — kullanıcı adı rengi (Kick rengi ya da özel), mesaj yazı rengi, arka plan rengi/koyulugu
- **Yazı tipi** — sistemde kurulu fontlardan seçim, boyut, 100–900 arası kalınlık ve italik; ayarlar penceresinde canlı ön izleme
- **Etiket vurgulama (mention)** — kendi adın (ya da takip ettiğin isimler) sohbette geçtiğinde etiket renkli/kalın gösterilir; istersen mesajın arka planını boyar, çerçeve çizer ve `.wav` bildirim sesi çalar
- **Öne çıkarma (highlight)** — seçtiğin kullanıcıların veya rollerin mesajlarını vurgula; arka plan boyama ve mesaj çerçevesi birbirinden bağımsız açılıp kapatılabilir
- **Mesaj çerçevesi** — çerçeve rengi sabit seçtiğin renk, kullanıcı adı rengi ya da rol rengi (mod mavi, VIP altın, yayıncı kırmızı — rozetle aynı) olabilir; kalınlık ve sol kenar / tam çerçeve seçilebilir
- **Mesaj filtreleme** — yasaklı kelimeler, engellenen kullanıcılar, bot mesajları/komutları, abone-bağış bildirimleri ayrı ayrı gizlenebilir
- **Silinen mesaj senkronu (opsiyonel)** — istersen moderasyonla silinen mesajlar overlay'den de otomatik kaldırılır
- **Canlı ayar güncelleme** — hiçbir ayar için başlat/durdur gerekmez, hepsi anında uygulanır
- **Sistem tepsisi** — küçültünce tepsiye gizlenir, kapatınca uygulama tamamen çıkar
- **Log kaydı** — beklenmedik kapanmaların sebebi diske yazılır (aşağıdaki "Sorun giderme")

## Kurulum (son kullanıcı)

Kurulum gerekmez. [**Releases**](https://github.com/vicdum/kickoverlay/releases/latest) sayfasından indir:

- **`KickChatOverlay-portable.zip`** (önerilen) — indir, zip'i çıkar, klasördeki `KickChatOverlay.exe`'yi çalıştır.
- **`KickChatOverlay.exe`** (tek dosya) — daha pratik ama antivirüs yanlış-pozitif riski biraz daha yüksek (aşağıya bak).

### Antivirüs "virüs" uyarısı veriyor, ne yapmalıyım?

Bu uygulama kod imzası (code signing sertifikası) içermiyor — ücretli, kimlik doğrulama gerektiren bir sertifika satın almadan bunu tamamen ortadan kaldırmak mümkün değil. Ayrıca overlay'in fare tıklamasını geçirme özelliği Windows'un düşük seviye pencere API'lerini (`SetWindowLongW`, `WS_EX_TRANSPARENT`) kullanır — bu, ekran katmanı oluşturan meşru araçlarla (ve bazı kötü amaçlı yazılımlarla) aynı davranış olduğu için bazı antivirüs yazılımları temkinli davranıp yanlış pozitif verebilir. Tek dosyalık (`--onefile`) derlemeler, çalışırken kendini geçici klasöre açtığı için bu konuda ekstra dikkat çeker; `KickChatOverlay-portable.zip` bunu yapmaz, o yüzden önerilen indirme budur.

Eğer engellenirsen:
1. Windows Defender / SmartScreen "Daha fazla bilgi" → "Yine de çalıştır" diyerek devam edebilirsin.
2. Dosyanın bozulmadığını doğrulamak için SHA256 karma değerini kontrol et (her sürümün Release notlarında yayınlanır).
3. Antivirüs yazılımın dosyayı silmişse, [VirusTotal](https://www.virustotal.com/) üzerinden tarayıp hangi motorun ne dediğine bakabilirsin; gerçek zararlı davranış (ağ trafiği, disk yazımı vb.) yok, kaynak kod bu depoda açık.

## Kullanım

1. Uygulamayı aç, ayarlar penceresine Kick kullanıcı adını gir
2. Genel / Görünüm / Öne Çıkanlar / Etiket / Filtreler sekmelerinden istediğin gibi düzenle
3. **Başlat**'a bas — overlay ekrana gelir, ayarlar penceresi açık kalır
4. Overlay'i konumlandırmak için "Pencere Konumunu Ayarla"yı işaretle, sürükle/boyutlandır, işareti kaldır
5. Ayarlar penceresini simge durumuna küçültürsen sistem tepsisine gizlenir (tray ikonuna çift tıkla geri aç); **X** ile kapatırsan uygulama tamamen çıkar

## Vurgu Stili (Öne Çıkanlar sekmesi)

Kimlerin vurgulanacağını seçtikten sonra (kullanıcı adı ve/veya rol) vurgunun **nasıl** görüneceği iki bağımsız parçadan oluşur:

**Arka planı vurgu rengiyle boya** — kapatırsan vurgulanan mesajın arka planı diğerleriyle aynı kalır, sadece çerçeve ile ayırt edilir.

**Çerçeve** dört seçenek:

| Seçenek | Çerçeve rengi |
|---|---|
| Yok | Çerçeve çizilmez |
| Seçilen Renk | Altındaki renk kutusundan seçtiğin sabit renk |
| Kullanıcı Adı Rengi | Kullanıcının Kick'teki kendi rengi |
| Rol Rengi | Rozetten türetilir: yayıncı kırmızı, mod mavi, VIP/kurucu altın… Mesajda görünen rozetle aynı renk. Abone rozeti kanala özel olduğu için rengi doğrudan o kanalın rozet görselinden örneklenir. Rozeti olmayan (isme göre vurgulanan) kullanıcıda "Seçilen Renk"e düşer. |

Birden fazla rozet varsa en belirleyici rol kazanır (yayıncı > Kick ekibi > moderatör > kurucu > VIP > OG > onaylı > hediye eden > abone).

**Kalınlık** 0–12 px, **Konum** sol kenar çubuğu ya da tam çerçeve. Vurgulanmayan mesajlar da aynı kalınlıkta şeffaf çerçeve alır, böylece metinler hizada kalır.

## Etiket Vurgulama (Etiket sekmesi)

"Öne Çıkanlar" mesajı **yazan** kişiye bakar; Etiket sekmesi mesajın **içeriğine** bakar. **İsimler** alanına kendi adını (ve istersen takma adlarını) virgülle ayırıp yaz — `@` koymana gerek yok.

Eşleşme kuralları:

- `@ad` ve düz `ad` yazımı ikisi de yakalanır, büyük/küçük harf önemsiz
- Türkçe karakter desteği var: `İbrahim`, `Ibrahim`, `ibrahim` ve `IBRAHIM` hepsi aynı isim sayılır (Python'un varsayılan büyük/küçük harf dönüşümü Türkçe noktalı/noktasız "I" çiftini doğru katlamıyor, bu yüzden özel bir eşitleme kullanılıyor — bkz. `turkish.py`). Diğer Türkçe harfler (ş, ğ, ü, ö, ç) zaten sorunsuz.
- Kelime içinde eşleşmez: isim `ali` ise `aliveli` veya `ali_2` tetiklemez
- `x@ali` gibi e-posta benzeri yazımlar tetiklemez
- İsim bir emote adıyla aynı olsa bile emote görselleri bozulmaz

Eşleşince neler olacağını sen seçersin:

| Ayar | Etkisi |
|---|---|
| Etiket Rengi + kalın | Sadece ismin geçtiği kelime boyanır, mesajın kalanı normal kalır |
| Mesajın arka planını boya | Tüm mesaj balonu seçtiğin renge/yoğunluğa boyanır |
| Mesaja çerçeve çiz | Kendi rengi, kalınlığı (0–12 px) ve konumu (sol kenar / tam çerçeve) olan çerçeve |
| Etiketlendiğimde ses çal | `.wav` dosyası çalar; dosya seçilmezse Windows bildirim sesi |

**Öncelik:** etiket arka planı ve çerçevesi, Öne Çıkanlar vurgusunu ezer — adının geçtiği mesaj, yazanın rolünden daha önemli.

**Ses hakkında:** Windows'un kendi ses API'si (`winsound`) kullanılıyor, bu yüzden yalnızca `.wav` çalar ve ses seviyesi uygulama içinden ayarlanamaz (Windows ses mikserinden ayarlanır). QtMultimedia bilerek pakete konmuyor, `.exe` boyutunu ~10 MB büyütürdü. **Sesler Arası En Az** değeri iki bildirim arasındaki bekleme süresidir; kalabalık sohbette 0 yapmak sesi makineli tüfeğe çevirir, varsayılan 3 sn.

## Sorun Giderme / Log Dosyaları

Uygulama beklenmedik şekilde kapanırsa sebebi diske yazılır. Ayarlar → **Genel** sekmesindeki **Log Klasörünü Aç** düğmesiyle ulaşabilirsin, ya da doğrudan:

```
%LOCALAPPDATA%\KickOverlay\logs\
```

İki dosya var:

| Dosya | Ne içerir |
|---|---|
| `kickoverlay.log` | Uygulama olayları (başlat/durdur/bağlantı/ayar), Python hataları ve tam traceback, Qt uyarıları. 1 MB'ta döner, 3 eski kopya tutulur. |
| `crash.log` | Python seviyesinde yakalanamayan sert çökmeler (Qt/C++ tarafı). `faulthandler` ile tüm thread'lerin yığın izi yazılır. |

**Nasıl okunur:** düzgün kapanışta log `surec bitiyor (kod=0)` satırıyla biter. Log bu satır olmadan aniden kesiliyorsa süreç zorla ölmüş demektir — `crash.log`'un sonuna bak. Yakalanan bir Python hatası varsa `YAKALANMAYAN HATA` satırını ve altındaki traceback'i ara.

**Log şişmesin diye:** kanal adı yanlışsa ya da internet/Kick API sürekli kesikse, bağlantı denemesi sabit 5 saniyede sonsuza kadar tekrarlanmıyor — her başarısızlıkta bekleme süresi ikiye katlanıp 60 saniyede sabitleniyor, ilk 3 denemeden sonra log satırları da (hâlâ "Ayrıntılı log" açıkken görünür şekilde) seyrekleşiyor. Eskiden bu döngü her 5 saniyede bir log satırı yazıp `kickoverlay.log`'u dakikalar içinde doldurup döndürüyordu.

Sorun bildirirken Ayarlar → Genel → **Ayrıntılı log** kutusunu işaretleyip hatayı tekrarla, sonra `kickoverlay.log`'u issue'ya ekle.

## Geliştirici Kurulumu

```bash
pip install -r requirements.txt
python main.py
```

## .exe Derleme

```bash
pip install pyinstaller pillow

# tek dosya (KickChatOverlay.exe)
pyinstaller KickChatOverlay.spec --distpath .

# portable klasor (KickChatOverlay/KickChatOverlay.exe) - antivirus
# yanlis pozitifi daha az, zip'leyip dagitmak icin
pyinstaller KickChatOverlay-onedir.spec --distpath .
```

Her iki spec dosyası da PyQt6'nın onefile/onedir derlemede varsayılan olarak tüm Qt6 klasörünü (Quick/Qml/Multimedia/Pdf gibi kullanılmayan ~40MB'lik parçalar dahil) pakete koymasını önleyip boyutu küçültüyor. Düz `pyinstaller --onefile --noconsole main.py` de çalışır ama çıktı belirgin şekilde daha büyük olur.

## TODO

- ikon / emote çözünürlüğünü yükseltme
- gif emote'ların gözükmeme sorununun düzeltilmesi
- hazır bildirim sesleri eklenmesi
- arttırma / azaltma butonları çalışmama sorununun düzeltilmesi

## Notlar / Bilinen Sınırlar

- Rozetlerin bir kısmı gerçek: moderatör, VIP, kurucu ve OG rozetleri Kick frontend'indeki SVG'lerin birebir kopyası; abone rozetleri kanal API'sinden inen gerçek PNG'ler (`%LOCALAPPDATA%\KickOverlay\sub_badges\` altında cache'lenir). Yayıncı, Kick ekibi, onaylı ve hediye eden rozetlerinin orijinal SVG'si elde olmadığı için bunlar hâlâ elle çizilmiş yaklaştırmalar.
- Kurucu rozetinin üzerindeki sayı sabit "1" — Kick bu sayıyı rozetin içine gömüyor, mesaj verisinden gelmiyor.
- Yazı tipi ve etiket ayarları **yeni gelen** mesajlara uygulanır; ekranda duran mesajlar süresi bitip kaybolana kadar eski görünümde kalır.
- Her yazı tipi her kalınlığı içermez. Kurulu olmayan bir kalınlık seçilirse Windows en yakınını taklit eder (ince fontlar kalınlaştırılırken bulanıklaşabilir). Ayar dosyasındaki yazı tipi bu bilgisayarda kurulu değilse sistem varsayılanına dönülür ve log'a yazılır.
- Bot tespiti otomatik değil — Kick mesajlarında "bot" rozeti yok. Filtreler sekmesinde bot kullanıcı adlarını elle listeleyip gizleyebilirsin (yaygın botlar önceden ekli).
- Kick API zaman zaman Cloudflare koruması yüzünden 403 dönebilir. Böyle durumda `pip install cloudscraper` kurup `kick_client.py` içindeki `requests.get` çağrısını `cloudscraper.create_scraper().get(...)` ile değiştirmen yeterli.

---

## Sponsor

Bu projeye destek olan [**clou.tr**](https://clou.tr)'a teşekkürler.

---

Made with ❤️ by vicdum
