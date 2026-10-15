# Önce bunu oku — Kripto Terminali 0.8.0

Bu paket programı başka AI agentlara bağımsız kod incelemesi yaptırmak için hazırlanmıştır. Hazırlanma tarihi: 16 Ekim 2026, Europe/Istanbul. İçerik teslim edilmiş 0.8.0 sürümünün sabit görüntüsüdür. Açık kullanıcı uygulamasına veya hesabına erişim içermez.

## Nereden başlamalı?

1. `AGENTA-VERILECEK-ISTEK.md`: Agentın yerine getirmesi istenen hazır inceleme isteği.
2. `MIMARI-VE-KOD-HARITASI.md`: Sistemin parçaları ve inceleme öncelikleri.
3. `INCELEME-ROLLERİ.md`: Ayrı agentlara verilebilecek dört görev.
4. `KURULUM-VE-TEST.md`: Ayrı ortamda test ve çalıştırma adımları.
5. `source/`: Kaynaklar, testler, npm kilit dosyası, Python gereksinimleri, masaüstü/motor paketleme tanımları ve rehberler.
6. `evidence/`: Test sonuçları, kabul kayıtları ve ekran görüntüleri. Bunlar önceki çalıştırmaların kanıtlarıdır; bağımsız doğrulama yerine geçmez.

## Gerçek durum

Program Türkçe Electron/React arayüzü ve Python/FastAPI motoruyla Windows'ta çalışır. DEMO örnek veri, PAPER gerçek açık piyasa verisiyle sanal hesaptır. Canlı ve testnet emir gönderimi kapalıdır. Binance/Bybit aktif USDT spot ve sürekli vadeli ürünleri keşfedilir. Son katalog kabulünde 685 farklı sembol / 1.805 borsa-ürün kaydı görülmüştür; dinamik sayılardır.

Ayrıntılı analiz kapanmış 15 dakika / 4 saat mumlarıyla likit coinler arasında 16'lık gruplarda döner. Beş yöntem ailesi sayısal seçicide değerlendirilir. Yerel dil modeli haber/sohbet/araştırma içindir; ağırlıkları eğitilmez ve doğrudan emir yetkisi yoktur. Son kabul kaydında 381 Python testi geçmiştir. Bu kayıt kârlılık veya canlıya hazır olma kanıtı değildir.

## İnceleme paketi ne içermez?

Gerçek kullanıcı veritabanı, cüzdan/işlem geçmişi, API anahtarı, şifreli anahtar deposu, Telegram bilgileri, model ağırlıkları, kişisel model dosyaları, node_modules/.venv, kurulum EXE veya taşınabilir uygulama dahil değildir. Testlerdeki FAKE/TEST anahtar metinleri bilerek bırakılmış test verileridir. Kanıt metinlerindeki kullanıcı dizinleri maskelenmiştir. Kaynak kod baytları, doğrulanmış kaynak ZIP ile aynıdır.

`MANIFEST.json` paket içindeki dosyaların SHA256 özetlerini, kaynak arşivi kimliğini ve kanıtların sürüm bağlamını içerir. Kaynak ZIP'in tamamı tekrar iç içe arşivlenmemiştir; agent doğrudan `source/` dosyalarını okuyabilir.
