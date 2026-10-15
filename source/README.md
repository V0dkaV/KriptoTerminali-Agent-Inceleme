# Kripto Terminali 0.8.0

## 0.8.0 — Otomatik geniş coin havuzu

Binance/Bybit aktif USDT spot ve sürekli vadeli listeleri otomatik keşfedilir. Güncel açık API kontrolünde 685 farklı kripto sembolü / 1.805 borsa ve ürün bulundu; sayı zamanla değişir. Hisse, ETF, fiat/stabil taban ve kaldıraçlı token sınıfları ayrılır. Otomatik havuz 1.500 sembolle, elle seçim 60 sembolle sınırlıdır. Hesap, onaylı görev ve risk limitleri büyütülmez.

Geniş fiyat taraması ve kapanmış mum analizi ayrıdır. Likit coinler 16'lık gruplarda dönüşümlü incelenir; en likit dört coin önceliklidir. Giriş adaylığı için en az 5 milyon USDT günlük hacim ve en fazla %0,5 alış/satış aralığı aranır; strateji, veri, maliyet ve risk kontrolleri ayrıca geçmelidir. Açık pozisyonlar ve öncelikli coinler anlık akışta tutulur. Geçmiş mumlar bellekte sınırlı tutulup diskte Parquet önbelleğine yazılır.

Genel bakış ve Piyasalar ekranı kapsamı gösterir. Arama/sayfalama tek seferde 60 coin çizer; analiz tablosu başlangıçta dört, genişletilince sayfa başına 60 satırdır. Motor çalışırken görev duraklatılmışsa **Görev onayı bekleniyor** açıkça gösterilir. Kalıcı sinyal makbuzu, geniş havuzda görüntüleme geçmişi silinse bile aynı mumdan ikinci işlem açılmasını engeller. Ayrıntılar: `docs/Genis-Piyasa-Radari.md`.

## 0.7.2 — Ayrıntılı inceleme ve güvenilirlik düzeltmeleri

Geçmiş testlerde giriş mumunun stop/hedefi ve tutma süresi düzeltildi. Eski raporlar silinmeden **Yeniden test edilmeli** etiketi alır; yeni testler `bar-causal-v2` gerçekleşme kurallarını kullanır. Eski sonuçları karşılaştırmadan önce aynı testi yeniden çalıştırın.

Geç fonlamanın isolated tasfiye muhasebesi, küçük görevlerde haber/model risk azaltımı ve sıkılaştırılan global limitlerin görev ekranına yansıması düzeltildi. Sohbet talimatlarında borsa/piyasa/yön kapsamı korunur; belirsiz çoklu talimatlar geniş kapsamlı işleme dönüştürülmez. Onaysız AI deneyleri mevcut seçicinin yerine geçmez. Eksik yakın dönem mumları girişe kapalıdır; bozuk eğitim çalışanı yenilenir.

Masaüstü bağlantısı kopunca motor yeni girişleri durdurup kaydederek kapanır. Ayar/oturum yazımı başarısızsa bellek ve kayıt birlikte geri alınır. Beklenmedik temel döngü hataları yeni girişleri durdurur. Önceden kapanmış işlemlerin tamamına geriye dönük muhasebe düzeltmesi yapılmaz. Ayrıntılar, sınırlar ve sonraki öneriler: `docs/Inceleme-Raporu.md`.

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

Windows x64 · Türkçe · gerçek Binance/Bybit verisiyle sanal işlem · ücretsiz yerel AI.

## 0.6.0 — Botla konuşma

Sol menüde **AI sohbet** hem Sade hem Pro görünümde bulunur. Hesap, geçmiş işlemler ve neden beklediği hakkındaki yanıtlar gerçek kayıtlardan; fiyat/gösterge analizleri borsa mumlarından üretilir. Serbest sohbet bilgisayardaki Qwen3 4B modeline gider ve **Yerel AI yorumu** olarak etiketlenir. Model olmadan kayıt sorguları çalışır; modelin bulunmadığı/kapalı olduğu açıkça gösterilir. Mesajlar yerel veritabanında korunur.

Örnekler: “Hesabımı özetle”, “Son işlemlerimi özetle”, “Neden işlem açmadın?”, “BTC piyasa analizi yap”, “BTC 6 aylık grafik analizi yap”. Bunlar kayıt veya ölçüm yanıtıdır; serbest sohbetin yerel model yanıtıyla aynı şey değildir. Kısa analiz EMA20/50 ve RSI14 kullanır; her yanıt zaman damgasını taşır.

“Yeni girişleri durdur”, “Oturumu sürdür”, “BTC pozisyonunu kapat” önce iki dakika geçerli onay kartı oluşturur. Açık bir sanal giriş talimatı coin, bütçe ve yön ister; örnek komut biçimi: “BTC 100 USDT bütçeyle 3x vadeli long işlem aç”. Bu bir yatırım önerisi değil, komut örneğidir. Profilin kaldıraç tavanı aşılmaz; eksik/birden fazla anlamlı, koşullu veya özel stop/hedef içeren talimat uygulanmaz. Bütçe azami teminat/alış gideridir; tamamının kullanılması hedeflenmez.

Manuel giriş planında stop 2×ATR, hedef 2R, süre tavanı 4 saattir. Onayda fiyat, bakiye, kaldıraç, haber, güncellik, strateji ve bütün merkezi risk kontrolleri yeniden yapılır. %0,3 fiyat veya %2 planlanan risk artışı yeni plan gerektirir. Aynı onay tekrar işlendiğinde yeni pozisyon oluşmaz; oturum/mod değişince ve yeniden açılışta eski onaylar geçersizdir. Manuel sonuçlar otomatik stratejinin öğrenme örneği sayılmaz. Gerçek borsa emirleri gönderilmez.

Yerel modelin emir veya ayar yetkisi yoktur. Yalnız sunucunun tanıdığı açık talimatlar plan oluşturur; doğal dildeki tüm talimat biçimleri desteklenmez. Serbest yorumlar hatalı olabilir; kaynak/ölçüm yanıtlarıyla ayrı etiketlenir. İlk model yüklemesi ve yanıt donanıma göre zaman alır; haber ve sohbet aynı yerel modeli sırayla kullanır.

## 0.5.0 ile gelen görünüm ve araştırma özellikleri

İlk açılışta **Sade** görünüm gelir: bakiye, net sonuç, açık risk, pozisyonlar, grafik ve kısa karar gerekçeleri öne çıkar. Üstteki **Pro** düğmesi tüm ayrıntılı ekranları gösterir. Görünüm cihazda hatırlanır; hesap, çalışma modu, risk veya açık işlemler değişmez. Sade görünümde gelişmiş oturum/AI ayrıntıları açılabilir ve Ayarlar her zaman erişilebilir.

Grafikte **Yakın / 6 ay / 1 yıl** seçenekleri vardır. Uzun dönemler gerçek Binance/Bybit kapanmış mumlarından sayfalanır; Sade günlük, Pro günlük veya 4 saatlik çözünürlük kullanır. Görünür aralıktan önce ayrıca 200 mum hazırlanır. EMA50/200, günlük bağlam, fiyat değişimi, kapanış bazlı düşüş, oynaklık ve hacim karşılaştırması hesaplanır. Bunlar coin fiyatının betimleyici ölçümleridir; botun geçmiş getirisi değildir. Veri boşlukları doldurulmaz, eksik kapsam/erişim sorunu belirtilir. Parquet önbelleği tekrar indirmeyi azaltır. DEMO açıkça örnek veri olarak etiketlidir.

**Stratejiler → Kaynaklı analiz kütüphanesi** yöntem, veri ihtiyacı, sınırlamalar, doğrulama durumu ve birincil kaynakları gösterir. 15 Ekim 2026 tarihinde TradingView, Bybit, scikit-learn ve özgün araştırmalar gözden geçirildi. Yeni VWAP/hacim profili/açık pozisyon/işlem akışı kartları araştırma bilgisidir; veri toplayıcıları ve işlem kuralları uygulanmış sayılmaz. Kaynaklar otomatik web taramasıyla güncellenmez.

Yerel AI her değerlendirmede kütüphaneden dönen beş kartı ve varsa kullanıcının açtığı en son iki gerçek uzun dönem özetini bağlamda alır. Verilen kartlar, kaynak kimlikleri ve modelin belirttiği kullanılan kartlar kaydedilir. Bilinmeyen kart atfı reddedilir. Bu işlem dil modelinin ağırlıklarını eğitmez; otomatik deneyler mevcut beş uygulanmış yöntemle sınırlıdır. Grafik arşivi öğrenen seçicinin ayrı eğitim penceresini otomatik büyütmez. Yerel model bağlamı 6144 token ile sınırlıdır.

Kapsamlı 6/12 aylık yürüyen strateji testi ve canlı emir bağlantısı sonraki aşamalardadır; bu teslim gerçek veriyle sanal işlem içindir.

## Korunan Binance fiyat düzeltmesi

Binance `24hrTicker` mesajındaki son fiyat (`c`) ile alış/satış (`b/a`) aynı mesajda birlikte işlenir. Önceki okuyucu bu mesajı yalnız kitap güncellemesi saydığı için son fiyat yedek REST döngüsüne kalabiliyordu. Ham kitap mesajı son işlem zamanını yenilemez. Hızlı seçili fiyat sorgusu yalnız tek piyasanın kotasyonunu 400 ms beklemeli, üst üste binmeyen isteklerle çeker; bütün portföyü tekrar yüklemez. Binance ticker akışı yaklaşık saniyelik güncellenir, bu nedenle web sitesiyle aynı karede birebir eşitlik garanti edilmez. Fiyatın kaynağı ve son işlem mesajının yaşı görünür; beş saniyeyi aşan yaş kırmızı gösterilir. Bu süre ölçümü ağ/masaüstü gecikmesinin sıfır olduğu anlamına gelmez. Mum analizi kapanmış mumlara dayanır; mumun kapanış fiyatı anlık son fiyatla aynı olmak zorunda değildir. Komisyon fiyat başlığından düşülmez.

## Başlatma / güncelleme

Eski uygulamadan **Ayarlar → Uygulamadan çık** ile tamamen çıkın; X tepsiye küçültür. Yeni kurulum EXE'sini açın. Mevcut sanal hesap ve kayıtlar korunur; **Yeni oturum** başlatmak yerine **Oturumu sürdür** kullanın. İlk kurulumda sanal bakiyeyi girip **Gerçek veride başlat** düğmesine basın. Gerçek para, API anahtarı veya testnet hesabı gerekmez.

## Öğrenme artık kararın içinde

15dk ve 4s seçiciler; kanal kırılımı, momentum, trend içi geri çekilme, ortalamaya dönüş ve sıkışma kırılımı ailelerini karşılaştırır. Gerçek tarihsel maliyetli işlem örneklerinden öğrenilen sonuçlar yöntem seçimi/veto ve risk azaltmayı etkiler. Yöntemler sınırlı, incelenebilir şablonlardır; serbest kod üretimi yoktur.

Her gerçek sanal kapanışın komisyon/fonlama sonrası net sonucu, başlangıç planlanan kayba bölünmüş R değeriyle kaydedilir. Bu geri bildirim sonraki seçimlerin yöntem ağırlığını etkiler. İlk beş kapanış birikene kadar risk tavanının dörtte biri kullanılır. Son beş yönteme ait kapanış toplamı -1,5R altındaysa yöntem 24 saat bekletilebilir. Toplam risk tavanı yükselmez.

ML için ilk adayın kronolojik maliyetli değerlendirmeyi geçmesi gerekir. Sonraki adaylar eğitimden SONRA gelen gerçek fiyatlarda mevcut seçiciyle ayrı referans işlemlerinde ölçülür. Her iki tarafta en az 20 kapanış, daha yüksek pozitif net/ortalama R ve daha büyük olmayan gerçekleşmiş sonuç düşüşü aranır. Fonlaması tamamlanmamış referanslar kabul kanıtı sayılmaz. Son 20 gerçek sanal kapanışta -3R kötüleşme koşulu oluşursa önceki modele dönüş/statistiksel seçiciye geri alma yapılır. Bu ölçütler gelecekte üstünlük garantisi değildir.

Kârlı olduğu gösterilmeyen ML adayı etkin diye gösterilmez. **İstatistiksel seçici**, model adayları incelenirken de tarihsel sonuçlar ve gerçek kapanış geri bildirimlerinden yöntem seçer; ML ile aynı şey değildir. Uygun yöntem yoksa bekler.

Tarihsel etiketler kapanmış mumlardan, sonraki açılış girişi ve muhafazakâr stop-öncelikli çıkışla üretilir. Eğitim sınırını aşan açık etiketler dışlanır. Tarihsel fonlama gerçek seri yerine aleyhte %0,03/8 saat taşıma varsayımıdır; açıkça tahminidir. İleri dönem referansları ve gerçek sanal işlemler gözlenen işaretli fonlamayı kullanır. Referans 1R sonuçları birleşik hesabın USDT kârı değildir.

## Yerel haber analisti ve araştırmacı

Qwen3 4B Q4_K_M, llama.cpp ile yalnız bu bilgisayarda çalışır. API ücreti yoktur. Fed, SEC, ECB, Beyaz Saray ve Avrupa Konseyi resmî akışları ile BLS takvimi izlenir; erişilemeyen kaynaklar görünür. Seçilmiş güncel başlıklar ve en fazla iki kaynak metni model bağlamına girer; bütün dünya haberlerinin eksiksiz veya anında kapsandığı iddia edilmez.

AI yorumları kaynak kimlikleriyle kaydedilir. Yeni giriş etkisi ancak bilinen resmî alan adı, 24 saatten yeni yayın, modelin en az 0,8 bildirdiği güven ve en fazla 15 dakikalık yorum penceresinde uygulanır. Modelin güveni kalibre edilmiş olasılık değildir. Risk azaltma varsa yeni giriş riski yarıya iner; bekletme yalnız yeni girişleri etkiler. Mevcut pozisyon çıkışlarını risk motoru yönetir.

Model önceki deney sonuçlarını bağlamda görür; en fazla üç yöntem ve 0,45/0,50/0,55 eşiklerinden birinden oluşan hipotez önerir. Altı saatte en fazla bir otomatik deney tarihsel değerlendirmeye gönderilir; ileri dönem kabulünü geçmeden terfi ettirilmez. Geçersiz kaynak, şema, yarım yanıt, serbest kod, emir veya risk tavanı değişikliği reddedilir. Haber metinlerindeki talimatlar veri kabul edilir; modele araç/işletim sistemi/emir yetkisi verilmez.

Dil modelinin milyarlarca ön eğitim ağırlığı bu bilgisayarda yeniden eğitilmez. Değişen kısım; sonuçlardan öğrenen seçiciler, aday modeller ve deney hafızasıyla yürüyen araştırmadır. Yerel model profesyonel finans uzmanı veya kâr garantisi olarak sunulmaz.

Model yaklaşık 2,5 GB'dır. Bu kişisel teslimde kullanıcının yerel önbelleğine indirildi ve SHA256 doğrulandı. Başka/temiz bilgisayarda **Ücretsiz modeli indir** düğmesi önbelleği kurar; kesilen indirme sürdürülebilir. Dizin `%LOCALAPPDATA%/KriptoTerminaliAI` içindedir. NVIDIA GPU tercih edilir; daha az katman/CPU geri dönüşü bulunur. Çalıştırıcı yalnız loopback üzerinde, geçici anahtarla ve araç/web arayüzü kapalı çalışır.

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

## Risk ve çalışma

Varsayılan 10.000 USDT ve otomatik karma profil. Bakiye iki borsa ve spot/vadeli arasında eşit bölünür. Spread/kayma iki kez düşülmez; spot %0,10, vadeli %0,06 komisyon ve tek taraf %0,03 kayma varsayılır. Tasfiye gerçek işaret fiyatı ile sabit %1 bakım teminatı modeline dayanan tahmindir; borsanın kesin risk kademesi/sigorta/ADL hesabı değildir.

Bilgisayar ve internet açık kalmalıdır. Bağlantısızken kaçırılan fiyat yolu yeniden kurulmaz. Gerçek/testnet emirleri, canlı arbitraj ve sunucu/otomatik güncelleme bu teslimde yoktur. Demo ve laboratuvarın temel kırılım testleri, öğrenen sanal seçiciden ayrı ve açıkça etiketlidir.

## Kaynak ve geliştirme

Electron 44 / Forge 8 / React / Python 3.12. Kullanıcı Python veya Node kurmaz. Kaynak geliştirme için `requirements.txt`, npm kilit dosyası ve `scripts` araçları kullanılır. Doğrulama: pytest, `test:ui`, `check-paper.cjs`, `check-agents.cjs`, PyInstaller ve paket kontrolü. `KRIPTO_DISABLE_LOCAL_AI=1` diğer testlerde çoklu model yüklemesini engeller. `KRIPTO_LOCAL_AI_DIR` geliştirme varlık dizinini seçer.

Kaynak ZIP, motorun `kripto-engine.spec` paketleme tanımını da içerir. Python 3.12 ve Node/npm bulunan Windows geliştirme ortamında, arşivdeki KriptoTerminali klasöründe:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
npm.cmd ci
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m PyInstaller --noconfirm --distpath engine-dist --workpath build\engine kripto-engine.spec
npm.cmd run make
```

Son komut Windows paketlerini `out/make` içine yazar. Bunlar kaynak geliştirme adımlarıdır; EXE kullanıcısının çalıştırması gerekmez.

SQLite WAL hesap/denetim kayıtlarını; `adaptive_feedback` gerçek kapanışları; `adaptive_controllers` sürümleri; `local_ai_report` ve `local_ai_experiments` araştırmayı saklar. Kaynak arşivi kullanıcı hesabı, anahtar, model ağırlığı veya bağımlılık klasörü içermez. Lisanslar `THIRD_PARTY_NOTICES.md` içindedir. İlk Windows paketi imzasızdır.

Birincil kaynaklar: [Qwen](https://huggingface.co/Qwen/Qwen3-4B-GGUF), [llama.cpp](https://github.com/ggml-org/llama.cpp/tree/b11655), [scikit-learn veri sızıntısı](https://scikit-learn.org/stable/common_pitfalls.html#data-leakage), [Bybit fiyatları](https://bybit-exchange.github.io/docs/v5/websocket/public/ticker). Lightweight Charts atfı uygulamada korunur.
