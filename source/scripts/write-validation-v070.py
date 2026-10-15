from pathlib import Path
import json
import re

root=Path(__file__).resolve().parent.parent
out=root.parent.parent/'outputs'
def read(name):return json.loads((root/'artifacts'/name).read_text(encoding='utf-8'))
version=json.loads((root/'package.json').read_text(encoding='utf-8'))['version']
ui=read('chat-ui-results.json');model=read('chat-model-results.json');binary=read('binary-results.json')
package=read('package-results.json');paper=read('paper-results.json');price=read('price-results.json')
history=read('history-ui-results.json');operations=read('operations-ui-results.json');baseline=read('agents-results.json')
assert all(item['version']==version for item in (ui,model,binary,package,paper,price,history,operations))
assert not any(item['errors'] for item in (ui,model,paper,history,operations))
assert binary['operations']=='passed' and binary['ml']=='passed'
assert all(package.values()) and model['accountUnchanged']
assert model['answer']['grounding']['status'] in ('qualitative','blocked')
assert len({d['symbol'] for d in paper['analyses']})==24
assert paper['operations']['mission']['capital']==100
count=int(re.search(r'(\d+) passed',(root/'artifacts/python-results-v070.txt').read_text(encoding='utf-8')).group(1))
assert count>=195
text=f'''# Kripto Terminali {version} — Doğrulama raporu

15 Ekim 2026 · Windows x64 · Gerçek piyasa kabulü: {paper['time']}.

## Bu teslim

Sade ve Pro menüsünde İşlem merkezi, kullanıcı onaylı bütçeli sanal görev, tur içindeki onaylı sinyallerin karşılaştırılması, kalıcı karar günlüğü, yeni sanal pozisyonlarda kısmi kâr alma/başabaş/takip stopu ve yerel sohbet için çıktı denetimi eklendi. Gerçek borsa emri gönderilmez.

| Kontrol | Sonuç |
|---|---|
| Python risk/muhasebe/öğrenme/API/sohbet/görev/çıkış denetimleri | {count} geçti |
| İşlem merkezi | Gerçek API, Sade/Pro, 1440×960 ve 1280×800; taşma ve sayfa hatası yok |
| Görev onayı | Önizlemede hesap değişmedi; açık onay etkinleştirdi; tekrar onay aynı makbuzu verdi |
| Görev sınırları | Görev sermayesine göre risk/bütçe, global sınır, cüzdan ve pozisyon kontrolleri geçti |
| Onaylanan kapsam | Profil artırılınca onaylanmış risk yüzdeleri büyümedi; daha düşük global sınır sıkılaştı |
| Görev yaşam döngüsü | Süre, duraklatma, günlük kayıp/düşüş, eski oturum ve yeniden açılış girişleri durdurdu; sıradan sürdür görevi atlatmadı |
| Atomiklik | Onay makbuzu ve giriş kaydı hatalarında hesap/pozisyon/karar günlüğü geri alındı |
| Fırsat sıralama | Daha yüksek karşılaştırma puanlı sinyal önce işlendi; bütçe commit anında yeniden kontrol edildi |
| Yeni sanal çıkışlar | Spot/vadeli long/short, yarım çıkış, minimum tutar, komisyon, kayma, eski pozisyon uyumu, stop/tasfiye önceliği geçti |
| Fonlama | Kısmi miktarın settlement zamanındaki hesabı, geç ve yinelenen kayıtlar, tam net/başlangıç riski ile tek geri bildirim geçti |
| Sohbet denetimi | Sayısal/yazılı oran-tutar-kaldıraç, emir ve kâr garantisi iddiaları testlerde engellendi; bilinen kaynak kimlikleri korundu |
| Gerçek yerel AI | Qwen3 4B / {model['model']['device']}; çıktı denetimi durumu: {model['answer']['grounding']['status']} |
| Gerçek BTC analizi | Güncel kapanmış mumlardan EMA20/50, RSI14; hesapta işlem veya bakiye değişikliği yok |
| Gerçek 100 USDT sanal görev | {len(paper['quotes'])} kotasyon, {paper['streams']} güncel akış, {len(paper['analyses'])} analiz bağlamı, 24 coin; bütçe aşılmadı |
| Binance fiyat akışı | {price['uniquePriceEvents']} ayrı fiyat olayı; en yüksek gözlenen olay yaşı {price['maxAge']:.2f} sn |
| Uzun grafik/kütüphane | Güncel paketli 6/12 aylık gerçek BTC grafiği ve 14 kaynaklı kart kontrolü geçti |
| Gömülü motor EXE | Kimlik doğrulama, sohbet, görev onayı/tekrar/duraklatma, geçmiş, araştırma çalışanı ve ML kaydı geçti |
| Windows masaüstü paketi | Açılış, yeniden açılışta veri/pozisyon/korumalı sahte anahtar korunması ve duraklama geçti |

## Sonuçların anlamı

Bu kısa gerçek fiyat kabulünde {len(paper['positions'])} açık ve {len(paper['closed'])} kapanmış otomatik sanal işlem görüldü. Kârlılık veya uzun süreli performans kanıtı değildir. Uygun sinyal oluşturmak için veri veya risk kuralı değiştirilmedi. Gerçek para kullanılmadı. Bu teslim, ilk plandaki bütün canlı emir/arbitraj ve üretim doğrulamalarının tamamlandığı anlamına gelmez.

Yerel model kabulünde yanıtın sayısal bir iddiası denetimden geçmedi ve yerine sabit açıklama gösterildi. Bu, modelin bütün cevaplarının doğru veya yatırım kalitesinde olduğu anlamına gelmez. Çıktı denetimi temkinlidir; eğitim amaçlı bazı sayısal açıklamaları da engelleyebilir. Nitel yorumlarda yanlışlık olabilir. Sayısal hesaplar modelden bağımsız kayıt/gösterge/plan yollarından gelir. Modelin emir ve risk ayarı yetkisi yoktur; ağırlıkları yeniden eğitilmez.

Uyarlanabilir çıkış bir ileri dönem hipotezidir. Eğitim ve geçmiş test etiketleri sabit çıkış modelindedir; yeni çıkışın daha fazla kazandırdığı iddia edilmez. Stop/başabaş seviyesi gerçek gerçekleşme garantisi değildir. Kayma, fiyat boşluğu ve sonraki fonlama planlanan kaybı aşabilir. 1R ilk stop mesafesidir; kısmi işlem için her parçanın minimum büyüklük ve maliyetli pozitif sonuç koşulu vardır. Tam kapanışta tek işlem/geri bildirim sayılır.

Görev günlük kayıp/düşüş eşiği yalnız yeni görev girişlerini kapatır; açık pozisyonların mevcut stop/hedef/süre ve birleşik hesap koruması sürer. Yeni görev eski göreve ait pozisyonlar açıkken başlatılamaz. Süre bitimi veya duraklatma manuel pozisyon kapatma değildir. Kullanılabilir bütçe yeni para değildir; cüzdan ve ortak portföy sınırları ayrıca uygulanır. Görev dışı mevcut/manuel işlemler hesap riskinde kalır.

Görev neti, gerçekleşmiş parçalarla açık miktarın maliyetli tahmininin toplamıdır. Alış/satış verisi eskirse arayüz belirtir; son bilinen değer kullanılır. Uygulama kapalıyken fiyat yolu yeniden kurulmaz. Bilgisayar ve internet açık kalmalıdır. Fonlama gözlenen akışa, komisyon/kayma tahmini oranlara dayanır; tasfiye sabit %1 bakım teminatıyla tahmindir ve borsanın gerçek kademelerini temsil etmez.

İlk plandaki 100 bağımsız işlem, maliyet sonrası pozitif sonuç, en fazla %10 test düşüşü ve 30 günlük sanal izleme koşulları bu kısa doğrulamayla sağlanmış sayılmaz. Canlı emirler kapalıdır. Otomatik güncelleme, kod imzası, sunucuda kesintisiz çalışma ve çok bacaklı gerçek emir yürütme bu teslimde yoktur.

## Önceki kanıtların ayrımı

Yeni görev, sohbet denetimi, gerçek model yanıtı ve sanal veri kabulü {version} sürümünde yapıldı. Haber yorumlama/otomatik deneyin ayrıntılı önceki kabulü {baseline['version']} ({baseline['time']}) sürümüne aittir; bu teslimde tekrar yapılmış gibi gösterilmez. Grafik ölçümleri coin fiyatının betimleyici sonuçlarıdır, bot strateji getirisi değildir. Kaynak kartları otomatik web taraması veya model eğitimi değildir.

Kanıtlar: Gercek-Veri-Dogrulamasi.json, Islem-Merkezi.png ve Gorev-Onay-Plani.png. Yerel test hesapları ve sahte anahtarlar kullanıcı teslimine dahil edilmez. Paket kaynak arşivi, kurulabilir EXE ve taşınabilir ZIP olarak sunulur; SHA256.json bütünlük özetlerini içerir.
'''
(out/'Dogrulama-Raporu.md').write_text(text,encoding='utf-8')
print(f'Rapor yazıldı: {version}, {count} tests')
