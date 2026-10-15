$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
& '.\.venv\Scripts\python.exe' -m PyInstaller --noconfirm --clean --onedir --name kripto-engine --distpath engine-dist --workpath build\engine --paths . --collect-submodules uvicorn --collect-submodules sklearn --collect-data tzdata --hidden-import pyarrow.vendored.version --hidden-import pyarrow._parquet --hidden-import sklearn.ensemble._hist_gradient_boosting --exclude-module pytest --exclude-module tkinter engine\main.py
if ($LASTEXITCODE -ne 0) { throw 'Motor paketlemesi başarısız.' }
