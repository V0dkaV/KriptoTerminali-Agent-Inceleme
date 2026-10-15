# Kripto Terminali 0.7.2 — Ayrıntılı inceleme ve düzeltmeler

15 Ekim 2026. İncelenen başlangıç: 0.7.1. Bütün hata senaryoları ayrı geçici hesaplarla çalıştırıldı; kullanıcı hesabı sıfırlanmadı ve açık işlemlerine müdahale edilmedi.

## Sonuç

İnceleme yalnız arayüzle sınırlı kalmadı: sinyalden bütçe ayırmaya, gerçekleşmeden muhasebeye, araştırmadan model seçimine ve masaüstünden motorun kapanışına kadar akışlar kontrol edildi. Somut hatalar aşağıda düzeltildi. Bu çalışma uygulamanın kârlı olduğunu veya canlı işleme hazır olduğunu göstermez. Güncel test sayıları ve paket kanıtları Dogrulama-Raporu.md ile Gercek-Veri-Dogrulamasi.json içindedir.

## Öncelikli bulgular

| Öncelik | Bulgu ve etkisi | Yapılan düzeltme |
|---|---|---|
| Yüksek | Geçmiş test, giriş yapılan mumun en yüksek/en düşük fiyatını atlayabiliyordu. Aynı mumda stop olmuş işlem sonraki mumda kârlı sayılabiliyordu. | Girişten sonra aynı mumun stop/hedefi değerlendirilir. İkisi birden görülürse muhafazakâr stop seçilir. Mum içi çıkış aynı mumun açılışında geriye dönük yeniden giriş sağlamaz. Tutma süresi giriş mumunu içerir. |
| Yüksek | Geç gelen fonlama, isolated tasfiye kaybını kayıtların geliş sırasına bağlı değiştirebiliyordu. | Parça başına teminat düzeltmesi ortaklaştırıldı. Sonradan gelen fonlama, kısmi/final gerçekleşmeler ve tasfiye düzeltmesi tekrar hesaplanır; aynı kayıt ikinci kez yazılmaz. |
| Yüksek | Aşırı fiyat boşluğu ve eski emir defteri birlikteyken isolated pozisyonun ekrandaki zararı başka cüzdanları da tüketmiş gibi görünebiliyordu. | Hesap özsermayesi ve tahmini kapanış, kalan isolated teminat ile fonlama sınırını kullanır. Ham fiyat zararı teşhis için ayrı tutulur. Bu model hâlâ borsanın gerçek tasfiye hesabının yaklaşık karşılığıdır. |
| Yüksek | AI araştırma adayı, onaylı model yokken mevcut seçici gibi kullanılabiliyordu. | Deney yalnız bekleyen kuyruğa girer. Mevcut temel seçici ve terfi etmiş model korunur. Eski kayıttaki onaysız adaylar başlangıçta karantinaya alınır; ileri dönem karşılaştırması yeni kanıtla başlar. |
| Yüksek | Sohbette belirli borsa/piyasa/yön için kapanış talimatı kapsamı fazla genişleyebiliyordu. | Kapanışlar açık borsa, spot/vadeli ve long/short kapsamını filtreler. Belirsiz çoklu coin, çelişki ve dışlama sessizce “hepsini kapat”a çevrilmez. |
| Yüksek | Masaüstü beklenmedik kapanınca motor arkada tek başına çalışabiliyordu. | Masaüstünün özel bağlantısı izlenir. Kopuşta yeni giriş hemen engellenir, hesap duraklatılıp kaydedilir ve motor kapanır. Takılı arka plan işi için 10 saniyelik son sınır vardır; kayıt başarısızsa başarılı çıkış kodu verilmez. |
| Orta | Ayar/oturum yazımı yarıda kalırsa ekrandaki sınırlar ve veritabanı ayrışabiliyordu. | Ayar ve komutlarda bellek ile veritabanı birlikte geri alınır. Yedekleme kendi yazma işlemini bekleyerek kilitlenmez ve güncel model kayıtlarını içerir. |
| Orta | Küçük görevlerde mutlak risk tavanı, haber ve modelin risk azaltmasını maskeleyebiliyordu. | Stil, model ve haber çarpanları görevin risk tavanına da uygulanır. Daha sıkı global kaldıraç ve pozisyon limiti mevcut görevde etkin olur; arayüz fiilî sınırı gösterir. |
| Orta | Mum boşlukları eğitim hedefi veya yakın dönem sinyali üretebiliyordu. | Giriş/tutma aralığı eksik eğitim etiketleri elenir. Son 80 mumda boşluk varsa analiz “veri boşluğu” gerekçesiyle girişe kapatılır. |
| Orta | Eğitim çalışanı çöktüğünde bozuk süreç havuzu sonraki işleri de bozabiliyordu. | Bozuk havuz yenilenir; eski havuzun hatası yeni çalışanı silemez. Gerçek alt süreç çökertilerek sonraki eğitimin tamamlanması sınandı. |
| Orta | Temel arka plan döngüsü beklenmedik sonlanınca motor çalışıyor görünmeye devam edebiliyordu. | Döngü gözetimi yeni girişleri durdurur ve açıklamalı hata kaydı oluşturur. Yeniden açılış duraklatılmıştır; geçici motor hatası kalıcı risk durdurmasını silmez. |

## Ek kontroller ve düzeltmeler

- Geçersiz, sonsuz veya alışın satıştan büyük olduğu kotasyon giriş/çıkış hesabına alınmaz. Kapanmamış ya da gelecekteki sinyal mumu yeni pozisyon açamaz.
- Büyük fiyat farkı sonrası yeniden kurulan stop/hedefin pozitif ve sonlu olması gerekir.
- Kapanış başladığında yeni risk, ayar komutu ve sohbet işlemi engellenir. Önceden tamamlanmış onayın makbuzu tekrar dönebilir; ikinci emir oluşturulmaz.
- Çözümlenmemiş işlem grupları varken hesap sıfırlanamaz.
- Sohbet çoklu bütçe/kaldıraç, ters anlamlı talimat ve desteklenmeyen görev kapsamını sessizce yok saymaz.
- Haber/AI yenilemesi sırasında mod, oturum veya izin değişirse eski sonuç uygulanmaz. Elle haber yenilemek, duraklatılmış hesabın işlem girişlerini başlatmaz.
- Kapanış gözetimi ile Windows alt süreç başlatmanın birlikte çalışması ayrıca paket düzeyinde denetlenir. Sahiplik bağlantısının tutulması, geçmiş test veya model eğitimini beklemede bırakamaz.
- Kaynak arşivinde eksik bırakılan motor paketleme tanımı eklendi; README içindeki adımlarla Windows paketi kaynaklardan yeniden oluşturulabilir.

## Yeniden üretilen iki örnek

**Giriş mumu:** sıfır komisyon/kayma ile 100 giriş, 98 stop ve 104 hedef; giriş mumunun en düşüğü 97, sonraki mumun en yükseği 105. Eski simülasyon +100 USDT hedef sonucu yazıyordu; düzeltilmiş simülasyon giriş mumunda −50 USDT stop sonucu yazıyor. Bu tamamen sentetik hata testi, gerçek strateji performansı değildir.

**Tasfiye ve fonlama:** aynı −11,46751 USDT fonlama kaydı, tasfiyeden önce geldiğinde toplam −383,09157; sonradan geldiğinde −394,55908 yazılabiliyordu. Düzeltme ile geliş sırası toplam sonucu değiştirmiyor. Pozisyonun kısmen kapandığı durumlar da denetlendi.

## Eski kayıtlar için davranış

Eski araştırma raporları silinmedi ve değerleri sessizce değiştirilmedi. `bar-causal-v2` gerçekleşme sürümü olmayan raporlar **Yeniden test edilmeli** etiketi taşır. Aynı testi yeniden çalıştırmak gerekir; önceki sonuçlar düzeltilmiş performans kanıtı sayılmaz. Yeni raporlar ve yeni kaydedilen araştırma model bilgileri bu sürümü içerir.

Önceden hatalı muhasebeleştirilmiş kapanmış işlemler topluca geriye dönük onarılmadı. Yeni gelen fonlama mevcut bir kapanışı uzlaştırabilir; fakat bu, bütün eski işlemlerin yeniden hesaplandığı anlamına gelmez. Hesap geçmişi korunur. Yeniden başlatmada onaysız eski deneyler korunarak beklemeye alınır; terfi etmiş modeller silinmez.

## Sıradaki geliştirmeler için öneri

1. **Kesinti sonrası tam fonlama uzlaştırması.** Mevcut akış son kayıtları okur ve kapanışları sınırlı süre izler. Uzun süre kapalı kalan uygulamada bütün geçmiş fonlamayı eksiksiz bulma garantisi yoktur. Pozisyon başlangıcından itibaren sayfalama, işlenmiş zaman damgası ve eksik hesap hareketi göstergesi eklemek muhasebe güvenini artırır.
2. **Tüm tarihçe için veri kalite haritası.** Son 80 mum ve etiketin tutma aralığı korunuyor; daha eski gösterge hazırlık bölgesi ile üst zaman dilimi EMA tarihçesinin bütünlüğü henüz bütünüyle denetlenmiyor. Kaynak/zaman dilimi bazında eksik aralık haritası ve kontrollü tamamlama önerilir.
3. **Hızlı kayıt yanıtı ve sohbet iptali.** “Hangi işlemi açtın?” gibi sorular mevcut kayıttan hızlı yanıtlanabilir. Uzun yerel model yanıtı için iptal ve kuyruk görünürlüğü kullanıcı deneyimini iyileştirir. Bu, stratejiyi daha çok işlem açmaya zorlamaktan daha ölçülebilir bir iyileştirmedir.

Yeni 1 dakikalık yöntem, daha yüksek kaldıraç veya daha gevşek giriş filtresi bu hata düzeltmesine eklenmedi. Mevcut 15 dakika / 4 saat stratejileri ve canlı emir kilidi korunur. İşlem sayısını artırmanın yararı, maliyet sonrası bağımsız dönem ve ileri sanal izleme ile ayrıca ölçülmelidir.

## Doğrulamanın sınırı

Otomatik testler hesap, kapsam, zaman sıralaması ve süreç güvenilirliğini denetler. Kısa gerçek veri koşusu güncel kotasyon/analiz/eğitim bağlantısını doğrular; haftalar veya aylar süren kârlılık değerlendirmesi yerine geçmez. Yerel dil modelinin ağırlıkları eğitilmez; öğrenen parça sayısal yöntem seçicisi ve kayıtlı işlem geri bildirimidir. Gerçek emir gönderimi kapalıdır. Paket kişisel kullanım için imzasızdır.
