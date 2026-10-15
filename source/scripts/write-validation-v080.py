from pathlib import Path
import json,re
root=Path(__file__).resolve().parent.parent
out=root.parent.parent/'outputs'
def read(name):return json.loads((root/'artifacts'/name).read_text(encoding='utf-8'))
version=json.loads((root/'package.json').read_text(encoding='utf-8'))['version']
catalog=read('catalog-public-results.json');universe=read('universe-engine-results.json');ui=read('universe-ui-results.json')
package=read('package-results.json');binary=read('binary-results.json');execution=read('execution-status-results.json')
assert all(r['version']==version for r in (catalog,universe,ui,package,binary,execution))
assert universe['packaged'] and ui['packaged'] and not ui['consoleErrors'] and not execution['errors']
assert catalog['all_sources_complete'] and universe['trainedContexts']>=8 and universe['rotatingBatches']>=2
assert all(universe[k] for k in ('sessionPreserved','balancePreserved','riskPreserved','paused'))
assert all(package.values()) and binary['ml']=='passed' and execution['trainedContexts']>=1
count=int(re.search(r'(\d+) passed',(root/'artifacts/python-results-v080.txt').read_text(encoding='utf-8')).group(1))
assert count>=381
text=f'''# Kripto Terminali {version} — Geniş piyasa doğrulaması

15 Ekim 2026. Katalog kontrolü: {catalog['verified_at']}. Gömülü motor kabulü: {universe['time']}.

## Güncel kabul

| Kontrol | Sonuç |
|---|---|
| Motor/risk/muhasebe/öğrenme/sohbet ve yeni katalog/kapsam testleri | {count} geçti; 23 bağımlılık kullanım uyarısı, test hatası yok |
| Açık API katalogları | {catalog['unique_symbols']} farklı kripto sembolü, {catalog['products']} borsa/ürün; dört kaynak tam |
| Katalog güvenilirliği | Aktif ürün, USDT teminat, sayfalama/döngü/eksik yanıt, fiat/stabil/kaldıraçlı token ve hisse/ETF sınıfları denetlendi |
| Binance spot sınıflandırması | Borsanın web ürün etiketleri doğrulandı; eksik sınıflandırma kabul edilmez. Bu ek web uç noktası belgeli işlem API'sinin dışında bir bağımlılıktır |
| Gömülü Windows motoru | {universe['universe']['discovered']} keşfedilmiş sembol, {universe['quotes']} kotasyon, {universe['streams']} güncel anlık akış |
| Gerçek grafik/eğitim | {universe['analysisCount']} kapanmış mum analizi, {len(universe['analyzedSymbols'])} farklı sembol, {universe['trainedContexts']} bitmiş model bağlamı, {universe['rotatingBatches']} farklı analiz grubu |
| Yeni coinler | İlk 24'lük listede olmayan coinlerde gerçek mum analizi ve geçmişten hazırlanan model gözlendi |
| Hesap | Liste genişlerken hesap oturumu, {universe['initialBalance']:,.0f} USDT sanal bakiye ve risk/kaldıraç sınırları korundu |
| Görev | Motor çalışırken duraklatılmış görev ana ekranda girişe kapalı göründü; yeniden onay adımları gösterildi |
| Kalıcı sinyal makbuzu | 500 satırlık geçmişin dışına çıkma ve yeniden açılış ikinci işlem üretmedi; başarısız işlem makbuzu geri aldı |
| Kaynak ve bellek | Ürün eşleştirmesi, eski/başarısız kaynak, açık pozisyon koruması, adil dönüşüm, 192 ham tarihçe bağlamı ve diskten yeniden yükleme geçti |
| Paketli UI | Otomatik/manüel geçişte hesap korunması, yeniden keşif, arama/sayfalama, Sade/Pro, 1280×800 ve 1440×960; taşma/JavaScript hatası yok |
| Büyük UI fikstürü | 1.205 örnek coin ve 241 örnek analiz; en fazla 60 coin/satır, başlangıçta 4 analiz; arama, boş/hata durumları geçti. Gerçek piyasa sonucu değildir |
| Ayrı paketli BTC/ETH kontrolü | Analiz eğitim sürerken ilerledi; {execution['trainedContexts']} arka plan modeli tamamlandı; iki görünüm/boyut ve duraklatma geçti |
| Masaüstü/araştırma | Yeniden açılışta pozisyon, duraklama ve korumalı sahte anahtar korundu; gömülü araştırma/ML çalışanları ve model kaydı geçti |

## Kullanım ve sınırlar

Ayarlar → Otomatik coin keşfi açıkken havuz yenilenir. Mevcut görev uygulama yeniden açılınca duraklatılmış kalır; İşlem merkezinde bütçeyi/limitleri inceleyip planı tekrar onaylamak gerekir. Liste genişlemesi bu onayı veya toplam risk tavanını atlamaz. Kaynaklar yaklaşık 15 dakikada bir yenilenir. Manüel modda en fazla 60, otomatik modda en fazla 1.500 sembol vardır; açık pozisyon coinleri korunur.

Geniş fiyat taraması bütün havuzu kapsar; ayrıntılı kapanmış mum analizi likit coinler arasında 16'lık gruplarda döner. En likit dört coin önceliklidir. Her coin aynı anda incelenmiş/eğitilmiş sayılmaz. En az 5 milyon USDT günlük hacim, en fazla %0,5 alış/satış aralığı, yeterli geçmiş, strateji/maliyet/risk koşulları ayrıca aranır. Sayılar dinamiktir. Hazırlık süresi ağ ve bilgisayara bağlıdır; işlem sıklığı garantisi yoktur.

Bu kısa gömülü motor koşusunda {universe['positions']} açık ve {universe['closed']} kapanmış otomatik sanal işlem gözlendi. Bunlar kârlılık kanıtı veya 30 günlük ileri izleme değildir. Dil modelinin ağırlıkları eğitilmez; sayısal seçiciye geçmiş değerlendirmesi hazırlanır. Canlı emirler kapalıdır. Gerçek kullanıcı hesabı değiştirilmedi; bütün kabul senaryoları ayrı geçici hesaplarda çalıştırıldı.

Önceki 0.7.2 muhasebe/gerçekleşme düzeltmeleri korunur; eski araştırma raporları yeniden test ister. Eski kapanmış hesap hareketlerinin hepsi geriye dönük onarılmadı. Uzun çevrimdışı aradan sonra tüm fonlama geçmişinin eksiksiz uzlaştırılması ile eski/üst zaman dilimi gösterge geçmişi boşluk denetimi sonraki önceliklerdir. Ayrıntılar Inceleme-Raporu.md ve Genis-Piyasa-Radari.md içindedir.

## Kanıtların sürümü ve teslim

0.8.0 katalog, geniş havuz motoru/UI, eğitim durumu, paket ve test kabulü günceldir. Önceki 24 coinlik gerçek veri koşusu, sohbet modeli, uzun grafik, fiyat karşılaştırması ve ayrıntılı 0.7.2 muhasebe UI/sahiplik kanıtları Gercek-Veri-Dogrulamasi.json içinde kendi sürüm ve tarihleriyle korunur; yeniden yapılmış gibi sunulmaz.

Windows kurulum EXE, taşınabilir ZIP, kaynak ZIP, Türkçe rehber ve yeni radar raporu outputs içindedir. Paket kişisel kullanım için imzasızdır. Teslim denetimi ZIP CRC, kaynak sürümü, paketlerde aynı gömülü motor ve SHA256 özetlerini denetler. Kaynak ZIP hesap, anahtar, model ağırlığı veya bağımlılık klasörü içermez; motorun paketleme tanımını içerir.
'''
(out/'Dogrulama-Raporu.md').write_text(text,encoding='utf-8')
print(f'{version}: {count} tests, {catalog["unique_symbols"]} catalog symbols, native rotating analysis and packaged UI validated')
