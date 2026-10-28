$ErrorActionPreference = 'Stop'
$Root = 'D:\AI\MiniMaxH3'
$Python = Join-Path $Root '.venv\Scripts\python.exe'
$Main = Join-Path $Root 'ComfyUI\main.py'
if (-not (Test-Path $Python) -or -not (Test-Path $Main)) {
    throw 'Isolated runtime is missing; run install-runtime.ps1 first.'
}
& $Python $Main --listen 127.0.0.1 --port 8188 --disable-auto-launch
exit $LASTEXITCODE
