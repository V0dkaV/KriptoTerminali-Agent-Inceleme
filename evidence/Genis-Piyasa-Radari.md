# Kripto Terminali 0.8.0 — Geniş piyasa radarı

Sabit 24 coinlik başlangıç havuzu, Binance ve Bybit'in aktif USDT ürünlerini otomatik keşfeden bir yapıya genişletildi. 15 Ekim 2026 açık API kontrolünde 685 farklı sembol ve 1.805 borsa/ürün kaydı bulundu. Liste dinamiktir; bu sayı her kurulumda aynı kalmak zorunda değildir.

## Kapsam

- Binance spot ve USDT teminatlı sürekli vadeli; Bybit spot ve USDT teminatlı sürekli vadeli ürünler.
- Aynı sembol farklı borsa ve ürünlerde ayrı analiz bağlamıdır, coin sayısında bir kez sayılır. Çarpanlı kontrat adları ayrı borsa sembolü olarak kalır.
- İşleme açık olmayan, USDT dışındaki, fiat/stabil tabanlı, kaldıraçlı token, hisse/ETF/emtia/forex ürünleri ayrılır. Binance spot hisse sınıfını exchangeInfo içinde belirtmediğinden Binance'in kendi web ürün sınıflandırması da doğrulanır. Bu web uç noktası değişirse ilgili kaynak hata durumuna geçip önceki liste korunur.
- En fazla 1.500 sembol otomatik havuza alınır. Kapasite aşılırsa açık pozisyon coinleri korunur; kalan seçim hacme göre sınırlanır. Elle seçim en fazla 60 semboldür.

## Nasıl tarar?

**Keşif:** Liste kaynakları yaklaşık 15 dakikada bir yenilenir. Piyasalar ekranındaki Listeyi yenile sonraki veri turu için yenileme ister. Başarısız kaynak eski başarılı kaydı korur, zamanı ve hatası görünür. Bir saatten eski ürün doğrulaması otomatik yeni giriş için yeterli değildir.

**Geniş fiyat taraması:** Borsa/ürün başına toplu fiyat isteği kullanılır. Yalnız gerçekten listelendiği üründen fiyat alınır. Güncel fiyat, en az 5 milyon USDT günlük hacim ve en fazla %0,5 alış/satış aralığı dönüşümlü analiz havuzuna adaylık sağlar. Bunlar tek başına giriş sinyali değildir.

**Ayrıntılı analiz:** Kapanmış 15 dakikalık / 4 saatlik mumlar, tur başına en fazla 16 coin için incelenir. En likit dört coin önceliklidir; kalan 12 yer diğer uygun coinler arasında sırayla döner. Aynı coin bütün borsa/ürünlerde mevcut olmak zorunda değildir. Analiz tablosu borsa, ürün, zaman dilimi ve son kontrol zamanını gösterir. İlk hazırlık ve bütün havuzun dolaşımı veri miktarı, ağ ve işlemciye bağlıdır; her coin aynı anda veya her saniye analiz edilmiş sayılmaz.

**Anlık koruma:** Borsa/ürün başına en likit önceliklerden en fazla 60 coin ve o üründeki açık pozisyonlar WebSocket takibinde tutulur. Öncelik listesi her fiyat değişiminde bağlantıları yeniden başlatmaz. Diğer coinler toplu fiyat yoluyla izlenir. Açık pozisyon takibi ve merkezi risk denetimi analiz/eğitim kuyruğundan ayrıdır.

**Bellek ve eğitim:** Ham mumların bellekteki çalışma kümesi 192 bağlamla sınırlıdır; hazırlanan tarihçe `data/history/scanner` altında Parquet olarak saklanır. Diskteki tarihçe yeni turda kullanılabilir. Model eğitimi mevcut tek çalışanlı, sınırlı kuyruktadır; bütün coinler için aynı anda model çalıştırılmaz. Yerel dil modeline her araştırmada en fazla 32 ilgili sembol gönderilir; dil modelinin ağırlıkları eğitilmez.

## Risk ve hesap korunması

Coin havuzunu genişletmek bakiye, kaldıraç, eşzamanlı pozisyon veya toplam risk tavanını artırmaz. Açık pozisyonlu coin listeden kaybolsa bile korunur ve fiyat takibi sürer; ürün doğrulaması yoksa yeni giriş yapılmaz. Risk ve haber azaltmaları her girişte yeniden uygulanır. `1000PEPE` gibi bir kontratın temel varlığı bağımsız spot listesinde doğrulanabiliyorsa haber ve coin yoğunlaşması aynı temel varlıkla eşlenir; gerçek emir sembolü ve fiyat birimi değiştirilmez. `1INCH` gibi sayıyla başlayan adlar körlemesine kesilmez.

Geniş havuzda 500 satırlık görüntüleme geçmişi kalıcı tekrar engeli olarak kullanılmaz. İşlenen sinyal için oturum/mod/sinyal kimliğine bağlı ayrı SQLite makbuzu tutulur. Ekran geçmişinden silinme veya yeniden açılış aynı mumun tekrar işlenmesine yol açmaz. Makbuz, giriş ve hesap kaydıyla aynı işlemde yazılır; kayıt hatasında geri alınır.

## Arayüz ve kullanım

Genel bakış ve Piyasalar ekranında keşfedilen, izlenen, likit, analiz edilmiş ve anlık takipteki kapsamlar ayrı gösterilir. Coin listesi arama ve sayfalama kullanır; tek sayfada 60 coin vardır. Analiz tablosu başlangıçta dört satır, genişletildiğinde sayfa başına 60 satır gösterir. Yüzlerce satır tek seferde çizilmez.

Ayarlar → Otomatik coin keşfi ile geniş havuz kullanılır. Elle seçime geçerken açık pozisyon coinleri korunarak en fazla 60 sembollük liste hazırlanır; düzenleme kaydedilmeden uygulanmaz. Yeniden otomatik seçime geçmek yeni keşif turu ister. Eski bir ayar formunu kaydetmek güncel otomatik listeyi eski 24 coinle değiştiremez.

Motor çalışsa bile görev duraklatılmışsa **Görev onayı bekleniyor** uyarısı görünür. Uygulama yeniden açıldıktan sonra İşlem merkezinden bütçeyi ve limitleri kontrol edip planı tekrar onaylayın. Bu onay sinyal zorlamaz. Piyasada uygun yöntem, yeterli geçmiş veya maliyet sonrası kabul yoksa bot beklemeye devam eder. Canlı emirler kapalıdır.

## Doğrulama

Katalog filtreleri, sayfalama, bozuk/eksik kaynak, dönüşümlü kapsam, açık pozisyon koruması, ayar geri alımı, kalıcı sinyal makbuzu ve bellek/disk tarihçesi otomatik testlerde denetlenir. Gerçek API keşfi ve yeni coinlerde ayrıntılı analiz/eğitim ayrıca çalıştırılır. 1.205 örnek coin ve 241 örnek analiz içeren arayüz deneyi yalnız sayfalama ve görünüm kanıtıdır; gerçek piyasa veya performans sonucu değildir. Güncel sayılar Dogrulama-Raporu.md ve Gercek-Veri-Dogrulamasi.json içindedir.
