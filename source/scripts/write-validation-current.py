from pathlib import Path
import json
import re

root=Path(__file__).resolve().parent.parent
out=root.parent.parent/'outputs'
def read(name):return json.loads((root/'artifacts'/name).read_text(encoding='utf-8'))
public=read('paper-results.json');package=read('package-results.json');binary=read('binary-results.json')
price=read('price-results.json');agents=read('agents-results.json');ui=read('ui-results.json')
history=read('history-results.json');history_ui=read('history-ui-results.json')
presentation=read('presentation-results.json');library=read('library-ui-results.json')
version=json.loads((root/'package.json').read_text(encoding='utf-8'))['version']
assert all(package.values()) and binary['ml']=='passed' and binary['history']=='passed'
assert all(r['version']==version for r in (public,price,agents,history_ui,binary))
assert not public['errors'] and not agents['errors'] and not history_ui['errors']
assert not presentation['consoleErrors'] and presentation['sameAccountAndPosition']=='passed'
assert price['uniquePriceEvents']>=5 and len(public['settings']['allowlist'])==24
assert len({r['symbol'] for r in public['analyses']})==24
assert len(history['cases'])==4 and all(c['coverage']['status']=='complete' for c in history['cases'])
assert all(c['coverage']['status']=='complete' for c in history_ui['cases'])
report=agents['localAI']['report']
assert len(report['knowledge']['card_ids'])==5
assert report['history_context'] and agents['localAI']['experiments'][-1]['status'] in ('forward_queue','insufficient_data')
count=int(re.search(r'(\d+) passed',(root/'artifacts/python-results-v050.txt').read_text(encoding='utf-8')).group(1))
assert count>=104
unavailable=', '.join(s['name'] for s in public['news'] if s['status']!='ok') or 'Yok'
text=f'''# Kripto Terminali {version} — Doğrulama raporu

Windows 11 x64 · 15 Ekim 2026 · Gerçek veri kontrolü: {public['time']}.

## Bu teslimde tamamlananlar

Varsayılan Sade görünüm ve isteğe bağlı Pro görünüm; gerçek 6/12 aylık grafik analizi; kaynaklı yöntem kütüphanesi ve bu bilginin yerel AI değerlendirmesine aktarılması. Önceki 24 coin, risk profilleri, sanal işlem ve öğrenen seçici korunmuştur. Kurulum ve taşınabilir paket Python motorunu içerir. Gerçek/testnet emirleri kilitlidir.

| Kontrol | Sonuç |
|---|---|
| Motor, risk, muhasebe, API, öğrenme ve yeni geçmiş/kütüphane testleri | {count} geçti |
| Geçmiş veri birim kontrolleri | Takvim ayı, sayfalama, kapanmış mum, boşluklar, önbellek, bozuk kayıt, yetki ve kaynak ayrımı |
| Gerçek Binance/Bybit geçmişi | BTC/ETH üzerinde dört 6/12 ay kontrolü; günlük ve 4s kapsamı tam; önbellek tekrarları aynı mumları verdi |
| Paketli gerçek grafik | Electron köprüsünden 6 ay ve 1 yıl gerçek BTC günlük grafiği, analiz özeti ve kaynak kütüphanesi geçti |
| Sade / Pro | Varsayılan Sade; seçim yeniden yüklemede korundu; aynı hesap ve açık pozisyon korundu |
| Görsel | 1440×960 ve 1280×800; iki görünümde ana ekranlar, kartlar ve kaynak düğmeleri incelendi; yatay taşma bulunmadı |
| Kütüphane | 14 kart, 12 birincil kaynak; arama, durum filtresi, açılan ayrıntılar ve kaynak düğmesi sınırları geçti |
| Gerçek yerel AI | Qwen3 4B; yeni kütüphane sürümüyle beş kart ve açılmış 12 aylık gerçek geçmiş özetiyle değerlendirme kaydı üretildi |
| Otomatik deney | Sınırlı hipotez maliyetli geçmiş değerlendirmesine gönderildi; sonucu ve ileri dönem durumu kaydedildi |
| Gerçek fiyatlar | {len(public['quotes'])} kotasyon, {public['streams']} WebSocket akışı; 24 coin üzerinde {len(public['analyses'])} analiz bağlamı |
| Seçili Binance fiyatı | 24 örnek, {price['uniquePriceEvents']} ayrı son fiyat olayı, en yüksek olay yaşı {price['maxAge']:.2f} sn |
| Gömülü motor | EXE açılışı, kimlik doğrulama, yeni kütüphane/geçmiş modülleri, ayrı test/ML çalışanı ve model kaydı geçti |
| Masaüstü yeniden açılışı | Pozisyonlar ve korumalı sahte anahtar korundu; yeni girişler duraklatıldı; paketli araştırma çalışanı geçti |

## Araştırmanın sınırı

Kütüphane 15 Ekim 2026'da TradingView, Bybit, scikit-learn ve özgün araştırmalardan elle gözden geçirildi. Kaynak bağlantıları kartlarda ve `Analiz-Kutuphanesi.md` içinde bulunur. Kütüphane webden kendiliğinden güncellenmez. Beş aile seçicide uygulanır; altı yeni yöntem araştırma adayı, üç kart doğrulama ilkesidir. VWAP, fiyat seviyesine göre hacim, geçmiş açık pozisyon ve CVD toplayıcıları henüz uygulanmadı. Kaynakların yöntem tanımlaması bu botun başarısını doğrulamaz.

AI'a verilen kartlarla modelin yanıtında işaretlediği kartlar ayrı tutulur. Bu kabul, bağlam aktarımı ve yapılandırılmış deney akışını doğrular; haber yorumunun doğruluk veya yatırım kalitesi ölçümü değildir. Bu turda modelin işaretlediği kart sayısı: {len(report.get('knowledge_ids',[]))}. Boş atıf listesi, modelin belirli bir kartı kullandığının kanıtı değildir. Bilinmeyen kart kimliği reddedilir. Dil modelinin ağırlıkları yeniden eğitilmez; 6144 token bağlam içinde sınırlı kaynak bilgisi sağlanır. Gerçek uzun dönem özetleri yalnız kullanıcı tarafından istenmiş, son bir gün içinde alınmış geçmişten gelir. Grafik açmak, öğrenen seçiciyi bir yıllık veriyle yeniden eğitmiş sayılmaz.

Uzun dönem grafik EMA50/200, günlük bağlam, fiyat değişimi, kapanış bazlı düşüş, oynaklık ve haftalık hacim karşılaştırması sağlar. Görünür dönemden önce 200 mum ayrıca istenir. Erişim yoksa eldeki gerçek veri ve eksikler gösterilir; gerçek mod örnek veriye dönmez. Dönem getirisi coin fiyatının değişimidir; sanal hesabın/stratejinin test getirisi değildir. Kapanış bazlı düşüş gün içi uç kayıpları içermez. DEMO görsel testleri açıkça örnek veri olarak etiketlenmiştir.

## İşlem ve öğrenme sınırları

Öğrenen seçici kapanmış mumlar, maliyetli kronolojik geçmiş ayrımı ve gerçek sanal kapanış geri bildirimlerini kullanır. İlk aday kabulü ve sonraki ileri dönem karşılaştırması ayrı kurallara bağlıdır; negatif/yetersiz aday, eksik fonlama ve tekrar kullanılan değerlendirme dönemi terfi kanıtı değildir. Model skoru kalibre edilmiş kazanma olasılığı değildir.

Sanal komisyon ve kayma varsayımsaldır; hesaba özel komisyonlar doğrulanmadı. Tarihsel etiket fonlaması aleyhte taşıma tahminidir, gerçek fonlama serisi değildir. Gerçek sanal muhasebe gözlenen işaretli fonlamayı işler. Spread ve kayma ikinci kez düşülmez. Tasfiye gerçek işaret fiyatı ve sabit %1 bakım teminatına dayalı tahmindir; borsanın kademelerini, ADL veya sigortasını birebir taklit etmez. Risk sınırları gerçekleşmiş kaybı garanti etmez.

Bu kısa kontrol {public['balance']:,.0f} USDT ile {len(public['positions'])} açık ve {len(public['closed'])} kapanmış sanal işlem gördü; kârlılık kanıtı değildir. 192 bağlamın ilk hazırlığı birkaç dakika sürebilir; uygun sinyal zorla oluşturulmaz. Gerçek veri kabulü 30 günlük izleme veya 100 bağımsız strateji işleminin yerine geçmez. Sohbetle emir verme, yeni dinamik kâr alma, kapsamlı 6/12 aylık yürüyen strateji testi bu teslimde eklenmedi.

Haber erişiminde sorun görülen kaynaklar: {unavailable}. Haber modeli en fazla dört başlık ve iki sınırlı kaynak metniyle yorumlar; dünya/siyaset haberlerinin tam ve anlık kapsamı yoktur. Yeni girişleri sınırlayabilir; emir, serbest kod veya risk tavanı değişikliği yapamaz. Yerel metin üretiminin doğruluğu ve Türkçe anlatımı her haberde garanti edilmez.

## Dağıtım ve kullanım

Mevcut uygulamadan Ayarlar → Uygulamadan çık ile tamamen çıkıp yeni EXE kurulmalıdır. X tepsiye küçültür. Güncellemede mevcut hesabı korumak için yeni oturum/sıfırlama yerine Oturumu sürdür kullanılmalıdır. Görünüm seçmek hesabı değiştirmez.

Bilgisayar/internet kapalıyken kaçırılan fiyat yolu yeniden kurulmaz. Fiyat yaşı borsa ve cihaz saat farkını da içerir; saf ağ gecikmesi ölçümü değildir. Yerel model ve ağır kabul kontrolleri cihaz belleğini korumak için sırayla çalıştırıldı. 16 GB/GTX1650Ti sistemde diğer ağır uygulamalar süreyi etkileyebilir.

Temiz başka bir Windows bilgisayarında kurulum/kaldırma sihirbazı, gerçek kullanıcı anahtarları, Telegram, 30 günlük izleme, otomatik güncelleme veya sunucu kurulumu doğrulanmadı. Kişisel paket imzasızdır. ZIP CRC'leri ve paketlerdeki motorun doğrulanmış EXE ile eşleşmesi teslim toplama sonrasında ayrıca kontrol edilir. Kaynak ZIP kullanıcı veritabanı, API anahtarı veya 2,5 GB model ağırlığı içermez. Model kullanıcı önbelleğinde ayrı tutulur; temiz bilgisayarda uygulamanın ücretsiz indirme düğmesi kullanılabilir.
'''
(out/'Dogrulama-Raporu.md').write_text(text,encoding='utf-8')
print(f'Validation {version}: {count} Python checks, real history, UI and local AI evidence verified.')
