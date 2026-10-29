param(
    [ValidateSet('fl2va', 'ref2va')]
    [string]$ModelSet = 'fl2va',
    # Pinned memory is off by default: measured on this machine it cut the commit
    # peak from 49,345 MiB to 38,245 MiB and raised the minimum commit headroom
    # from 420 MiB to 2,934 MiB, with byte-identical output. -EnablePinnedMemory
    # restores the old behaviour for comparison only.
    [switch]$EnablePinnedMemory,
    [string[]]$ExtraArgs = @(),
    [switch]$StopExisting,
    [string]$PlanDir = 'D:\AI\MiniMaxH3\launches'
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

$memoryArgs = if ($EnablePinnedMemory) { @() } else { @('--disable-pinned-memory') }
$pinnedState = if ($EnablePinnedMemory) { 'enabled (explicit opt-out of the low-memory default)' } else { 'disabled (project default)' }
$comfyArgs = @($Main, '--listen', '127.0.0.1', '--port', '8188',
              '--disable-auto-launch', '--reserve-vram', '1.0') + $memoryArgs + $ExtraArgs
$launch = "$Python $($comfyArgs -join ' ')"
Write-Output "Pinned memory: $pinnedState"
Write-Output "Launch command: $launch"

# Refuse to silently reuse an already-running server: its model set and flags
# are unknown, and the measurements would not belong to this launch.
function Get-ServerPid {
    $owner = Get-NetTCPConnection -LocalPort 8188 -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1 -ExpandProperty OwningProcess
    return $owner
}
$existing = Get-ServerPid
if ($existing) {
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$existing" -ErrorAction SilentlyContinue
    Write-Output "FOUND existing listener on 127.0.0.1:8188 pid=$existing"
    Write-Output "  command line: $($proc.CommandLine)"
    if (-not $StopExisting) {
        throw 'Port 8188 is already in use. Re-run with -StopExisting to replace it, or stop it yourself.'
    }
    Write-Output 'Stopping the existing listener because -StopExisting was passed.'
    Stop-Process -Id $existing -Force
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Milliseconds 500
        if (-not (Get-ServerPid)) { break }
    }
    if (Get-ServerPid) { throw "Port 8188 is still held after stopping pid=$existing" }
    Write-Output 'Port 8188 released.'
}

# Start the server as a child we can identify. The venv launcher spawns a
# child that runs under the base interpreter, so the first python PID is not
# necessarily the process that serves requests; resolve the real one below.
if (-not (Test-Path $PlanDir)) { New-Item -ItemType Directory -Path $PlanDir -Force | Out-Null }
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$logPath = Join-Path $PlanDir "$stamp-$ModelSet.log"
$launcher = Start-Process -FilePath $Python -ArgumentList $comfyArgs -PassThru `
    -WindowStyle Hidden -RedirectStandardOutput $logPath -RedirectStandardError "$logPath.err"
Write-Output "Launched pid=$($launcher.Id), log=$logPath"

$ready = $false
for ($i = 0; $i -lt 240; $i++) {
    Start-Sleep -Seconds 1
    try {
        $stats = (Invoke-WebRequest -Uri 'http://127.0.0.1:8188/system_stats' -TimeoutSec 3 -UseBasicParsing).Content | ConvertFrom-Json
        $ready = $true
        break
    } catch { }
}
if (-not $ready) { throw "Server did not answer /system_stats within 240 s; see $logPath" }

# The serving process is whoever owns the listening socket, not the launcher.
$serverPid = Get-ServerPid
if (-not $serverPid) { throw 'Server answered but no listener PID was found' }
$serverProc = Get-CimInstance Win32_Process -Filter "ProcessId=$serverPid"

$record = [ordered]@{
    captured_at_utc         = (Get-Date).ToUniversalTime().ToString('o')
    model_set               = $ModelSet
    pinned_memory           = $pinnedState
    requested_command       = $launch
    launcher_pid            = $launcher.Id
    server_pid              = $serverPid
    server_started_at       = $serverProc.CreationDate.ToString('o')
    server_command_line     = $serverProc.CommandLine
    server_executable       = (Get-Process -Id $serverPid).Path
    reported_argv           = $stats.system.argv
    comfyui_version         = $stats.system.comfyui_version
    torch_version           = $stats.system.pytorch_version
    python_version          = $stats.system.python_version
    vram_total_mib          = [math]::Round($stats.devices[0].vram_total / 1MB, 1)
    log                     = $logPath
    # Not evidence of anything. The other model set is simply the file that
    # this launch does not load; unload is proven only by VRAM/working-set
    # readings inside the run window.
    other_model_present_on_disk = (Test-Path $OtherPath)
    other_model_file            = $Other
}
$record | ConvertTo-Json -Depth 5 | Set-Content -Encoding utf8 (Join-Path $PlanDir "$stamp-launch.json")
$serverPid | Set-Content (Join-Path $Root 'comfyui.pid')
$record | ConvertTo-Json -Depth 5
