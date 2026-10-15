from pathlib import Path
import hashlib
import json
import zipfile

root=Path(__file__).resolve().parent.parent
output=root.parent.parent/'outputs'
version=json.loads((root/'package.json').read_text(encoding='utf-8'))['version']
expected=hashlib.sha256((root/'engine-dist/kripto-engine/kripto-engine.exe').read_bytes()).hexdigest()
for path in (root/f'out/make/squirrel.windows/x64/KriptoTerminali-{version}-full.nupkg',output/'KriptoTerminali-Tasinabilir.zip'):
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        engine=next(n for n in archive.namelist() if n.endswith('resources/kripto-engine/kripto-engine.exe'))
        assert hashlib.sha256(archive.read(engine)).hexdigest()==expected,path
with zipfile.ZipFile(output/'KriptoTerminali-KaynakKod.zip') as archive:
    assert archive.testzip() is None
    names=archive.namelist()
    package=json.loads(archive.read('KriptoTerminali/package.json'))
    assert package['version']==version
    assert 'KriptoTerminali/kripto-engine.spec' in names
    assert all(any(n.endswith('/'+f) for n in names) for f in ('engine/universe.py','engine/scanner_cache.py','src/UniversePanel.tsx','tests/test_universe.py','tests/test_market_catalog.py','scripts/check-universe-engine.cjs','scripts/check-universe-ui.cjs'))
    assert all(any(n.endswith('/'+f) for n in names) for f in ('engine/history.py','engine/knowledge.py','src/ResearchLibrary.tsx','engine/chat.py','src/ChatPanel.tsx','engine/operations.py','engine/exits.py','engine/grounding.py','src/OperationsPanel.tsx','tests/test_operations.py','tests/test_exits.py','tests/test_grounding.py','engine/training.py','engine/diagnostics.py','src/ExecutionStatus.tsx','tests/test_fast_execution.py','tests/test_training.py'))
    assert all(any(n.endswith('/'+f) for n in names) for f in ('engine/state_transaction.py','tests/test_accounting_audit.py','tests/test_review_learning.py','tests/test_review_state.py','tests/test_parent_supervision.py','tests/test_chat_scope.py','scripts/check-review-ui.cjs','scripts/check-parent-binary.cjs','docs/Inceleme-Raporu.md'))
    assert not any(n.endswith(('.db','.enc','.joblib','.gguf')) for n in names)
    assert not any('/.venv/' in n or '/node_modules/' in n for n in names)
    count=len(names)
with (output/'KriptoTerminali-Kurulum.exe').open('rb') as file:
    assert file.read(2)==b'MZ'
manifest=json.loads((output/'SHA256.json').read_text())
for name,details in manifest.items():
    assert hashlib.sha256((output/name).read_bytes()).hexdigest()==details['sha256']
result=dict(installer='valid PE',archives='CRC passed',source_files=count,version=version,
    bundled_engine='matches verified final engine in portable and Squirrel release',hashes='verified')
(root/'artifacts/delivery-results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
