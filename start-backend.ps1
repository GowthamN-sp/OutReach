$ErrorActionPreference = 'Stop'
Set-Location "$PSScriptRoot\backend"
$envDir = '.venv'
if (Test-Path "$envDir\Scripts\python.exe") {
    try {
        & "$envDir\Scripts\python.exe" --version 2>$null
        if ($LASTEXITCODE -ne 0) { $envDir = '.venv-v2' }
    } catch { $envDir = '.venv-v2' }
}
if (-not (Test-Path "$envDir\Scripts\python.exe")) {
    python -m venv $envDir
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
$python = (Resolve-Path "$envDir\Scripts\python.exe").Path
& $python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
& $python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --no-access-log
