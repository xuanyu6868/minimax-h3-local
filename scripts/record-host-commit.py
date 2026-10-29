"""Record the host's commit/pagefile configuration read-only.

Nothing here modifies the system: every call is a CIM query. The values are
written to a JSON evidence file together with the exact queries used, so the
numbers can be re-checked without trusting this script.
"""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

QUERY = r"""
$mem = Get-CimInstance Win32_PerfRawData_PerfOS_Memory
$cs  = Get-CimInstance Win32_ComputerSystem
$usage = @(Get-CimInstance Win32_PageFileUsage | Select-Object Name, AllocatedBaseSize, CurrentUsage, PeakUsage)
$setting = @(Get-CimInstance Win32_PageFileSetting | Select-Object Name, InitialSize, MaximumSize)
[ordered]@{
  committed_bytes      = $mem.CommittedBytes
  commit_limit_bytes   = $mem.CommitLimit
  physical_total_bytes = $cs.TotalPhysicalMemory
  automatic_managed    = [bool]$cs.AutomaticManagedPagefile
  pagefile_usage       = $usage
  pagefile_setting     = $setting
} | ConvertTo-Json -Depth 5
"""


def main(out_path):
    raw = subprocess.run(
        ['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', QUERY],
        capture_output=True, text=True, check=True,
    ).stdout
    data = json.loads(raw)
    data['captured_at_utc'] = datetime.now(timezone.utc).isoformat()
    data['source'] = 'CIM: Win32_PerfRawData_PerfOS_Memory, Win32_ComputerSystem, Win32_PageFileUsage, Win32_PageFileSetting'
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    limit = data['commit_limit_bytes'] / 2**20
    phys = data['physical_total_bytes'] / 2**20
    print(json.dumps({
        'out': str(out_path),
        'commit_limit_MiB': round(limit, 1),
        'physical_MiB': round(phys, 1),
        'commit_limit_minus_physical_MiB': round(limit - phys, 1),
        'automatic_managed_pagefile': data['automatic_managed'],
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'reports/evidence/host-commit.json')
