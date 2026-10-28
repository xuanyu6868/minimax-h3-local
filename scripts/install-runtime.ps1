$ErrorActionPreference = 'Stop'
$Root = 'D:\AI\MiniMaxH3'
$Comfy = Join-Path $Root 'ComfyUI'
$Venv = Join-Path $Root '.venv'
$Commit = '63be2f9b82ad0dac88a7ceaa28a9cf3154125a18'

if (-not (Test-Path $Root)) { New-Item -ItemType Directory -Path $Root | Out-Null }
if (-not (Test-Path $Comfy)) {
    git clone --filter=blob:none --no-checkout https://github.com/Comfy-Org/ComfyUI.git $Comfy
    if ($LASTEXITCODE -ne 0) { throw 'ComfyUI clone failed' }
}
$Actual = git -C $Comfy rev-parse HEAD
if ($LASTEXITCODE -ne 0 -or $Actual -ne $Commit) {
    throw "Expected ComfyUI $Commit, found $Actual. No update or reset was performed."
}
if (-not (Test-Path (Join-Path $Comfy 'main.py'))) {
    git -C $Comfy checkout --detach $Commit
    if ($LASTEXITCODE -ne 0) { throw 'ComfyUI checkout failed' }
}
if (-not (Test-Path (Join-Path $Venv 'Scripts\python.exe'))) {
    uv venv --python 3.12 $Venv
    if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed' }
}
$Python = Join-Path $Venv 'Scripts\python.exe'
uv pip install --python $Python torch==2.10.0 torchvision==0.25.0 torchaudio==2.10.0 --index-url https://download.pytorch.org/whl/cu130
if ($LASTEXITCODE -ne 0) { throw 'CUDA PyTorch installation failed' }
# --no-deps is required: requirements.txt lists an unpinned torch, which would
# replace the CUDA build above with the default PyPI build.
uv pip install --python $Python --no-deps -r (Join-Path $Comfy 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'ComfyUI dependency installation failed' }
& $Python -c "import torch; assert torch.cuda.is_available(), 'CUDA build was replaced'; print(torch.__version__, torch.version.cuda)"
if ($LASTEXITCODE -ne 0) { throw 'CUDA PyTorch verification after dependency install failed' }
uv pip freeze --python $Python | Out-File -Encoding utf8 (Join-Path $Root 'installed-freeze.txt')
Write-Output "Runtime ready: $Root"
