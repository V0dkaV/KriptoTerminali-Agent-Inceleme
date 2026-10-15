# Ayrı ortamda kurulum ve test

Referans ortam Windows x64, Python 3.12, Electron 44/Forge 8 ve Vite 8'dir. Node gereksinimi kilitli Vite paketinde `^20.19.0 || >=22.12.0`; Node 22.12+ uygun bir geliştirme seçimidir. Bunlar geliştirme adımlarıdır; son kullanıcının EXE kullanımı için Python/Node gerekmez.

ZIP'i yeni bir klasöre aç ve source/ içine gir. PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
npm.cmd ci
$env:KRIPTO_DISABLE_LOCAL_AI = '1'
$env:KRIPTO_DATA_DIR = Join-Path (Get-Location) 'review-data'
.venv\Scripts\python.exe -m pytest -q
npm.cmd run build
```

`evidence/PYTHON-PAKET-SURUMLERI.txt`, kabul ortamındaki paket ad/sürümlerini kişisel dizin bilgisi olmadan listeler. Gerektiğinde bağımsız sanal ortamda daha yakın tekrar üretim için bunu kullan. npm sürümleri package-lock.json içindedir. Referans test sonucu evidence/python-results-v080.txt içindedir; tekrar çalıştırdığın sonucu ayrıca raporla.

## Masaüstü arayüzünü açma

Önce yukarıdaki ortam değişkenlerini aynı terminalde ayarla, sonra `npm.cmd start` çalıştır. KRIPTO_DATA_DIR mutlaka ayrı bir test klasörü olsun. Motor Node ana süreci tarafından başlatılır; doğrudan kimliksiz API bekleme. Yerel dil modelinin kapatılması sayısal strateji eğitimini kapatmaz.

## Hedefli doğrulama

```powershell
.venv\Scripts\python.exe -m pytest tests/test_universe.py tests/test_market_catalog.py -q
.venv\Scripts\python.exe -m pytest tests/test_accounting_audit.py tests/test_review_state.py -q
.venv\Scripts\python.exe -m pytest tests/test_parent_supervision.py tests/test_chat_scope.py -q
node scripts/check-universe-ui.cjs
node scripts/check-universe-engine.cjs --source
```

UI araçları Playwright üzerinden Electron ve bazı fikstürler için kurulu Chrome kullanır. Gerçek piyasa kabul araçları açık Binance/Bybit uç noktalarına ağ erişimi ister; bölgesel erişim, zaman ve liste değişimleri sonucu etkileyebilir. Ağsız test ile gerçek API kabulünü ayrı değerlendir. Bazı yaşam döngüsü ve paket testleri Windows'a özeldir; diğer platformda çalıştırılamayanları hata gizlemeden belirt.

## Windows paketini üretme — inceleme için zorunlu değil

```powershell
.venv\Scripts\python.exe -m PyInstaller --noconfirm --distpath engine-dist --workpath build\engine kripto-engine.spec
npm.cmd run make
```

Çıktılar out/make içindedir. Dağıtım toplama/rapor yazma araçları önceki artifacts kayıtlarına ihtiyaç duyar; inceleme ZIP'i bunları otomatik yeniden oluşturmuş sayılmaz. Kaynak kodu çalıştırmak için ağır kurulum/taşınabilir paket ve dil modeli ağırlığı bu ZIP'e eklenmedi.
