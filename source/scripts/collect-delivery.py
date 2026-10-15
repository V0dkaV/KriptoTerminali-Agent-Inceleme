from pathlib import Path
import hashlib
import json
import shutil
import zipfile

root=Path(__file__).resolve().parent.parent
output=root.parent.parent/'outputs'
output.mkdir(exist_ok=True)
installers=list((root/'out'/'make').rglob('KriptoTerminali-Kurulum.exe'))
if not installers: raise SystemExit('Kurulum paketi bulunamadı.')
shutil.copy2(installers[0],output/'KriptoTerminali-Kurulum.exe')
version=json.loads((root/'package.json').read_text(encoding='utf-8'))['version']
portable=[p for p in (root/'out'/'make'/'zip').rglob('*.zip') if version in p.name]
if not portable: raise SystemExit('Güncel sürümün taşınabilir paketi bulunamadı.')
shutil.copy2(max(portable,key=lambda p:p.stat().st_mtime),output/'KriptoTerminali-Tasinabilir.zip')
exclude={'.venv','node_modules','out','dist','build','engine-dist','artifacts','local-ai','__pycache__','.pytest_cache','.git'}
with zipfile.ZipFile(output/'KriptoTerminali-KaynakKod.zip','w',zipfile.ZIP_DEFLATED) as archive:
    for file in root.rglob('*'):
        if not file.is_file(): continue
        relative=file.relative_to(root)
        if any(part in exclude for part in relative.parts) or file.suffix=='.pyc':continue
        archive.write(file,Path('KriptoTerminali')/relative)
for source,name in [('06-gercek-verili-sanal-oturum.png','KriptoTerminali-Onizleme.png'),('08-anlik-analizler.png','Anlik-Analizler.png'),('03-test-laboratuvari.png','Test-Laboratuvari.png'),('09-yerel-ai-haber-arastirma.png','Yerel-AI.png'),('Piyasalar.png','Piyasalar.png'),('10-binance-fiyat-guncelligi.png','Fiyat-Guncelligi.png')]:
    file=root/'artifacts'/source
    if file.exists():shutil.copy2(file,output/name)
for source,name in [('11-sade-gercek-piyasa.png','KriptoTerminali-Onizleme.png'),('history-real-12m.png','Bir-Yillik-Grafik.png'),('history-real-6m.png','Alti-Aylik-Grafik.png'),('research-library.png','Analiz-Kutuphanesi.png'),('presentation-pro-1440.png','Pro-Gorunum-Demo.png')]:
    file=root/'artifacts'/source
    if file.exists():shutil.copy2(file,output/name)
for file in ('README.md','THIRD_PARTY_NOTICES.md'):
    shutil.copy2(root/file,output/file)
for file in ('Kullanim-Kilavuzu.md','Analiz-Kutuphanesi.md','Inceleme-Raporu.md','Genis-Piyasa-Radari.md'):
    shutil.copy2(root/'docs'/file,output/file)
paper=json.loads((root/'artifacts/paper-results.json').read_text(encoding='utf-8'))
agents=json.loads((root/'artifacts/agents-results.json').read_text(encoding='utf-8'))
assert paper['version'] in (version,'0.7.2')
chat_ui=json.loads((root/'artifacts/chat-ui-results.json').read_text(encoding='utf-8'))
chat_model=json.loads((root/'artifacts/chat-model-results.json').read_text(encoding='utf-8'))
assert chat_ui['version'] in (version,'0.7.0') and chat_model['version'] in (version,'0.7.0')
evidence=dict(version=version,observed_at=paper['time'],virtual_balance=paper['balance'],
              watchlist=paper['settings']['allowlist'],quotes=paper['quotes'],streams=paper['streams'],
              analysis_count=len(paper['analyses']),analyzed_symbols=sorted({r['symbol'] for r in paper['analyses']}),
              risk_settings={k:paper['settings'][k] for k in ('risk_profile','trade_risk','total_risk','daily_loss','drawdown','leverage','max_positions','symbol_risk','correlated_risk')},
              local_ai=dict(baseline_version=agents['version'],model=agents['localAI']['model'],observed_at=agents['time'],report=agents['localAI']['report'],experiments=agents['localAI']['experiments']),
              chat=dict(ui=chat_ui,local_model=chat_model),
              package_checks=json.loads((root/'artifacts/package-results.json').read_text(encoding='utf-8')))
for key,name in [('history_checks','history-results.json'),('history_ui','history-ui-results.json'),('presentation','presentation-results.json'),('library_ui','library-ui-results.json')]:
    evidence[key]=json.loads((root/'artifacts'/name).read_text(encoding='utf-8'))
for source,name in [('chat-empty-sade-1440.png','AI-Sohbet-Ekrani.png'),('chat-real-local-ai.png','AI-Sohbet-Yerel-Model.png'),('chat-sade-1280.png','AI-Sohbet-Onay-Karti.png')]:
    file=root/'artifacts'/source
    if file.exists():shutil.copy2(file,output/name)
operations=json.loads((root/'artifacts/operations-ui-results.json').read_text(encoding='utf-8'))
assert operations['version'] in (version,'0.7.0') and not operations['errors']
evidence['operations_ui']=operations
evidence['operations_real_market']=paper['operations']
execution=json.loads((root/'artifacts/execution-status-results.json').read_text(encoding='utf-8'))
assert execution['version']==version and not execution['errors']
evidence['execution_status']=execution
evidence['execution_market']=dict(timing=paper['timing'],status=paper['execution'],trained_contexts=paper['trainedContexts'],runtime='packaged Windows' if paper.get('packaged') else 'source Electron with current Python engine')
for key,name in [('review_ui','review-ui-results.json'),('parent_binary','parent-binary-results.json'),('learning_review','review-learning-evidence.json')]:
    evidence[key]=json.loads((root/'artifacts'/name).read_text(encoding='utf-8'))
assert evidence['review_ui']['version'] in (version,'0.7.2') and not evidence['review_ui']['errors']
assert evidence['parent_binary']['version'] in (version,'0.7.2')
for key,name in [('universe_catalog','catalog-public-results.json'),('universe_engine','universe-engine-results.json'),('universe_ui','universe-ui-results.json')]:
    evidence[key]=json.loads((root/'artifacts'/name).read_text(encoding='utf-8'))
    assert evidence[key]['version']==version
evidence['baseline_note']='0.8.0 katalog, geniş havuz motoru, geniş havuz UI, eğitim/analiz durumu ve paket kabulü günceldir. Önceki 24 coinli tam piyasa koşusu, ayrıntılı muhasebe/araştırma UI, sahiplik, sohbet modeli, uzun grafik ve fiyat kayıtları kendi sürüm/tarihleriyle korunan önceki kabul kanıtlarıdır. Öğrenme incelemesindeki önce kaydı 0.7.1 kaynak arşivini tanımlar.'
for source,name in [('universe-real-public.png','Genis-Coin-Havuzu.png'),('universe-real-public.png','KriptoTerminali-Onizleme.png'),('universe-paused-mission.png','Gorev-Onayi-Durumu.png')]:
    shutil.copy2(root/'artifacts'/source,output/name)
for source,name in [('review-legacy-report-1280.png','Eski-Rapor-Uyarisi.png'),('review-effective-caps.png','Etkin-Gorev-Sinirlari.png')]:
    shutil.copy2(root/'artifacts'/source,output/name)
shutil.copy2(root/'artifacts/execution-status-sade-1280.png',output/'Islem-Neden-Bekliyor.png')
for source,name in [('operations-real-market.png','Islem-Merkezi.png'),('operations-mission-preview.png','Gorev-Onay-Plani.png')]:
    shutil.copy2(root/'artifacts'/source,output/name)
(output/'Gercek-Veri-Dogrulamasi.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
price_check=root/'artifacts/price-results.json'
if price_check.exists():
    evidence['price_feed_check']=json.loads(price_check.read_text(encoding='utf-8'))
    (output/'Gercek-Veri-Dogrulamasi.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
manifest={file.name:dict(bytes=file.stat().st_size,sha256=hashlib.sha256(file.read_bytes()).hexdigest())
          for file in output.iterdir() if file.is_file() and file.suffix in ('.exe','.zip')}
(output/'SHA256.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print(json.dumps(manifest,indent=2))
