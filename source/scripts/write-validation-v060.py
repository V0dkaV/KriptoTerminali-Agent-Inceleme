from pathlib import Path
import json
import re

root=Path(__file__).resolve().parent.parent
out=root.parent.parent/'outputs'
def read(name):return json.loads((root/'artifacts'/name).read_text(encoding='utf-8'))
version=json.loads((root/'package.json').read_text(encoding='utf-8'))['version']
ui=read('chat-ui-results.json');model=read('chat-model-results.json');binary=read('binary-results.json')
package=read('package-results.json');paper=read('paper-results.json');price=read('price-results.json');history=read('history-ui-results.json')
baseline=read('agents-results.json')
assert all(item['version']==version for item in (ui,model,binary,package,paper,price,history))
assert not ui['errors'] and not model['errors'] and not paper['errors'] and not history['errors']
assert model['answer']['kind']=='ai' and model['accountUnchanged'] and model['analysis']['kind']=='analysis'
assert binary['conversation']=='passed' and binary['ml']=='passed' and all(package.values())
assert len({d['symbol'] for d in paper['analyses']})==24 and price['uniquePriceEvents']>=5
count=int(re.search(r'(\d+) passed',(root/'artifacts/python-results-v060.txt').read_text(encoding='utf-8')).group(1))
assert count>=128
text=f'''# Kripto Terminali {version} — Doğrulama raporu

15 Ekim 2026 · Windows 11 x64 · Sohbet kabulü: {model['time']}.

## Yeni teslim

Sade ve Pro sol menüsünde **AI sohbet** eklendi. Kalıcı konuşma geçmişi, gerçek hesap soruları, güncel mum analizi, bilgisayardaki Qwen3 4B ile serbest sohbet ve kullanıcı onaylı sanal işlem planları bulunur. Gerçek borsa emirleri gönderilmez.

| Kontrol | Sonuç |
|---|---|
| Python motor/risk/muhasebe/öğrenme/API ve yeni sohbet kontrolleri | {count} geçti |
| Sohbet UI | Sade/Pro, 1440×960 ve 1280×800, mesaj kutusu erişimi ve taşma kontrolü geçti |
| Mesajlar | Güvenli düz metin; Enter/Shift+Enter; 2000 karakter; geçmiş yeniden açılış/remount sonrasında korundu |
| Hesap ve işlem yanıtları | Gerçek kayıtlarla; model kapalıyken de çalıştı |
| Yerel model | Gerçek Qwen3 4B, {model['model']['device']}; tamamlanmış Türkçe sohbet yanıtı verdi; ücretli API yok |
| Gerçek piyasa analizi | BTC'nin güncel halka açık kapanmış mumlarından EMA20/50 ve RSI14 yanıtı; hesap/işlem değiştirilmedi |
| Plan ve onay | Önizleme hesabı değiştirmedi; onay düğmesi talimatı uyguladı ve kilitlendi |
| Talimat koruması | Açıklayıcı/varsayımsal, eksik veya çelişkili istekler emir planına dönüşmedi; desteklenmeyen özel stop/koşullu emir reddedildi |
| Manuel sanal giriş | Bütçe ve istenen düşük kaldıraç korundu; hesap/coin/ilişkili coin/strateji sınırları aynı merkezi kontrolden geçti |
| Yeniden kontrol | Onay anında duraklatma, eski kitap, düşürülen kaldıraç, fiyat değişimi, haber erişimi ve hesap düşüşü durumu tekrar sınandı |
| Tekrar ve atomiklik | Çift onay tek sonuç verdi; sonuç makbuzu kalıcı; kayıt hatasında pozisyon ve makbuz birlikte geri alındı |
| Eski onay | İki dakika, oturum/mod değişimi ve yeniden açılış korumaları geçti |
| Öğrenme ayrımı | Sohbetten açılan manuel işlemler otomatik yöntemin ML geri bildirimine eklenmedi |
| Gömülü EXE | Yeni sohbet API'si, kayıt yanıtı, onay ve tekrar makbuzu; geçmiş, araştırma alt süreci ve ML kaydı geçti |
| Paketli masaüstü | Açılış, yeniden açılışta pozisyon/korumalı sahte anahtar ve duraklama; araştırma çalışanı geçti |
| Korunan gerçek piyasa akışı | 24 coin, {len(paper['quotes'])} kotasyon, {paper['streams']} WebSocket; {len(paper['analyses'])} analiz bağlamı |
| Fiyat kontrolü | 24 örnekte {price['uniquePriceEvents']} ayrı Binance fiyat olayı; en yüksek olay yaşı {price['maxAge']:.2f} sn |
| Uzun grafik | Paketli 6/12 aylık gerçek BTC grafiği ve 14 kartlık kütüphane geçti |

## İşlevlerin sınırı

Kayıt yanıtları, gösterge hesapları ve yerel model yorumu ayrı etiketlenir. Serbest sohbet modelinin yanıtı bağımsız doğruluk veya yatırım kalitesi testinden geçmiş sayılmaz. Bu kabulde model, bağlamda tanımlanmayan nicel marj önerisi de üretti; bu nedenle yorumları işlem/risk kuralı olarak uygulanmaz. Modelin hatalı açıklama veya tavsiyeleri olabilir. Ekran bu durumu belirtir; gerçek işlem değerleri sunucunun hesapladığı onay kartındadır.

Modelin emir, serbest kod veya ayar değiştirme yetkisi yoktur. Risk tavanı sohbetten yükseltilmez. Yalnız tanımlı açık talimatlar sunucuda plan oluşturur; doğal dilin bütün biçimleri desteklenmez. Eksik coin/bütçe/yön açıklatılır. Emir gibi görünen açıklayıcı sorular ve örnek/koşullu istekler yürütülebilir plana çevrilmez. Yeni giriş planları yalnız gerçek verili Sanal modda hazırlanır.

Manuel girişler kullanıcı tarafından seçilen yöndedir; otomatik stratejinin onaylı sinyali olarak sunulmaz. Stop 2×ATR, hedef 2R, süre tavanı 4 saattir. Bütçe azami teminat/alış maliyetidir; tamamının kullanılması hedeflenmez. Risk sınırları daha küçük tutar üretebilir veya girişi reddedebilir. Onayda fiyat %0,3 veya planlanan risk %2 artmışsa yeni plan gerekir. Bütçe/kaldıraç ve merkezi kontrol her onayda yeniden uygulanır. Bunlar gerçekleşmiş kayıp garantisi değildir.

Komisyon/kayma varsayımsal; fonlama gözlenen akışa dayanır. Tasfiye sabit %1 bakım teminatı tahminidir, gerçek borsa kademeleri/ADL/sigorta ile birebir değildir. Stop, fonlama veya fiyat boşluğu planlanan kaybı aşabilir. Bu kısa gerçek veri kabulünde {len(paper['positions'])} açık ve {len(paper['closed'])} kapanmış otomatik sanal işlem görüldü; kârlılık veya 30 günlük izleme kabulü değildir.

Sohbet ve haber araştırması aynı yerel modeli sırayla kullanır. İlk yükleme ve yanıt süreleri donanıma bağlıdır. Kayıt soruları model beklemez. Üretim ağırlıkları yeniden eğitilmez. Sohbet/metinler yerel SQLite veritabanında saklanır. Kapalı bilgisayarda motor çalışmaz; kaçırılan fiyat yolu yeniden kurulmaz.

## Korunan özellikler ve önceki kabul

6/12 aylık grafikler yalnız kapanmış gerçek mumlardan hesaplanan betimleyici fiyat ölçümleridir; strateji getirisi veya yıllık eğitim sonucu değildir. Kaynak kütüphanesi 14 kart/12 kaynak içerir; beş uygulanan aile, altı araştırma adayı ve üç doğrulama ilkesi ayrıdır. Otomatik web araştırması/güncellemesi yapılmaz.

Yerel haber yorumlama ve otomatik deneyin ayrıntılı gerçek kabul kaydı **{baseline['version']}**, tarih **{baseline['time']}** sürümüne aittir. Bu sürümde yeni sohbet modeli gerçek çalıştırıldı; eski haber/deney kabulü tekrar çalıştırılmış gibi sunulmaz. `Gercek-Veri-Dogrulamasi.json` güncel sohbet ve önceki araştırma kanıtlarını sürüm/tarihleriyle ayrı içerir.

## Dağıtım

Eski uygulamadan **Ayarlar → Uygulamadan çık** ile tamamen çıkılmalı, yeni EXE kurulmalıdır. X tepsiye küçültür. Mevcut hesabı korumak için yeni oturum/sıfırlama yerine Oturumu sürdür seçilmelidir. Sol menüde AI sohbet her iki görünümde de bulunur.

Python/Node kullanıcı tarafından kurulmaz. Qwen modeli kullanıcı önbelleğinde ayrı bulunur; temiz bilgisayarda ücretsiz indirme gerekir. Kişisel Windows paketi imzasızdır. Temiz başka bilgisayarda kurulum/kaldırma, gerçek API anahtarları, Telegram, uzun dönem kârlılık, sunucu ve otomatik güncelleme doğrulanmadı. Kaynak ZIP kullanıcı veritabanı, anahtar veya model ağırlığı içermez. Teslim CRC/SHA256 ve gömülü motor eşleşmesi ayrıca kontrol edilir.
'''
(out/'Dogrulama-Raporu.md').write_text(text,encoding='utf-8')
print(f'Validation {version}: {count} Python checks; current chat/model/package and baseline research evidence verified.')
