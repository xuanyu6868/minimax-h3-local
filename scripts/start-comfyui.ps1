param(
    [ValidateSet('fl2va', 'ref2va')]
    [string]$ModelSet = 'fl2va'
)
$ErrorActionPreference = 'Stop'
$Root = 'D:\AI\MiniMaxH3'
$Python = Join-Path $Root '.venv\Scripts\python.exe'
$Main = Join-Path $Root 'ComfyUI\main.py'
if (-not (Test-Path $Python) -or (-not (Test-Path $Main))) {
    throw 'Isolated runtime is missing; run install-runtime.ps1 first.'
}

# Only one diffusion model may sit in VRAM at a time. ComfyUI caches every
# loaded checkpoint until it is explicitly unloaded or the process exits, so
# switching model sets requires a fresh process rather than a node change.
$Other = if ($ModelSet -eq 'fl2va') { 'minimax_h3_ref2va_pruned_w6a8.safetensors' } else { 'minimax_h3_fl2va_pruned_w6a8.safetensors' }
$OtherPath = Join-Path $Root "ComfyUI\models\diffusion_models\$Other"

$comfyArgs = @($Main, '--listen', '127.0.0.1', '--port', '8188',
              '--disable-auto-launch', '--reserve-vram', '1.0')
$launch = "$Python $($comfyArgs -join ' ')"
Write-Output "Model set: $ModelSet"
Write-Output "Launch command: $launch"
$record = [ordered]@{
    captured_at_utc = (Get-Date).ToUniversalTime().ToString('o')
    model_set       = $ModelSet
    comfyui_commit  = (& git -C (Join-Path $Root 'ComfyUI') rev-parse HEAD)
    python          = (& $Python -c "import sys; print(sys.version.split()[0])")
    torch           = (& $Python -c "import torch; print(torch.__version__)")
    launch_command  = $launch
    unloaded_model  = $Other
    unloaded_size   = if (Test-Path $OtherPath) { (Get-Item $OtherPath).Length } else { $null }
}
$record | ConvertTo-Json -Depth 4 | Set-Content -Encoding utf8 (Join-Path $Root 'launch-args.json')

& $Python @comfyArgs
exit $LASTEXITCODE
