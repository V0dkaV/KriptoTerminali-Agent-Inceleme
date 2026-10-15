from pathlib import Path
import json,re
root=Path(__file__).resolve().parent.parent
out=root.parent.parent/'outputs'
def read(name):return json.loads((root/'artifacts'/name).read_text(encoding='utf-8'))
version=json.loads((root/'package.json').read_text(encoding='utf-8'))['version']
ui=read('execution-status-results.json');paper=read('paper-results.json');binary=read('binary-results.json');package=read('package-results.json')
review=read('review-ui-results.json');parent=read('parent-binary-results.json')
assert all(r['version']==version for r in (ui,paper,binary,package,review,parent))
assert not ui['errors'] and not paper['errors'] and not review['errors'] and all(package.values())
assert binary['operations']=='passed' and binary['ml']=='passed'
assert len({d['symbol'] for d in paper['analyses']})==24 and paper['trainedContexts']>=48
count=int(re.search(r'(\d+) passed',(root/'artifacts/python-results-v072.txt').read_text(encoding='utf-8')).group(1))
assert count>=329
assert ui['trainedContexts']>=1
assert review['packaged'] and review['accountPreserved'] and review['legacyReport']['needsRetest']
assert review['newReport']['executionModel']=='bar-causal-v2' and not review['newReport']['needsRetest']
assert parent['exitMilliseconds']<15000 and parent['restartPaused'] and parent['accountPreserved'] and parent['ownershipResearchWorker']
timing=paper['timing']
text=f'''# Kripto Terminali {version} — Doğrulama raporu

15 Ekim 2026 · Gerçek piyasa kabulü: {paper['time']}.

## Sonuçlar

| Kontrol | Sonuç |
|---|---|
| Python motor, muhasebe, risk, öğrenme, sohbet, görev ve yaşam döngüsü | {count} test geçti; 23 bağımlılık kullanım uyarısı, test hatası yok |
| Giriş mumu geçmiş testi | Eski kaynakta sentetik +100 USDT hedef; düzeltilmiş kaynakta aynı giriş mumunda −50 USDT stop. Performans ölçümü değildir. |
| Fonlama ve isolated teminat | Geç/erken fonlama, kısmi/final kapanış, tekrar gelen kayıt ve eski emir defterinde özsermaye sınırı geçti |
| Risk | Küçük görevde model/haber azaltımı; düşürülen global kaldıraç/pozisyon sınırı; geçersiz kotasyon ve kapanmamış mum engeli geçti |
| AI/öğrenme | Onaysız aday yalıtımı ve eski aday karantinası, mod/oturum/izin değişimi, gerçek eğitim çalışanı çökmesi sonrası yeniden eğitim geçti |
| Sohbet | Borsa/piyasa/yön kapanış kapsamı, çoklu/çelişkili talepleri reddetme, kapanırken işlem engeli ve makbuz tekrar güvenliği geçti |
| Kayıt | Altı farklı komutta ve ayarlarda kısmi kayıt hatasında bellek/DB geri alımı; güncel model içeren kilitlenmeyen yedek geçti |
| Süreç gözetimi | Ana masaüstünün gerçek ani ölümü, EOF, normal kapanış, bağımsız motor, takılan 60 sn iş için 10 sn son sınır ve açık sahiplik bağlantısıyla araştırma/ML başlatma senaryoları geçti |
| Gömülü EXE sahipliği | Bağlantı kopuşundan {parent['exitMilliseconds']/1000:.2f} sn sonra başarılı kapanış, aynı klasörde kilit bırakma/hesabı koruma/duraklatılmış yeniden açılış geçti |
| Paketli UI | 1440×960 ve 1280×800 eski rapor uyarısı; yeni gerçekleşme sürümüyle araştırma; görev ×5 onaylıyken fiilî ×2/2 pozisyon sınırı; hesap korunması ve JavaScript hatasız görünüm geçti |
| Gerçek veri | 24 coin, {len(paper['quotes'])} kotasyon, {paper['streams']} güncel akış, {len(paper['analyses'])} analiz, {paper['trainedContexts']} hazırlanmış geçmiş seçicisi |
| Gerçek veride süreler | İlk analiz {timing['firstAnalysisMs']/1000:.1f} sn; 24 coin kapsamı {timing['allCoinsMs']/1000:.1f} sn; kabul toplamı {timing['totalMs']/1000:.1f} sn |
| Analiz/eğitim eşzamanlılığı | Paketli uygulamada gerçek BTC/ETH analizi, eğitim sürerken motor kontrolü; {ui['trainedContexts']} bitmiş arka plan modeli; Sade/Pro, iki pencere boyutu, duraklatma durumu geçti |
| Paket | Kimlik doğrulama, araştırma/ML çalışanı, model özeti, yeniden açılışta pozisyon ve korumalı sahte anahtarın korunması geçti |

## Eski sonuçlar ve sınırlar

Eski araştırma raporları yeniden test etiketi alır; eski sonuç korunur, otomatik düzeltilmiş gibi sunulmaz. Yeni raporlar bar-causal-v2 sürümündedir. Önceden hatalı kapanmış bütün işlemler geriye dönük onarılmadı. Eski onaysız deneyler ileri karşılaştırmaya yeniden başlatılır; onaylı modeller silinmez.

Yakın veri boşluğu ve eğitim hedefi aralıkları denetleniyor; eski gösterge geçmişi ile üst zaman dilimi EMA bütünlüğü için ek çalışma gerekir. Uzun çevrimdışı aradan sonraki bütün fonlamanın eksiksiz uzlaştırılması garanti edilmez. Ayrıntılar ve öncelikli öneriler Inceleme-Raporu.md içindedir.

Bu kısa koşuda {len(paper['positions'])} açık ve {len(paper['closed'])} kapanmış otomatik sanal işlem gözlendi. Bunlar kârlılık, eğitim üstünlüğü veya 30 günlük izleme kanıtı değildir. Canlı emirler kapalıdır. Komisyon/kayma ve tasfiye varsayımları simülasyondur. Kullanıcı hesabı sıfırlanmadı; bütün hata ve kabul senaryoları ayrı geçici hesaplarda çalıştırıldı.

24 coinlik tam piyasa kabulü kaynak Electron uygulamasıyla; BTC/ETH eğitim kontrolü, rapor uyarısı, görev ekranı, yeniden açılış ve korumalı depolama kontrolleri dağıtılan Windows paketiyle yapıldı. Her ikisi aynı 0.7.2 motor kaynaklarını kullanır. Süreler bu makine ve ağdaki kabul koşusuna aittir; gecikme veya işlem sıklığı garantisi değildir.

Stratejiler 15 dakika / 4 saat kapanmış mumları kullanır; 1 dakikalık scalping eklenmedi. Yerel dil modelinin ağırlıkları eğitilmez. Bu sürüm için ayrıca gerçek dil modeli çıkarımı tekrar çalıştırılmadı; sohbetin kapsam ve yürütme denetimleri günceldir. Önceki sohbet modeli/UI, uzun grafik ve fiyat karşılaştırma kanıtları kendi sürüm ve tarihleriyle Gercek-Veri-Dogrulamasi.json içinde korunur; güncel koşu gibi sunulmaz.

## Teslimat

KriptoTerminali-Kurulum.exe, taşınabilir ZIP, kaynak ZIP, Türkçe rehber, inceleme raporu ve ekran görüntüleri outputs içindedir. Kurulum kişisel kullanım için imzasızdır. Paketlerin SHA256 özetleri SHA256.json içindedir. Teslim doğrulaması ZIP CRC, kurulum PE biçimi, kaynak sürümü, paketlerde gömülü motor özeti ve dosya hashlerini ayrıca denetler.
'''
(out/'Dogrulama-Raporu.md').write_text(text,encoding='utf-8')
print(f'{version}: {count} tests, review UI, current market and packaged ownership validated')
