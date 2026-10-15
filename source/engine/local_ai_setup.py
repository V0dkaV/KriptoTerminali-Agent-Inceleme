"""Pinned public assets; resumable download, SHA256 and bounded ZIP extraction."""
import hashlib
import urllib.request
import zipfile
from engine.local_ai import MODEL_FILE,MODEL_SHA,MODEL_REVISION,SERVER_SHA

RUNTIME_URL='https://github.com/ggml-org/llama.cpp/releases/download/b11655/llama-b11655-bin-win-vulkan-x64.zip'
RUNTIME_SHA='f5a9ec9e6474c89368eca80e849577492fdb4d9482e727c1f1c9acd96c88cade'
MODEL_URL=f'https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/{MODEL_REVISION}/{MODEL_FILE}?download=true'


def install(ai):
    ai.installing=True
    try:
        ai.status='downloading';ai.message='Ücretsiz yerel model indiriliyor; kesilirse kaldığı yerden sürer.'
        ai.assets.mkdir(parents=True,exist_ok=True)
        ai.progress=dict(downloaded=0,total=2497280256,phase='model')
        for url,file,sha in [(MODEL_URL,ai.assets/'models'/MODEL_FILE,MODEL_SHA),(RUNTIME_URL,ai.assets/'runtime.zip',RUNTIME_SHA)]:
            file.parent.mkdir(parents=True,exist_ok=True)
            if file.is_file():
                with file.open('rb') as handle:
                    if hashlib.file_digest(handle,'sha256').hexdigest()==sha:continue
            partial=file.with_suffix(file.suffix+'.partial')
            offset=partial.stat().st_size if partial.exists() else 0
            headers={'User-Agent':'KriptoTerminali/0.3 model-setup'}
            if offset:headers['Range']=f'bytes={offset}-'
            with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=60) as response:
                if response.status!=206:offset=0
                ai.progress=dict(downloaded=offset,total=offset+int(response.headers.get('content-length',0)),phase='model' if file.suffix=='.gguf' else 'runtime')
                with partial.open('ab' if offset else 'wb') as handle:
                    for chunk in iter(lambda:response.read(4*1024*1024),b''):
                        if ai.closing:return
                        handle.write(chunk);ai.progress['downloaded']+=len(chunk)
            ai.message='İndirilen yerel dosya doğrulanıyor.'
            with partial.open('rb') as handle:actual=hashlib.file_digest(handle,'sha256').hexdigest()
            if actual!=sha:raise ValueError('Dosya özeti eşleşmedi; çalıştırılmadı.')
            partial.replace(file)
        runtime=(ai.assets/'runtime').resolve();runtime.mkdir(exist_ok=True)
        with zipfile.ZipFile(ai.assets/'runtime.zip') as archive:
            for member in archive.infolist():
                if not (runtime/member.filename).resolve().is_relative_to(runtime):raise ValueError('Geçersiz arşiv yolu')
            archive.extractall(runtime)
        with (runtime/'llama-server.exe').open('rb') as handle:
            if hashlib.file_digest(handle,'sha256').hexdigest()!=SERVER_SHA:raise ValueError('Çalıştırıcı doğrulanamadı.')
        ai.status='ready_to_load';ai.message='Yerel model kuruldu; ilk analizde belleğe yüklenecek.'
    except Exception:
        ai.status='error';ai.message='Model kurulumu tamamlanamadı. Yeniden indir ile sürdürülebilir.'
    finally:ai.installing=False
