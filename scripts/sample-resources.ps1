param(
    [string]$OutFile = 'D:\AI\MiniMaxH3\samples\resource-samples.csv',
    [int]$IntervalSeconds = 2,
    [string]$PidFile = 'D:\AI\MiniMaxH3\comfyui.pid'
)
$ErrorActionPreference = 'Stop'
$dir = Split-Path $OutFile -Parent
if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }

"timestamp,gpu_used_MiB,gpu_total_MiB,gpu_util_pct,comfy_ws_MiB,comfy_private_MiB,os_free_MiB,os_commit_MiB" |
    Out-File -Encoding utf8 -Append $OutFile

while ($true) {
    $gpu = (& nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv,noheader,nounits) -split ',\s*'
    $os = Get-CimInstance Win32_OperatingSystem
    $ws = ''; $priv = ''
    if (Test-Path $PidFile) {
        $target = Get-Content $PidFile -ErrorAction SilentlyContinue
        $proc = Get-Process -Id $target -ErrorAction SilentlyContinue
        if ($proc) {
            $ws = [math]::Round($proc.WorkingSet64 / 1MB, 1)
            $priv = [math]::Round($proc.PrivateMemorySize64 / 1MB, 1)
        }
    }
    $freeMb = [math]::Round($os.FreePhysicalMemory / 1KB, 1)
    $commitMb = [math]::Round(($os.TotalVirtualMemorySize - $os.FreeVirtualMemory) / 1KB, 1)
    $line = "{0},{1},{2},{3},{4},{5},{6},{7}" -f (Get-Date -Format o), $gpu[0], $gpu[1], $gpu[2], $ws, $priv, $freeMb, $commitMb
    $line | Out-File -Encoding utf8 -Append $OutFile
    Start-Sleep -Seconds $IntervalSeconds
}
