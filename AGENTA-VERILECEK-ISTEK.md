# Agent için hazır inceleme isteği

Bu ZIP'teki Kripto Terminali 0.8.0 uygulamasını bağımsız ve ayrıntılı olarak incele. Önce BASLANGIC.md, MIMARI-VE-KOD-HARITASI.md ve KURULUM-VE-TEST.md dosyalarını oku. source/ içindeki uygulanan davranışı esas al; README, önceki raporlar ve geçen testlerin bütün hataları dışladığını varsayma.

Amacım gerçek borsa verileriyle sanal işlem yapan botun doğru, tutarlı ve güvenilir çalışması. Özellikle aşağıdakileri incele:

- Grafik verisinden sinyal/model seçimine, bütçe ayırmadan emir/gerçekleşme ve kâr/zarar kaydına kadar akış.
- Ücret, kayma, fonlama, kısmi kapanış, isolated teminat/tasfiye ve tekrar gelen kayıtlar.
- Oturum/mod/görev onayı, eşzamanlı risk, coin yoğunlaşması, korelasyon ve yeniden başlatma.
- Gelecek veri sızıntısı, kapanmamış/eksik/eski mumlar, eğitim/doğrulama ayrımı, model terfi/geri alma ve araştırma adayının yetkileri.
- Otomatik geniş coin keşfi, borsa/ürün uygunluğu, dönüşümlü tarama adaleti, anlık pozisyon koruması, kaynak hata/yaşları, bellek ve API istek yükü.
- Sohbetten verilen talimatların kapsamı, onay/idempotency, sırlar, Electron/IPC ve motor süreç güvenliği.
- Kullanıcıya gösterilen durumun gerçek yürütmeyle tutarlılığı; özellikle “motor çalışıyor” ile “görev girişe açık” ayrımı.

İlk turda kodu değiştirmeden bulguları raporla. Gerekiyorsa ayrı geçici klasörde test veya küçük yeniden üretim hazırla; gerçek hesap bağlama, canlı emir kilidini açma veya mevcut kullanıcı uygulamasını yönetme. Kârlılık ölçmek için örnek sonuçları gerçek performans gibi sunma. İşlem sayısını artırmak için risk filtrelerini kendiliğinden gevşetme.

Her somut bulgu için şunları ver:

1. Öncelik: P0 kritik / P1 yüksek / P2 orta / P3 düşük.
2. Kaynak dosyası ve doğrulanmış satır numarası.
3. Hangi olay dizisinin hatayı tetiklediği; hesap, işlem veya kullanıcı üzerindeki etkisi.
4. Yeniden üretim/test kanıtı; çalıştırmadıysan bunu açıkça belirt.
5. En küçük uygun düzeltme ve düzeltmeyi doğrulayacak test.

Somut hataları, bilinen eksikleri ve isteğe bağlı ürün önerilerini ayrı yaz. Önceki raporlarda düzeltilmiş sorunları ancak bu sürümde yeniden üretilebiliyorsa yeni bulgu say. İncelemediğin veya çalıştıramadığın alanları ve platform/ağ kısıtlarını belirt. İncelemenin sonunda sonraki en değerli üç işi sırala. Bulgusuz alanlar için “kesin hatasız” veya “kâr garantili” sonucu verme.
