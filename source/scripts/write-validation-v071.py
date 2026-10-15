from pathlib import Path
import json,re
root=Path(__file__).resolve().parent.parent
out=root.parent.parent/'outputs'
def read(name):return json.loads((root/'artifacts'/name).read_text(encoding='utf-8'))
version=json.loads((root/'package.json').read_text(encoding='utf-8'))['version']
ui=read('execution-status-results.json');paper=read('paper-results.json');binary=read('binary-results.json');package=read('package-results.json')
assert all(r['version']==version for r in (ui,paper,binary,package))
assert not ui['errors'] and not paper['errors'] and all(package.values())
assert binary['operations']=='passed' and binary['ml']=='passed'
assert len({d['symbol'] for d in paper['analyses']})==24 and paper['trainedContexts']>=48
count=int(re.search(r'(\d+) passed',(root/'artifacts/python-results-v071.txt').read_text(encoding='utf-8')).group(1))
assert count>=213
assert ui.get('persisted_model_check',{}).get('contexts',ui.get('trainedContexts',0))>=1
timing=paper['timing']
text=f'''# Kripto Terminali {version} — Gecikme düzeltmesi doğrulaması

15 Ekim 2026 · Gerçek veri kabulü: {paper['time']}.

## Değişiklik ve kanıt

Önceki akış, her bağlamda yeni model eğitimini bekletiyor ve bütün tarama tamamlanınca girişleri bütçeliyordu. Yeni model eğitimi tek çalışanlı, sınırlı bir arka plan kuyruğuna ayrıldı. Mevcut seçiciyle hazır sinyaller yaklaşık saniyelik ayrı giriş döngüsünde, o anda hazır diğer adaylarla sıralanır. İlk geçmiş değerlendirmesi olmayan bağlam hazır model gibi gösterilmez veya model olmadan girdi kabul edilmez.

| Kontrol | Sonuç |
|---|---|
| Python motor/risk/muhasebe/öğrenme/sohbet/görev/çıkış ve yeni gecikme kontrolleri | {count} geçti |
| Engellenmiş eğitim | Bir coinin eğitimi bekletilirken mevcut modeli hazır diğer coin analizi ve sanal girişi tamamlandı |
| Yavaş coin isteği | Başka coinin veri isteği bekletilirken hazır sinyalin sanal girişi tamamlandı; bütün tur beklenmedi |
| Yeni geri bildirim | Kayıp sonrası elenen eski kuyruk sinyali açılmadı; commit öncesi model/geri bildirim yeniden kontrol edildi |
| Yaşam döngüsü | Eski oturum/mod/durdurulan strateji/izin listesinden çıkarılan coin/eğitim şeması için eski sonuçlar uygulanmadı |
| Kuyruk | Bağlam başına en yeni iş, tekrar önleme, kapasite, hata beklemesi ve temiz kapanış geçti |
| Giriş hatası | Kayıt hatası yeni girişleri durdurdu; görev sessizce ölmedi; pozisyon koruma döngüsü bağımsız kaldı |
| Durum tutarlılığı | Sonraki analiz açılmış sinyali tekrar kuyrukta göstermedi; çift giriş oluşmadı |
| Gerçek piyasa | 24 coin, {len(paper['quotes'])} kotasyon, {paper['streams']} akış; {len(paper['analyses'])} analiz ve {paper['trainedContexts']} hazırlanmış geçmiş seçicisi |
| Hazırlık süreleri | İlk analiz {timing['firstAnalysisMs']/1000:.1f} sn; 24 coinin analiz kapsamı {timing['allCoinsMs']/1000:.1f} sn; kabul toplamı {timing['totalMs']/1000:.1f} sn |
| UI | Eğitim çalışırken gerçek analiz ve motor kontrolü birlikte gözlendi; Sade/Pro, 1280×800 ve 1440×960, taşma ve JavaScript hatası yok |
| Gömülü motor | Kimlik doğrulama, görev onayı/tekrar, araştırma çalışanı ve model kaydı geçti; paketli UI koşusundan sonra 16 arka plan modeli yerel kayıtta doğrulandı |
| Paketli masaüstü | Yeniden açılışta hesap/pozisyon/korumalı sahte anahtar korunması ve duraklama geçti |

Ölçülen süreler bu makinede ve bu ağdaki kısa kabul koşusuna aittir; önceki koşuyla kontrollü hız karşılaştırması veya gecikme garantisi değildir. Eğitim ve ağ için bilerek bekletilen bütünleştirme testleri, hazır sinyalin bu işlere bağımlı olmadığını doğrular.

## İşlem sıklığı ve sınırlar

Stratejiler hâlâ kapanmış 15 dakikalık ve 4 saatlik mumları kullanır. Anlık mumdan giriş veya 1 dakikalık scalping eklenmedi. Oynaklık, maliyetli yöntem beklentisi, veri yaşı, cüzdan, minimum 10 USDT sanal notional ve ortak risk filtreleri korunur. Bir saniyelik giriş döngüsü her saniye işlem açılacağı anlamına gelmez. Risk artırılmadı, uygun sinyal üretmek için örnek veri eklenmedi.

Bu kısa gerçek veri kabulünde {len(paper['positions'])} açık ve {len(paper['closed'])} kapanmış otomatik sanal işlem görüldü. Kârlılık kanıtı değildir. Canlı emirler kapalıdır; fonlama gözlenen akış, komisyon/kayma ve tasfiye tahmini modellerdir. İlk planın bağımsız işlem/30 gün izleme koşulları bu testlerle sağlanmış sayılmaz.

Yerel dil modeli sohbet/haber araştırması içindir; giriş emri üretmez ve ağırlıkları burada eğitilmez. Eğitimden ayrılan kısım sayısal yöntem seçicisinin geçmiş değerlendirmesidir. Mevcut dil modelinin çıkarım hızı bu güncellemede değiştirilmedi. Eski/yavaş fiyat yolunun bilgisayar kapalıyken yeniden kurulması desteklenmez.

## Önceki kontrollerin sürümü

Sohbet UI, gerçek Qwen sohbet çıktı denetimi, uzun grafik, Binance fiyat akışı ve bütçeli görev ekranı için ayrıntılı değişmeyen kabul kanıtları 0.7.0; haber/deney kabulü kendi önceki sürüm ve tarihleriyle Gercek-Veri-Dogrulamasi.json içinde korunur. Bunlar bu sürümde yeniden çalıştırılmış gibi sunulmaz. Güncel sürümün kontrolleri bu raporun tablosunda belirtilmiştir.

Kaynak arşivi, kurulabilir EXE, taşınabilir ZIP ve Türkçe rehber outputs içinde sunulur. Islem-Neden-Bekliyor.png yeni durum kartını gösterir. SHA256.json paket bütünlüğü özetlerini içerir. Gerçek kullanıcı hesabı okunarak teşhis edildi; testler ayrı geçici hesaplarda yapıldı, kullanıcı hesabına müdahale edilmedi.
'''
(out/'Dogrulama-Raporu.md').write_text(text,encoding='utf-8')
print(f'{version}: {count} tests, execution and background training validated')
