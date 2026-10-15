# Kripto Terminali 0.8.0 — Kullanım rehberi

## 0.8.0 — Geniş piyasa radarı

Ayarlar → **Otomatik coin keşfi** açıkken Binance ve Bybit'in aktif USDT kripto ürünleri bulunur. Piyasalar → **Geniş piyasa radarı** keşfedilen coinleri, likidite adaylarını, analiz bağlamlarını ve anlık takip kapsamını ayrı gösterir. **Listeyi yenile** sıradaki veri turunda listeyi yeniler; bakiye veya işlemleri sıfırlamaz.

Coin arama kutusuyla bütün havuz içinde arayın; sayfa başına 60 coin gösterilir. Ayrıntılı analiz, kapanmış 15 dakika / 4 saat mumlarıyla 16 coinlik dönüşümlü gruplarda yürür. Her coin aynı anda incelenmiş veya eğitilmiş sayılmaz. Güncel hacmi yetersiz, alış/satış aralığı geniş, geçmişi eksik veya giriş koşulu uygun olmayan coin bekler.

Elle seçim için otomatik keşfi kapatıp en fazla 60 USDT sembolü düzenleyin ve kaydedin. Otomatiği tekrar açınca liste yeniden oluşturulur. Mevcut bakiye, açık pozisyonlar, görev bütçesi, kaldıraç ve risk sınırları korunur. Geniş liste daha fazla eşzamanlı pozisyon izni vermez.

**Görev onayı bekleniyor** görünüyorsa analiz motoru çalışsa bile duraklatılmış görev giriş açmaz. İşlem merkezinde bütçe ve limitleri kontrol edip planı tekrar onaylayın. Uygulama yeniden açıldığında bu onay yine gerekir. Ayrıntılar `Genis-Piyasa-Radari.md` içindedir.

## 0.7.2 — İnceleme sonrası değişiklikler

- Test laboratuvarında **Yeniden test edilmeli** görünen raporu aynı ayarlarla yeniden çalıştırın. Eski sonuç korunur; giriş mumundaki stop/hedef düzeltmesini içermediği için doğrulanmış sonuç sayılmaz.
- Hesabın kaldıraç veya pozisyon tavanını düşürürseniz etkin görev de daha sıkı sınırı kullanır. İşlem merkezi fiilî sınırı gösterir; onaylanmış görevin sınırı otomatik büyümez.
- Sohbette kapanış isterken coin, borsa, spot/vadeli ve yönü açık yazın. Karmaşık/çelişkili talepler otomatik olarak daha geniş işleme çevrilmez.
- AI deneyleri önce bekleyen adaydır; onaylı karşılaştırmayı geçmeden kullanılan model olmaz. Eksik yakın dönem mumları giriş gerekçesinde veri boşluğu olarak görünür.
- Masaüstü beklenmedik kapandığında motor duraklatılıp kaydedilir; takılan arka plan işi için kapanış sınırı 10 saniyedir. Yeniden açılışta girişler duraklatılmıştır. X düğmesinin sistem tepsisine küçültmesi normal çalışmaya devam eder.
- Eski kapanmış işlemlerin hepsi geriye dönük hesaplanmadı. Uzun süre çevrimdışı kalındığında fonlama geçmişinin eksiksiz uzlaştırılması henüz garanti edilmez. Ayrıntılı bulgular ve öneriler `Inceleme-Raporu.md` içindedir.

## 0.7.1 — Eğitimden bağımsız hızlı karar akışı

Fiyat/pozisyon takibi, kapanmış mum analizi, model eğitimi ve giriş kontrolü ayrı döngülerde çalışır. Yeni model eğitilirken mevcut seçici kullanılabilir; ilk değerlendirmesi hazır olmayan bağlam işlem açmaz. Eğitim kuyruğu bağlam başına yalnız en yeni mumu tutar; tek çalışanla arka planda yürür. Hazır sinyaller, bütün coinlerin tarihçesinin veya eğitiminin bitmesini beklemeden yaklaşık saniyelik giriş döngüsünde değerlendirilir. Ağ ve işlem yükü bu süreyi etkileyebilir; bu bir gerçekleşme süresi garantisi değildir.

**İşlem neden açılmıyor?** kartı Sade ve Pro genel bakışta görünür: gerçek motor kontrolü zamanı, analiz kapsamı, eğitim kuyruğu ve bekleme nedenlerinin sayıları gösterilir. Her adayın örnek yetersizliği, maliyet sonrası ortalaması, yöntem duraklaması veya model eşiği gerekçesi kayıtta ayrı tutulur. Henüz geçmiş değerlendirmesi oluşmayan bağlam hazır istatistiksel/ML seçici olarak sayılmaz.

Bütçe ayrılmadan hemen önce mevcut model, en güncel kapanış geri bildirimi ve risk kuralları tekrar değerlendirilir. Yeni kayıp bilgisiyle elenmiş bir sinyal eski kuyruktan açılamaz. Oturum/mod değişimi, durdurma ve coin/strateji kapatma eski eğitim sonuçlarının uygulanmasını engeller. Giriş kaydı hatası yeni girişleri durdurur; giriş döngüsü sessizce kaybolmaz ve mevcut pozisyonların koruyucu takibi sürer.

Bu değişiklik strateji sıklığını veya risk profilini yükseltmez. Stratejiler hâlâ kapanmış 15 dakikalık / 4 saatlik mumları kullanır; 1 dakikalık scalping, oluşmakta olan mumdan giriş veya her fiyat hareketinde işlem eklenmemiştir. Anlık fiyat akışı, giriş koşulu bulunduğu anlamına gelmez. 100 USDT gibi küçük hesaplarda risk/komisyon ve cüzdan bütçesi, minimum 10 USDT sanal emir büyüklüğünün altında sonuç üretebilir. Kaldıraç minimum notional kuralını veya stop riskini ortadan kaldırmaz.

## 0.7.0 — Bütçeli görev ve uyarlanabilir çıkış

**İşlem merkezi**, Sade ve Pro menüsündedir. Gerçek veri için Sanal modunu seç; görev bütçesini, azami kaldıracı, eşzamanlı pozisyonu ve yeni giriş süresini (1–72 saat) gir. **Görev planını gör** hesabı değiştirmez. Kapsamı inceleyip **Bu görevi onayla** dediğinde açık otomatik stratejiler bu sınırlar içinde giriş yapabilir. “100 USDT ile piyasayı tara” aynı onay kartını sohbetten oluşturur. “Fırsatları göster” kayıtlı adayları özetler. Bu sayılar komut örneğidir; yatırım önerisi değildir.

Görev bütçesi mevcut sanal hesaptan bir üst sınırdır; bakiye eklemez veya sıfırlamaz. Risk hem görev sermayesine hem birleşik hesaba uygulanır. Onaylanan risk yüzdeleri korunur; global sınırlar sonradan düşürülürse daha sıkı olan kullanılır. Profilin sonradan yükseltilmesi görevin onaylanmış sınırlarını büyütmez. Farklı cüzdanların gerçek serbest bakiyesi ayrıca kontrol edilir. Kâr görevin bütçe tavanını otomatik büyütmez. Görev dışındaki mevcut/manuel pozisyonlar birleşik hesap riskinde kalır.

Bir anda tek görev çalışır. Eski göreve ait pozisyonlar açıkken yeni görev kurulmaz; pozisyonlar İşlemler ekranından kapatılabilir veya koruyucu çıkışları beklenebilir. Duraklatma, süre dolması, göreve özel günlük kayıp/düşüş eşiği ve yeniden açılış yeni görev girişlerini kapatır; açık pozisyonların stop/hedef takibi sürer. **Oturumu sürdür**, durdurulmuş görevi atlatmaz; yeni görev onayı gerekir. X sistem tepsisine küçültür; bilgisayar kapalıyken motor çalışmaz.

Tarama turunda onaylı sinyaller merkezi bütçe ayrılmadan önce karşılaştırılır. Puan; seçicinin skoru (70 ağırlık), risk çarpanı (20) ve spread katkısının (en fazla 10) sınırlandırılmış toplamıdır. Kâr/kazanma olasılığı veya yatırım tavsiyesi değildir. En yüksek puanlı aday önce risk kontrolüne girer; coin yoğunlaşması, cüzdan, kaldıraç, haber, veri yaşı ve global sınırlar hâlâ girişi engelleyebilir. İlk hazırlık birkaç dakika sürebilir; analiz kapsamı ve kaynak zamanları görünür. Açık pozisyon takibi taramadan bağımsız sürer. Sinyalin işlenmesi, gerekçesi, kaynak mumu ve model sürümü son 500 kararlık yerel günlükte korunur; görev olayları da kaydedilir.

Yeni Sanal pozisyonlarda varsayılan **uyarlanabilir çıkış** vardır: ilk stop mesafesi kadar lehte hareket (+1R) ve maliyet sonrası pozitif sonuç varsa uygun büyüklükte yarısı kapanır. Her iki parça en az 10 USDT olmalı; sağlanmazsa tam hedef korunur. Kalan bölümün stopu giriş/çıkış komisyonu ve gözlenen fonlama dahil başabaşa ve ilk stop mesafesiyle takip seviyesine sıkılaşır; gevşetilmez. Nihai hedef 2R ve mevcut süre sınırı korunur. Tasfiye, stop, tam hedef ve süre çıkışları önceliklidir. Başabaş seviyesi gerçekleşme garantisi değildir; boşluk, kayma ve sonraki fonlama zarara yol açabilir.

Önceden açılmış pozisyonlar eski sabit politikada kalır. Kısmi sonuçlar anında ayrı muhasebeleştirilir; işlem sayısı ve öğrenme geri bildirimi yalnız tam kapanışta, bütün parçaların neti ve ilk riskle bir kez oluşur. Manuel sohbet işlemleri öğrenme örneğine katılmaz. Araştırma/eğitim etiketleri hâlâ sabit çıkış varsayımındadır; yeni canlı fiyatlı sanal çıkış kuralının üstünlüğü kanıtlanmış değildir ve ileri dönem karşılaştırması gerektirir.

Serbest yerel AI açıklamalarında doğrulanamayan rakamlar, yazıyla tutar/oran/kaldıraç önerileri ve işlem yaptığını ileri süren çıktılar denetimle engellenip açıklayıcı mesajla değiştirilir. Bu filtre nitel yorumların doğruluğunu garanti etmez. Bakiye, gösterge, risk, plan ve görev sonuçları deterministik hesap/kayıt yollarından gösterilir. Dil modelinin emir veya risk ayarı değiştirme yetkisi yoktur; ağırlıkları yeniden eğitilmez.

## 0.6.0 — Botla konuşma

Sol menüde **AI sohbet** hem Sade hem Pro görünümde bulunur. Hesap, geçmiş işlemler ve neden beklediği hakkındaki yanıtlar gerçek kayıtlardan; fiyat/gösterge analizleri borsa mumlarından üretilir. Serbest sohbet bilgisayardaki Qwen3 4B modeline gider ve **Yerel AI yorumu** olarak etiketlenir. Model olmadan kayıt sorguları çalışır; modelin bulunmadığı/kapalı olduğu açıkça gösterilir. Mesajlar yerel veritabanında korunur.

Örnekler: “Hesabımı özetle”, “Son işlemlerimi özetle”, “Neden işlem açmadın?”, “BTC piyasa analizi yap”, “BTC 6 aylık grafik analizi yap”. Bunlar kayıt veya ölçüm yanıtıdır; serbest sohbetin yerel model yanıtıyla aynı şey değildir. Kısa analiz EMA20/50 ve RSI14 kullanır; her yanıt zaman damgasını taşır.

“Yeni girişleri durdur”, “Oturumu sürdür”, “BTC pozisyonunu kapat” önce iki dakika geçerli onay kartı oluşturur. Açık bir sanal giriş talimatı coin, bütçe ve yön ister; örnek komut biçimi: “BTC 100 USDT bütçeyle 3x vadeli long işlem aç”. Bu bir yatırım önerisi değil, komut örneğidir. Profilin kaldıraç tavanı aşılmaz; eksik/birden fazla anlamlı, koşullu veya özel stop/hedef içeren talimat uygulanmaz. Bütçe azami teminat/alış gideridir; tamamının kullanılması hedeflenmez.

Manuel giriş planında stop 2×ATR, hedef 2R, süre tavanı 4 saattir. Onayda fiyat, bakiye, kaldıraç, haber, güncellik, strateji ve bütün merkezi risk kontrolleri yeniden yapılır. %0,3 fiyat veya %2 planlanan risk artışı yeni plan gerektirir. Aynı onay tekrar işlendiğinde yeni pozisyon oluşmaz; oturum/mod değişince ve yeniden açılışta eski onaylar geçersizdir. Manuel sonuçlar otomatik stratejinin öğrenme örneği sayılmaz. Gerçek borsa emirleri gönderilmez.

Yerel modelin emir veya ayar yetkisi yoktur. Yalnız sunucunun tanıdığı açık talimatlar plan oluşturur; doğal dildeki tüm talimat biçimleri desteklenmez. Serbest yorumlar hatalı olabilir; kaynak/ölçüm yanıtlarıyla ayrı etiketlenir. İlk model yüklemesi ve yanıt donanıma göre zaman alır; haber ve sohbet aynı yerel modeli sırayla kullanır.

## Sade görünüm ve Pro

Üstteki **Sade / Pro** yalnız görünümü değiştirir. Hesap, bakiye, çalışma modu, açık pozisyon ve risk ayarları aynıdır. Seçim aynı bilgisayarda hatırlanır. İlk açılış Sade'dir. Sade'de **Oturum, AI ve öğrenme ayrıntıları** bölümünü açarak sanal bakiye/oturum, model ve AI ayrıntılarına erişebilirsiniz; Pro bütün ayrıntıları gösterir. Ayarlar iki görünümde de erişilebilirdir.

## 6 aylık ve 1 yıllık grafik analizi

**Piyasalar** ekranından coin, borsa ve spot/vadeli ürünü seçin. Grafikte **6 ay** veya **1 yıl** düğmesine basın. Sade günlük mumlar, Pro günlük veya 4 saatlik mumlar kullanır. **Yakın** normal kısa dönem grafiğine döner. **Yenile** geçmişi tekrar kontrol eder. Tarih aralığı UTC takvim ayıyla belirlenir, arayüz tarihleri İstanbul saatinde gösterir. İlk/güncel kapanmamış mum analize alınmaz.

Gerçek mumlar borsadan sayfalanır ve yerel Parquet önbelleğinde saklanır. Görünür dönemden ayrı 200 hazırlık mumu istenir. Dönem fiyat değişimi, kapanış bazlı düşüş, EMA50/200 ve günlük trend bağlamı görünür; Pro oynaklık, hacim karşılaştırması ve hazırlık sayısını da gösterir. Bunlar coin fiyatının geçmiş ölçümleridir; sanal hesabın getirisi veya kazanç tahmini değildir.

Eksik/geçmişi kısa coin veya erişim sorunu varsa kapsam sayısı ve uyarılar gösterilir; eksik mum üretilmez. DEMO'da grafikler **Örnek veri** diye etiketlidir. Uzun dönem grafik seçmek, otomatik seçiciyi bir yıllık veriyle eğitmiş veya bir yıllık strateji testi yapmış sayılmaz.

## Kaynaklı yöntem bilgisi ve AI

**Stratejiler → Kaynaklı analiz kütüphanesi** arama ve durum filtresi içerir. Karta tıklayarak yöntem, gerekli veri, sınırlar, doğrulama durumu ve birincil kaynak bağlantılarını açın. Beş uygulanmış aile, altı araştırma adayı ve üç doğrulama ilkesi vardır. VWAP/hacim profili/açık pozisyon/CVD gibi adayların verileri henüz ölçülüyormuş gibi sunulmaz.

Her AI değerlendirmesine dönüşümlü beş kaynak kartı ve varsa sizin açtığınız en son iki gerçek 6/12 aylık özet eklenir. Kartlar ve modelin yanıtında işaretlediği kartlar ayrı kaydedilir. Model henüz bu sürümle çalışmadıysa bu belirtilir. Bilinmeyen kart atfı uygulanmaz. AI deneyinin çalıştırılabilen yöntemleri mevcut beş aileyle sınırlıdır.

Bu bilgi aktarımı dil modelinin ağırlıklarını yeniden eğitmez. Kütüphane 15 Ekim 2026'da elle araştırılıp gözden geçirildi; kendiliğinden webden güncellenmez. Yerel model 6144 token bağlamla sınırlıdır; bütün dokümanlar her çağrıya yüklenmez. Sohbet ekranı bu sürümde eklendi. Dinamik kâr alma kuralları henüz uygulanmadı. Yöntemlerin tamamı kâr sağladığı kanıtlanmış stratejiler değildir.

## Korunan fiyat akışı davranışı

Binance `24hrTicker` mesajındaki son fiyat (`c`) ile alış/satış (`b/a`) aynı mesajda birlikte işlenir. Önceki okuyucu bu mesajı yalnız kitap güncellemesi saydığı için son fiyat yedek REST döngüsüne kalabiliyordu. Ham kitap mesajı son işlem zamanını yenilemez. Hızlı seçili fiyat sorgusu yalnız tek piyasanın kotasyonunu 400 ms beklemeli, üst üste binmeyen isteklerle çeker; bütün portföyü tekrar yüklemez. Binance ticker akışı yaklaşık saniyelik güncellenir, bu nedenle web sitesiyle aynı karede birebir eşitlik garanti edilmez. Fiyatın kaynağı ve son işlem mesajının yaşı görünür; beş saniyeyi aşan yaş kırmızı gösterilir. Bu süre ölçümü ağ/masaüstü gecikmesinin sıfır olduğu anlamına gelmez. Mum analizi kapanmış mumlara dayanır; mumun kapanış fiyatı anlık son fiyatla aynı olmak zorunda değildir. Komisyon fiyat başlığından düşülmez.

## Mevcut hesabı koruyarak güncelle

1. Açık eski uygulamada **Ayarlar → Uygulamadan çık** seçin. X tepsiye küçültür; tamamen çıkış değildir.
2. Yeni `KriptoTerminali-Kurulum.exe` dosyasını çalıştırın.
3. Uygulamayı açın ve **Oturumu sürdür** seçin. Bakiyeyi korumak istiyorsanız yeni oturum/sıfırlama yapmayın. Mevcut 1.000 USDT gibi sanal bakiye ve denetim kayıtları güncellemede korunur.

İlk kurulumsa bakiyeyi girip **Gerçek veride başlat** seçin. Gerçek para, API anahtarı veya testnet hesabı gerekmez. Python/Node ayrıca kurulmaz. İmzasız kişisel Windows x64 paketidir.

## Geniş coin havuzu ve işlem tarzı

Başlangıç havuzu 24 coindir: BTC, ETH, SOL, BNB, XRP, DOGE, ADA, AVAX, LINK, DOT, LTC, BCH, TRX, SUI, ICP, NEAR, APT, ARB, OP, ATOM, UNI, AAVE, FIL ve INJ. USDT pariteleri Binance/Bybit spot ve vadeli piyasalarda ayrı izlenir; borsada gerçekten bulunmayan ürün için veri/işlem uydurulmaz. Bu liste yatırım önerisi veya strateji başarısı sıralaması değildir.

Fiyatlar toplu REST ve anlık WebSocket ile alınır. Bybit abonelikleri en fazla 10 konu içeren isteklerle açılır. Son fiyat, alış/satış ve vadeli işaret fiyatı ayrı zamanlarla korunur. Yeni giriş için günlük USDT hacmi en az 5 milyon, spread en fazla %0,2 ve güncel kitap gerekir. Her coin/borsa/ürün/zaman diliminin kendi geçmiş değerlendirmesi bulunur. İlk hazırlık birkaç dakika sürebilir; bu sırada anlık fiyat ve mevcut pozisyon koruması devam eder. Analiz sayacı hedeflenen 192 bağlamın hazırlığını gösterir; likidite filtresini geçmeyen ürün analiz edilmez. Kapanmamış mumla giriş analizi yapılmaz.

Ana ekrandan profil seçilebilir:

| Profil | Pozisyon tavanı | İşlem riski tavanı | Toplam açık risk | Günlük kayıp eşiği | Düşüş eşiği | Kaldıraç |
|---|---:|---:|---:|---:|---:|---:|
| Korumacı | 4 | %0,25 | %1 | %1 | %6 | 2x |
| Dengeli | 8 | %0,50 | %2 | %2 | %10 | 3x |
| Atak | 12 | %0,75 | %4 | %3 | %15 | 5x |
| Otomatik karma (varsayılan) | 8 | %0,75 | %2 | %2 | %10 | 3x |

Karma modda korumacı pay işlem tavanının üçte biri, dengeli pay üçte ikisi, atak pay tamamıdır. Öğrenme risk çarpanı ayrıca uygulanır: yeni yöntemlerde ilk beş gerçek sanal kapanış birikene kadar en fazla ×0,25. Atak karma pay için aynı coin/borsa/ürün/zaman dilimi ve yöntemde en az beş gerçek kapanışın son onluk toplamı pozitif, model skoru en az 0,65 ve öğrenme risk çarpanı 1 olmalıdır. Skor kalibre edilmiş kazanç olasılığı değildir. Atak profil de uygun olmayan sinyali zorla açmaz.

Tek coin planlanan risk tavanı sırasıyla %0,5 / %1 / %1,5 / %1; bağlantılı coin tavanı %0,75 / %1,25 / %2,5 / %1,25'tir. Borsa ve spot/vadeli arasında aynı coin birlikte sayılır. Son 192 eşleşen 15dk getirisinden en az 48 gözlem varsa mutlak korelasyon ≥0,85 birlikte bütçelenir; ilişki bilinmiyorsa ortak bütçe kullanılır. Ters pozisyonlar için otomatik hedge indirimi yapılmaz. Büyüklük atomik merkezi bütçeden ayrılır; strateji ve cüzdan tavanları ayrıca uygulanır. Bu yüzden pozisyon tavanı dolmak zorunda değildir.

Profil seçmek açık işlemleri büyütmez; yeni büyüklükler yeni girişlere uygulanır. Günlük kayıp/düşüş sınırları hemen geçerli olur; düşüş çıkışı mevcut pozisyonları da kapatmayı deneyebilir. Ayarlar'daki sayısal değişiklikler özel profil oluşturur. En fazla 60 USDT paritesi elle seçilebilir; açık pozisyonlu coin çıkarılamaz. Eski standart BTC/ETH listesi güncellemede genişler; kişisel liste, daha düşük kişisel limitler ve mevcut sanal bakiye korunur. Yeni oturum başlatmanız gerekmez.

## Bu sürümde bot nasıl öğreniyor?

**Öğrenen karar motoru** beş yöntemi karşılaştırır: kanal kırılımı, momentum, trend içi geri çekilme, ortalamaya dönüş, sıkışma kırılımı. Hem 15dk hem 4s bağlamında çalışır. Tarihsel maliyetli örneklerden öğrenilen sonuçlar ve kendi sanal kapanışları, hangi yöntemin seçileceğini ve yeni işlem riskini etkiler. Öğrenme artık yalnız ekranda izlenen bir skor değildir.

Kapanan işlemin gerçek sanal komisyon/fonlama sonrası net sonucu kaydedilir. Yöntemlere ait sonuçlar seçim ağırlığını değiştirir. İlk beş kapanış birikene kadar öğrenme risk çarpanı en fazla dörtte birdir; karma profil payı ayrıca uygulanır. Kaybeden yöntem daha küçük açılabilir; son beş kapanış toplamı -1,5R altındaysa 24 saat bekleyebilir. Bu sırada portföy tavanları değişmez.

**İstatistiksel seçici etkin**: tarihsel sonuçlar ve sanal kapanış geri bildirimiyle yöntem seçilir. **ML seçimi etkin**: sınıflandırıcı ayrıca girişleri seçer/veto eder. İkisi aynı şey değildir. ML adayı kabul ölçütlerini geçmediyse etkinmiş gibi gösterilmez. Uygun yöntem yoksa bot bekler.

Yeni model, mevcut modele karşı eğitiminden sonra gelen gerçek fiyatlarla ayrı referans işlemlerinde izlenir. İkisinde de en az 20 kapanış, daha iyi pozitif net/ortalama R ve daha yüksek olmayan gerçekleşmiş sonuç düşüşü gerekir. Fonlaması tamamlanmamış referanslar sayılmaz. Kötüleşen modelde geri alma koşulu bulunur. **Bunlar gelecekte daha iyi sonuç garantisi değildir.**

1R, işlemin başlangıçta planlanan kayıp birimidir. Referans 1R sonuçları birleşik hesabın USDT kârı değildir. Tarihsel örneklerde fonlama gerçek seri yerine aleyhte taşıma maliyeti varsayımıdır; ileri dönem ve gerçek sanal işlemler gözlenen fonlamayı kullanır.

## Ücretsiz yerel AI

**Yerel haber analisti & araştırmacı**, Qwen3 4B modeliyle bu bilgisayarda çalışır; ücretli AI API'si kullanılmaz. Bu kişisel teslimde model indirildi ve doğrulandı. Temiz/başka bilgisayarda dosyalar yoksa **Ücretsiz modeli indir · 2,5 GB** düğmesi görünür. İndirme sürdürülebilir; bütünlük kontrolü yapılmadan dosyalar çalıştırılmaz.

Model ilk analizde belleğe yüklenir. İlk yanıtın hazırlanması donanıma göre zaman alabilir. Bu sırada fiyat, stop ve risk takibi ayrı motorla devam eder. NVIDIA kartı tercih edilir; bellek yetersizse daha az katman/CPU denenir. Model dosyaları `%LOCALAPPDATA%/KriptoTerminaliAI` klasöründedir ve küçük kurulum EXE'sinden ayrı tutulur.

AI; Fed, SEC, ECB, Beyaz Saray ve Avrupa Konseyi kaynakları ile BLS takviminden gelen seçilmiş haberleri, tarihlerini ve sınırlı kaynak metinlerini değerlendirir. Erişilemeyen kaynak görünür. Bütün dünya haberlerinin eksiksiz veya anında kapsandığı iddia edilmez.

Yorumlar kaynaklarla gösterilir. Giriş etkisi için bilinen resmî alan adı, 24 saatten yeni yayın, modelin bildirdiği en az 0,8 güven ve en fazla 15 dakikalık yorum süresi gerekir. Etki uygulanmadıysa ekranda belirtilir. Risk azaltma yeni giriş riskini yarıya indirir; bekletme yeni girişleri durdurur. Açık pozisyon çıkışları risk motorunda kalır. Modelin güveni kalibre edilmiş olasılık değildir; yorumu haberin doğrulanmış etkisi sayılmaz.

AI önceki deney sonuçlarını bağlamda kullanıp mevcut beş yöntemden en fazla üçü ve izinli skor eşiğiyle bir hipotez oluşturur. Altı saatte en fazla bir otomatik deney maliyetli tarihsel değerlendirmeye gönderilir. Sonuç ve ileri dönem kuyruğu aynı paneldedir. Öneri, otomatik emir veya kârlılık kanıtı değildir; serbest kod üretip çalıştıramaz.

Dil modelinin ön eğitim ağırlıkları bu bilgisayarda yeniden eğitilmez. Öğrenen kısım işlem seçicileri, model adayları ve sonuçları hatırlayan araştırma döngüsüdür. Ayarlar'dan yerel AI, haber etkisi ve otomatik araştırma ayrı yönetilebilir; haricî ücretli AI kapalı kalır.

## Sonuçları izle

- Üstte **maliyet sonrası sonuç**, özsermaye, risk ve hesap düşüşü bulunur.
- **Bot şimdi ne düşünüyor?** seçilen yöntemi, bekleme/veto gerekçesini ve model durumunu gösterir.
- **Öğrenilen yöntem ağırlıkları** her yöntemin değerlendirmesini ve kısıtını gösterir.
- **İşlemler** bölümünde açılış, kapanış, yöntem, risk çarpanı ve net sonuç görünür.

Spot yalnız long, vadeli long/short destekler. Bakiye Binance/Bybit spot/vadeli arasında eşit bölünür. Seçili profilin tavanları yukarıdaki tabloda gösterilir. Öğrenen seçici bu tavanları yükseltemez.

Komisyon tahmini spot tek taraf %0,10, vadeli %0,06; kayma tek taraf %0,03'tür. Spread/kayma ikinci kez düşülmez. Tasfiye, gerçek işaret fiyatı ve sabit %1 bakım teminatı varsayımıyla tahmin edilir; borsanın kesin kademeli tasfiye/sigorta/ADL hesabı değildir.

## Çalışma ve kayıtlar

Bilgisayar ve internet açık kalmalıdır. X tepsiye küçültür. **Yeni girişleri durdur** mevcut stop/hedef takibini durdurmaz. **Tümünü kapat** güncel alış/satış verisiyle sanal çıkış dener; veri yoksa gerçekleşmiş sayılmaz. **Yeni oturum** eski hesabı arşivleyip bakiyeyi yeniden oluşturur.

Bağlantısızken kaçırılan fiyat yolu yeniden oynatılmaz. Yeniden açılışta yeni girişler durur; pozisyonlar ilk güncel veriden izlenir. **Ayarlar → Veritabanını yedekle** hesap ve öğrenme kayıtlarını yedekler. SQLite WAL/SHM dosyalarını farklı yedeklerle karıştırmayın.

Demo/laboratuvar isteğe bağlıdır; öğrenen sanal oturumu başlatmak için gerekmez. Laboratuvar temel kırılım şablonlarının ayrı araştırmasıdır; öğrenen seçicinin hesabıyla karıştırılmamalıdır. Gerçek/testnet emirleri, canlı arbitraj, sunucu ve otomatik güncelleme bu pakette yoktur.
