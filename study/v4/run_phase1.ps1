# Launch the Study v4 Phase 1 audit as independent background workers (outside Claude Code).
#   powershell -ExecutionPolicy Bypass -File study\v4\run_phase1.ps1 [-Workers 5]
# Units are claimed with lock files; re-running resumes. Logs: study\v4\runs\phase1\worker-*.log
param([int]$Workers = 5)
$ErrorActionPreference = "Stop"
$repo = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)).Replace('\', '/')
$bash = "C:\Program Files\Git\bin\bash.exe"
New-Item -ItemType Directory -Force -Path (Join-Path $repo "study/v4/runs/phase1") | Out-Null
foreach ($i in 1..$Workers) {
    $log = "study/v4/runs/phase1/worker-$i.log"
    Start-Process -FilePath $bash -ArgumentList "-c `"cd '$repo' && ./.venv/Scripts/python.exe -W ignore -m study.v4.audit >> '$log' 2>&1`"" -WindowStyle Hidden
    Write-Host "started worker $i -> $log"
    Start-Sleep -Seconds 10
}
