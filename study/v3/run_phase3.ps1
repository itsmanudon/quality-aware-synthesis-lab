# Launch the remaining Study v3 Phase 3 jobs as independent background processes.
# Run from a normal PowerShell window (outside Claude Code), in the repo root:
#   powershell -ExecutionPolicy Bypass -File study\v3\run_phase3.ps1
# Every job resumes from its last finished unit and claims units with lock files, so running
# this again (or after a reboot) never repeats or corrupts work. Logs: study\v3\runs\phase3\*.log
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $repo
$bash = "C:\Program Files\Git\bin\bash.exe"
$runs = "study\v3\runs\phase3"
function Start-Job2($name, $cmd) {
    $log = Join-Path $runs "$name.log"
    Start-Process -FilePath $bash -ArgumentList @("-c", "cd '$($repo -replace '\','/')' && $cmd >> '$($log -replace '\','/')' 2>&1") -WindowStyle Hidden
    Write-Host "started $name -> $log"
}
Start-Job2 "u2-gen" "study/v3/vendor/.venv-u2/Scripts/python.exe -I study/v3/u3_pools.py --jobs study/v3/runs/phase3/u2/jobs.json --out study/v3/runs/phase3/u2 --device cpu"
Start-Job2 "curate-forward" "bash study/v3/curate_worker.sh forward"
Start-Job2 "curate-reverse" "bash study/v3/curate_worker.sh reverse"
Start-Job2 "eval-primary-1" "bash study/v3/eval_worker.sh primary"
Start-Job2 "eval-primary-2" "bash study/v3/eval_worker.sh primary"
Start-Job2 "eval-rest-1" "bash study/v3/eval_worker.sh rest"
Write-Host "6 jobs started. Progress: study\v3\runs\phase3\{u2,curated,eval-primary,eval-rest}\units"
