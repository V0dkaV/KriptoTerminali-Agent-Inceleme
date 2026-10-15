# Kaynaklı analiz kütüphanesi

Sürüm: 2026.10.15-1 · Gözden geçirme: 2026-10-15.

Bu araştırma, yöntem tanımlarını ve veri gereksinimlerini güncel birincil belgelerden gözden geçirir. Kaynak yayınının eski olması yeni bir buluş gibi sunulmaz. Bir gösterge tanımı, bu uygulamanın maliyet sonrası başarısının kanıtı değildir.

Kütüphane otomatik webden güncellenmez. Yerel AI her turda beş kart alır; kartlar salt bilgi bağlamıdır. Çalıştırılabilir deney şeması beş mevcut yöntemle sınırlıdır.

## Kanal kırılımı

Durum: **Öğrenen seçicide uygulanıyor**.

Önceki kapanmış mumların kanalını aşan hareket, üst zaman EMA eğilimiyle karşılaştırılır. Uygulamanın kendi kuralıdır.

Veri: Kapanmış OHLCV, üst zaman mumları, güncel alış/satış.

Sınır: Sahte kırılım, fiyat boşluğu ve maliyetler.

Doğrulama: Maliyetli kronolojik değerlendirme ve ileri dönem karşılaştırması; her coin için kâr kanıtı değildir.

Kaynak: [Moskowitz, Ooi, Pedersen · Time Series Momentum (2012)](https://www.aqr.com/Insights/Research/Journal-Article/Time-Series-Momentum).

## MACD ve momentum

Durum: **Öğrenen seçicide uygulanıyor**.

MACD histogram kesişimi, RSI ve üst zaman trendi uygulamanın belirlenmiş koşullarıyla birlikte kullanılır.

Veri: Kapanmış OHLCV ve yeterli hazırlık.

Sınır: Gecikme ve yatay piyasada sık ters sinyal.

Doğrulama: Seçicinin maliyetli geçmiş ve ileri dönem karşılaştırması; MACD kaynağı bu birleşimin başarısını doğrulamaz.

Kaynak: [TradingView · MACD](https://www.tradingview.com/support/solutions/43000502344-moving-average-convergence-divergence-macd-indicator/).

## Trend içi geri çekilme

Durum: **Öğrenen seçicide uygulanıyor**.

Üst zaman eğilimi yönünde EMA20 seviyesine dönüş ve yeniden geçiş araştırılır; bu, uygulamanın kuralıdır.

Veri: Kapanmış OHLCV ve üst zaman EMA50/200.

Sınır: Trend kırıldığında tekrar giriş kayıpları.

Doğrulama: Diğer dört aileyle aynı maliyet ve bağımsız ileri dönem koşulları.

Kaynak: [Moskowitz, Ooi, Pedersen · Time Series Momentum (2012)](https://www.aqr.com/Insights/Research/Journal-Article/Time-Series-Momentum).

## Bollinger ortalamaya dönüş

Durum: **Öğrenen seçicide uygulanıyor**.

Bollinger bandına geri dönüş, RSI ve sınırlı trend gücüyle değerlendirilir.

Veri: Kapanmış OHLCV, oynaklık ve trend ölçümleri.

Sınır: Banda değmek tek başına al/sat nedeni değildir; güçlü trend sürdürülebilir.

Doğrulama: Trend ailelerine karşı maliyetli karşılaştırma ve ileri dönem izleme.

Kaynak: [TradingView · Bollinger Bands](https://www.tradingview.com/support/solutions/43000501840-bollinger-bands-bb/).

## Volatilite sıkışması

Durum: **Öğrenen seçicide uygulanıyor**.

Düşük Bollinger genişliği ardından kanal kırılımı ve üst zaman teyidi kullanılır.

Veri: Kapanmış OHLCV ve geçmiş bant genişliği.

Sınır: Sıkışma, kırılım yönünü veya başarısını tek başına belirlemez.

Doğrulama: Maliyetli geçmiş ve ileri dönem karşılaştırması; haber sıçramalarında kayma izlenir.

Kaynak: [TradingView · Bollinger Bands](https://www.tradingview.com/support/solutions/43000501840-bollinger-bands-bb/).

## Olaydan başlayan VWAP

Durum: **Araştırma adayı; otomatik işlem kuralı değil**.

Önceden tanımlanan bir olaydan başlayarak hacim ağırlıklı fiyat bağlamı oluşturma adayı.

Veri: OHLCV ve zaman damgalı, önceden seçilmiş başlangıç olayı.

Sınır: Sonucu gördükten sonra başlangıç seçmek yanlılık yaratır. Mumdan hesaplanan değer işlem bazlı ortalamanın yaklaşımıdır.

Doğrulama: Başlangıç kuralı sabitlenmeli; bağımsız dönemde maliyetli karşılaştırılmalı. Henüz hesaplanmıyor.

Kaynak: [TradingView · Anchored VWAP](https://www.tradingview.com/support/solutions/43000669764-anchored-vwap-drawing-tool/).

## Hacim profili ve değer alanı

Durum: **Araştırma adayı; otomatik işlem kuralı değil**.

Fiyat seviyelerindeki hacim yoğunluğu, POC ve değer alanı için araştırma adayı.

Veri: Alt zaman mumları veya işlem bazlı fiyat/hacim geçmişi.

Sınır: Günlük mum hacmini seviyelere yaymak gerçek işlem dağılımını vermez. Yükselen mum hacmi alıcı agresör hacmi değildir.

Doğrulama: Veri çözünürlüğü ve hesap kuralı belirtilmeli; tarihsel ve ileri dönem sınanmalı. Henüz hesaplanmıyor.

Kaynak: [TradingView · Volume profile](https://www.tradingview.com/support/solutions/43000502040-volume-profile-indicators-basic-concepts/).

## Açık pozisyon ve fiyat bağlamı

Durum: **Araştırma adayı; otomatik işlem kuralı değil**.

Fiyat, hacim ve açık pozisyon değişimini birlikte inceleme adayı; yön için bağımsız kanıt gerekir.

Veri: Borsa/ürün bazlı zaman eşleşmiş açık pozisyon serisi ve birim dönüşümü.

Sınır: Açık pozisyon long/short yönünü tek başına göstermez; birimler ve rapor kalitesi değişebilir.

Doğrulama: Veri akışı ve kalite kontrolleri henüz bağlı değil; eksik ölçümden sinyal üretilmez.

Kaynak: [Bybit · Open interest API](https://bybit-exchange.github.io/docs/v5/market/open-interest), [Giagkiozis, Said · Open interest data quality (2023)](https://arxiv.org/abs/2310.14973).

## Fonlama ve baz farkı

Durum: **Araştırma adayı; otomatik işlem kuralı değil**.

Spot–vadeli farkı ile gerçekleşmiş fonlamanın maliyet sonrası birlikte incelenmesi.

Veri: Eşzamanlı spot/vadeli kitaplar, gerçek fonlama geçmişi ve iki bacağın ücretleri.

Sınır: Fonlama işareti değişebilir; baz farkı kapanmayabilir. Mevcut muhasebe fonlamayı izler, bu aday işlem kuralı değildir.

Doğrulama: İki bacağın gerçekleşme/teminat riski ve maliyetli bağımsız test gerekir.

Kaynak: [Bybit · Funding history API](https://bybit-exchange.github.io/docs/v5/market/history-fund-rate).

## İşlem akışı ve CVD

Durum: **Araştırma adayı; otomatik işlem kuralı değil**.

Gerçekleşen işlemlerin agresör yönüyle hacim farkı ve kümülatif farkını inceleme adayı.

Veri: Sıralı işlem kimliği, zaman, miktar ve agresör yönü; kopuk akışta yeniden eşleme.

Sınır: Alış/satış kotasyonu veya mum rengi gerçek agresör işlem akışının yerine geçmez.

Doğrulama: Kalıcı işlem akışı toplayıcısı henüz yok; geçmiş mumlarla CVD üretilmez.

Kaynak: [Bybit · Public trade stream](https://bybit-exchange.github.io/docs/v5/websocket/public/trade).

## 6–12 aylık trend bağlamı

Durum: **Araştırma adayı; otomatik işlem kuralı değil**.

Günlük trend, oynaklık ve düşüş bağlamıyla kısa dönem kararlarının karşılaştırılması için aday.

Veri: Gerçek 6/12 aylık mumlar ve ayrıca 200 mum hazırlık. Grafikte istenen geçmişin özeti bulunur.

Sınır: Uzun dönem araştırmasının sonuçları kriptoya veya 15 dakikalık kurala doğrudan aktarılamaz.

Doğrulama: Grafik özeti betimseldir; otomatik seçici bu uzun arşiv üzerinde yeniden eğitilmiş sayılmaz.

Kaynak: [Moskowitz, Ooi, Pedersen · Time Series Momentum (2012)](https://www.aqr.com/Insights/Research/Journal-Article/Time-Series-Momentum).

## İlerleyen dönem doğrulaması

Durum: **Doğrulama ilkesi; uygulama sınırı aşağıda**.

Geçmişte eğitip sonraki dönemde ölçme; üst üste binen hedef süreleri için ayrım aralığı kullanma ilkesi.

Veri: Zaman sıralı veriler, hedef gerçekleşme zamanı ve denenen parametre kaydı.

Sınır: Rastgele bölme veya gelecekte kapanan etiketleri eğitime almak veri sızıntısı yaratır.

Doğrulama: Mevcut seçici kronolojik ayırır ve ileri dönem karşılaştırır; kapsamlı 6/12 aylık yürüyen test henüz yok.

Kaynak: [scikit-learn · TimeSeriesSplit](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html).

## Model skoru ve kalibrasyon

Durum: **Doğrulama ilkesi; uygulama sınırı aşağıda**.

Model skorlarının gerçekleşme sıklıklarıyla bağımsız dönemde karşılaştırılması.

Veri: Yeterli bağımsız etiket, kalibrasyon eğrisi ve uygun kayıp ölçümleri.

Sınır: Skor 80/100 ifadesi kanıtlanmış %80 kazanma olasılığı değildir.

Doğrulama: Kalibrasyon raporu henüz uygulanmadı; mevcut skor kesin olasılık diye sunulmaz.

Kaynak: [scikit-learn · Probability calibration](https://scikit-learn.org/stable/modules/calibration.html).

## Çoklu deneme yanlılığı

Durum: **Doğrulama ilkesi; uygulama sınırı aşağıda**.

Çok sayıda stratejiden en iyisini seçmenin tesadüfi iyi sonuç üretme etkisini hesaba katma ilkesi.

Veri: Başarısızlar dahil tüm denemeler, örnek uzunluğu ve getiri dağılımı.

Sınır: En iyi geçmiş sonucu seçmek kalıcı üstünlük kanıtı değildir.

Doğrulama: Deneyler kaydedilir ve ileri dönem sınanır; Deflated Sharpe hesabı henüz uygulanmadı.

Kaynak: [Bailey, López de Prado · Deflated Sharpe Ratio (2014)](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf).
