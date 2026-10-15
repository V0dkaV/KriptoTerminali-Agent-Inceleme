# Mimari ve kod haritası

Dosya yolları ZIP köküne göredir. Çalıştırılabilir kaynak kökü source/ klasörüdür.

| Alan | Ana dosyalar | Kontrol noktası |
|---|---|---|
| Masaüstü ve yerel köprü | electron/main.cjs, electron/preload.cjs | süreç izolasyonu, IPC izin listesi, token/anahtarlar, tepsi ve kapanış |
| Motor sahibi ve HTTP | engine/main.py, engine/server.py | tek motor kilidi, masaüstü bağlantısı kaybı, kapanış, doğrulama/yetki |
| Merkezi yürütme | engine/core.py | sinyal → risk → büyüklük → gerçekleşme → muhasebe; kilit ve durum geçişleri |
| Görev ve sıra | engine/operations.py | bütçe/onay/süre, aday sıralama, kalıcı sinyal makbuzu ve tekrar engeli |
| Hesap ve risk | engine/models.py, portfolio.py, margin.py, exits.py | birleşik bütçe, isolated teminat, maliyet, kısmi çıkış, yoğunlaşma |
| Kalıcı kayıt | engine/store.py, state_transaction.py | SQLite WAL, atomik yazım, belleği geri alma, makbuz ve yedekleme |
| Borsa ve geniş havuz | engine/market.py, universe.py, stream.py, scanner_cache.py | katalog/ürün doğrulaması, toplu kotasyon, dönüşüm, WebSocket ve bellek/disk sınırları |
| Strateji ve öğrenme | engine/research.py, adaptive.py, training.py | nedensel geçmiş test, etiketler, maliyet, bağımsız dönem, arka plan çalışanı |
| Haber ve yerel AI | engine/news.py, local_ai.py, agents.py, knowledge.py | kaynak/yaş/güven, deney yalıtımı, bütçe/yaşam döngüsü, emir yetkisinin ayrılması |
| Sohbet | engine/chat.py, grounding.py, research_provider.py | kapsam çıkarımı, gerçek kayıtla dayanak, onay, yeniden yürütme ve sınırlı araştırma |
| Uzun tarihçe | engine/history.py | 6/12 ay kapsama, sayfalama, veri boşluğu, son özetlerin AI bağlamı |
| UI | src/App.tsx, UniversePanel.tsx, ExecutionStatus.tsx, OperationsPanel.tsx, AdaptiveLearning.tsx, ChatPanel.tsx | kapsam/durum doğruluğu, sayfalama, hata/boş/yükleniyor, erişilebilirlik |
| Paketleme | package.json, package-lock.json, forge.config.cjs, kripto-engine.spec | gömülü Python, kaynak/dağıtım uyumu, sırların dışlanması |

## Temel akış

Borsa listeleri → geniş toplu fiyat taraması → uygun coinlerin dönüşümlü kapanmış mum analizi → sayısal yöntem seçimi → görev ve merkezi risk sınırları → sanal gerçekleşme → pozisyon kontrolü/çıkış → maliyet ve kapanış geri bildirimi.

Eğitim ayrı sınırlı süreç kuyruğundadır. Haber/AI yeni girişleri azaltabilir veya durdurabilir; doğrudan borsaya emir gönderemez. Onaysız araştırma adayı aktif model yerine geçmemelidir. Canlı emir uçları kapalıdır. İnceleyen agent bu koşulları koddan bağımsız doğrulamalıdır.

## Önceden belirlenmiş sınırlar — yeni hatalarla karıştırma

- Uzun çevrimdışı aradan sonra bütün fonlama geçmişini eksiksiz uzlaştırma henüz tamamlanmış değildir.
- Yakın mumlar ve eğitim etiketi aralıkları denetlenir; daha eski/üst zaman dilimi gösterge hazırlık geçmişinin bütünü için veri kalite çalışması sürmelidir.
- Önceden hatalı muhasebeleştirilmiş bütün kapanışlar topluca geriye dönük onarılmamıştır.
- bar-causal-v2 olmayan eski araştırma raporları yeniden test ister; bu yüzden uyarı taşır.
- Eğitim etiketi sabit çıkış yaklaşımındadır; sanal uyarlanabilir kısmi çıkışın üstünlüğü ayrıca ileri dönem karşılaştırması gerektirir.
- Binance spot hisse/ETF ayrımı, Binance'in resmî web ürün sınıflandırması uç noktasına da bağlıdır; bu uç nokta belgeli işlem API'sinin dışındadır.
- 1 dakikalık scalping, bütün coinlerin eşzamanlı derin analizi ve dil modeli ağırlıklarını yeniden eğitme yoktur. Yeni semboller için ilk hazırlık zaman alır.
- Yerel model ağırlığı/runtime varlıkları pakette yoktur; sayısal motoru incelemek için gerekmez. Gerçek yerel AI çıkarımı ayrıca varlık kurulumu ister.

Önceki testler muhasebe/yaşam döngüsünü doğrular; kısa piyasa koşuları kârlılık veya 30 günlük izleme kanıtı değildir. Yeni ve yeniden üretilebilir sorunları önceliklendir.
