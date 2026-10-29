param(
    [string]$OutFile = 'D:\AI\MiniMaxH3\samples\resource-samples.csv',
    [int]$IntervalSeconds = 2,
    [string]$PidFile = 'D:\AI\MiniMaxH3\comfyui.pid'
)
$ErrorActionPreference = 'Stop'
$dir = Split-Path $OutFile -Parent
if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }

# committed_MiB / commit_limit_MiB come from the Memory performance counter set,
# which reports the real Windows commit charge. The Win32_OperatingSystem-derived
# value in os_commit_MiB is TotalVirtualMemorySize - FreeVirtualMemory, a different
# quantity, so both are recorded and neither is used as a substitute for the other.
# commit_headroom_MiB and commit_ratio are computed from the same reading, so the
# margin can never be mismatched with a limit measured at another moment.
"timestamp,gpu_used_MiB,gpu_total_MiB,gpu_util_pct,comfy_ws_MiB,comfy_private_MiB,os_free_MiB,os_commit_MiB,committed_MiB,commit_limit_MiB,commit_headroom_MiB,commit_ratio" |
    Out-File -Encoding utf8 -Append $OutFile

while ($true) {
    $gpu = (& nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv,noheader,nounits) -split ',\s*'
    $os = Get-CimInstance Win32_OperatingSystem
    $mem = Get-CimInstance Win32_PerfRawData_PerfOS_Memory
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
    $committedMb = ''; $limitMb = ''; $headroomMb = ''; $ratio = ''
    if ($mem) {
        $committedMb = [math]::Round($mem.CommittedBytes / 1MB, 1)
        $limitMb = [math]::Round($mem.CommitLimit / 1MB, 1)
        $headroomMb = [math]::Round(($mem.CommitLimit - $mem.CommittedBytes) / 1MB, 1)
        $ratio = [math]::Round($mem.CommittedBytes / $mem.CommitLimit, 4)
    }
    $line = "{0},{1},{2},{3},{4},{5},{6},{7},{8},{9},{10},{11}" -f (Get-Date -Format o), $gpu[0], $gpu[1], $gpu[2], $ws, $priv, $freeMb, $commitMb, $committedMb, $limitMb, $headroomMb, $ratio
    $line | Out-File -Encoding utf8 -Append $OutFile
    Start-Sleep -Seconds $IntervalSeconds
}
