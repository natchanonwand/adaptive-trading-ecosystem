param([switch]$CodeOnly)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath ([IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')))
$checkpoint = '6ada091'
$allowed = @('dashboard/src/App.tsx', 'dashboard/tests/components.test.tsx')
$tracked = @(& git ls-tree -r --name-only $checkpoint)
if ($LASTEXITCODE -ne 0 -or -not $tracked.Count) { throw 'Phase 4B checkpoint missing' }
foreach ($name in @(& git diff --name-only $checkpoint -- $tracked)) {
    if ($name -notin $allowed) { throw "Unexpected Phase 4B change: $name" }
}
$before = @{}
foreach ($name in $tracked) { $before[$name] = (Get-FileHash -LiteralPath $name).Hash }
& .venv/Scripts/python.exe -m pytest tests/features tests/integration/test_feature_dataset.py -q --junitxml=test-results/phase4_c-targeted.xml
if ($LASTEXITCODE -ne 0) { throw 'Phase 4C targeted tests failed' }
& "$PSScriptRoot/verify_phase4_b.ps1" -CodeOnly:$CodeOnly
if (-not $?) { throw 'Phase 2B through 4B regression failed' }
foreach ($name in $tracked) {
    if ((Get-FileHash -LiteralPath $name).Hash -ne $before[$name]) { throw "File changed during gate: $name" }
}
Copy-Item test-results/phase4_b.xml test-results/phase4_c.xml
if (-not $CodeOnly) {
    & .venv/Scripts/python.exe scripts/verify_phase4_c_evidence.py
    if ($LASTEXITCODE -ne 0) { throw 'Phase 4C or preserved evidence verification failed' }
}
Write-Output 'PASS: Phase 4C implementation; real EA feature qualification separately NOT PROVIDED'
