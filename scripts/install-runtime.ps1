param(
    [string]$Root = 'D:\AI\MiniMaxH3',
    [string]$ComfyCommit = '63be2f9b82ad0dac88a7ceaa28a9cf3154125a18',
    [switch]$PlanOnly,
    [switch]$Relock
)
$ErrorActionPreference = 'Stop'
$Comfy = Join-Path $Root 'ComfyUI'
$Venv = Join-Path $Root '.venv'
$TorchIndex = 'https://download.pytorch.org/whl/cu130'
$TorchSpec = @(
    'torch==2.10.0+cu130',
    'torchvision==0.25.0+cu130',
    'torchaudio==2.10.0+cu130'
)

function Get-Head([string]$Repo) {
    $value = & git -C $Repo rev-parse HEAD 2>$null
    if ($LASTEXITCODE -ne 0) { return $null }
    return $value
}

if (-not (Test-Path $Root)) { New-Item -ItemType Directory -Path $Root | Out-Null }

# 1) Clone only when the directory is absent or empty. Never clone into, reset,
#    or discard an existing directory.
if (Test-Path $Comfy) {
    $existingHead = Get-Head $Comfy
    if (-not $existingHead) {
        throw "Existing directory is not a usable git repo: $Comfy. Move it away manually; nothing was changed."
    }
    $dirty = & git -C $Comfy status --porcelain
    if ($LASTEXITCODE -ne 0) { throw "Cannot inspect git status in $Comfy" }
    if ($dirty) {
        throw "Existing checkout has local changes; refusing to reset. Review or move them: $Comfy"
    }
    if ($existingHead -ne $ComfyCommit) {
        throw "Existing checkout is at $existingHead, expected $ComfyCommit. Refusing to change it automatically."
    }
} else {
    if ($PlanOnly) {
        Write-Output "[plan] git clone --filter=blob:none https://github.com/Comfy-Org/ComfyUI.git $Comfy"
    } else {
        git clone --filter=blob:none https://github.com/Comfy-Org/ComfyUI.git $Comfy
        if ($LASTEXITCODE -ne 0) { throw 'ComfyUI clone failed' }
    }
}

# 2) Check out the pinned commit when it is not already HEAD. This must run before
#    the HEAD assertion, otherwise a fresh clone can never reach a matching state.
$head = if (Test-Path $Comfy) { Get-Head $Comfy } else { $null }
if ($head -ne $ComfyCommit) {
    if ($PlanOnly) {
        Write-Output "[plan] git -C $Comfy checkout --detach $ComfyCommit"
    } else {
        git -C $Comfy fetch --depth 1 origin $ComfyCommit
        if ($LASTEXITCODE -ne 0) { throw 'Fetching the pinned commit failed' }
        git -C $Comfy checkout --detach $ComfyCommit
        if ($LASTEXITCODE -ne 0) { throw 'ComfyUI checkout failed' }
    }
}

# 3) Verify HEAD only after checkout has had a chance to run.
if (-not $PlanOnly) {
    $finalHead = Get-Head $Comfy
    if ($finalHead -ne $ComfyCommit) {
        throw "HEAD verification failed: $finalHead != $ComfyCommit"
    }
    Write-Output "ComfyUI HEAD verified at $finalHead"
}

if (-not (Test-Path (Join-Path $Venv 'Scripts\python.exe'))) {
    if ($PlanOnly) {
        Write-Output "[plan] uv venv --python 3.12 $Venv"
    } else {
        uv venv --python 3.12 $Venv
        if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed' }
    }
}
if ($PlanOnly) {
    Write-Output "[plan] uv pip install $($TorchSpec -join ' ') --index-url $TorchIndex"
    Write-Output "[plan] uv pip compile requirements (pinned to the installed torch/cu130 constraints)"
    Write-Output '[plan] uv pip sync the compiled lock file, then assert torch CUDA availability'
    exit 0
}

$Python = Join-Path $Venv 'Scripts\python.exe'

# 4) Prefer the lock file that was verified against this environment. Only
#    -Relock re-resolves from requirements.txt, and that is an explicit action.
$verifiedLock = Join-Path $Root 'requirements.lock.txt'
$lock = Join-Path $Root 'requirements.lock.txt'

if ($Relock -or -not (Test-Path $verifiedLock)) {
    uv pip install --python $Python @TorchSpec --index-url $TorchIndex
    if ($LASTEXITCODE -ne 0) { throw 'CUDA PyTorch installation failed' }
    $constraints = Join-Path $Root 'torch-constraints.txt'
    ($TorchSpec -join "`n") | Out-File -Encoding utf8 $constraints
    uv pip compile (Join-Path $Comfy 'requirements.txt') --python $Python `
        --constraint $constraints --extra-index-url $TorchIndex --output-file $lock
    if ($LASTEXITCODE -ne 0) { throw 'Resolving a pinned lock file failed' }
} else {
    Write-Output "Using verified lock file: $verifiedLock"
}

uv pip sync --python $Python $lock --extra-index-url $TorchIndex
if ($LASTEXITCODE -ne 0) { throw 'Applying the lock file failed' }

# 5) Fail loudly if the CUDA build was replaced by a dependency resolution.
& $Python -c "import torch; assert torch.cuda.is_available(), 'CUDA build was replaced'; print(torch.__version__, torch.version.cuda)"
if ($LASTEXITCODE -ne 0) { throw 'CUDA PyTorch verification after dependency install failed' }

uv pip freeze --python $Python | Out-File -Encoding utf8 (Join-Path $Root 'installed-freeze.txt')
Write-Output "Runtime ready: $Root"
