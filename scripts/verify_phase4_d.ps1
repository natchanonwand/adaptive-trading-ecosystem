param([switch]$CodeOnly)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath ([IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')))
$checkpoint = '90e9091'
$allowed = @('dashboard/src/App.tsx')
$tracked = @(& git ls-tree -r --name-only $checkpoint)
if ($LASTEXITCODE -ne 0 -or -not $tracked.Count) { throw 'Phase 4C checkpoint missing' }
foreach ($name in @(& git diff --name-only $checkpoint -- $tracked)) {
    if ($name -notin $allowed) { throw "Unexpected Phase 4C change: $name" }
}
$before = @{}
foreach ($name in $tracked) { $before[$name] = (Get-FileHash -LiteralPath $name).Hash }
& .venv/Scripts/python.exe -m pytest tests/behavioral_research tests/integration/test_behavioral_research.py -q --junitxml=test-results/phase4_d-targeted.xml
if ($LASTEXITCODE -ne 0) { throw 'Phase 4D targeted tests failed' }
& "$PSScriptRoot/verify_phase4_c.ps1" -CodeOnly:$CodeOnly
if (-not $?) { throw 'Phase 2B through 4C regression failed' }
foreach ($name in $tracked) {
    if ((Get-FileHash -LiteralPath $name).Hash -ne $before[$name]) { throw "File changed during gate: $name" }
}
Copy-Item test-results/phase4_c.xml test-results/phase4_d.xml
if (-not $CodeOnly) {
    & .venv/Scripts/python.exe scripts/verify_phase4_d_evidence.py
    if ($LASTEXITCODE -ne 0) { throw 'Phase 4D or preserved evidence verification failed' }
    & .venv/Scripts/python.exe scripts/collect_phase4_d_readiness.py
    if ($LASTEXITCODE -ne 0) { throw 'Readiness metadata collection failed' }
}
Write-Output 'PASS: Phase 4D implementation; real EA research qualification separately NOT PROVIDED'
