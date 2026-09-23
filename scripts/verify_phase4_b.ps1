param([switch]$CodeOnly)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath ([IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')))
$checkpoint = '5f25848'
$allowed = @('dashboard/src/App.tsx', 'dashboard/tests/components.test.tsx', 'scripts/verify_phase4_a.ps1', 'scripts/verify_phase4_a1.ps1')
$tracked = @(& git ls-tree -r --name-only $checkpoint)
if ($LASTEXITCODE -ne 0 -or -not $tracked.Count) { throw 'Phase 4A.1 checkpoint missing' }
foreach ($name in @(& git diff --name-only $checkpoint -- $tracked)) {
    if ($name -notin $allowed) { throw "Unexpected Phase 4A.1 modification: $name" }
}
$hashes = @{}
foreach ($name in $tracked) { $hashes[$name] = (Get-FileHash -LiteralPath $name).Hash }
& .venv/Scripts/python.exe -m pytest tests/observer tests/integration/test_external_observer.py -q --junitxml=test-results/phase4_b-targeted.xml
if ($LASTEXITCODE -ne 0) { throw 'Phase 4B targeted tests failed' }
& "$PSScriptRoot/verify_phase4_a1.ps1" -CodeOnly:$CodeOnly -ReviewedIntegrationFiles @('dashboard/src/App.tsx', 'dashboard/tests/components.test.tsx', 'scripts/verify_phase4_a.ps1')
if (-not $?) { throw 'Phase 4A.1 regression failed' }
foreach ($name in $tracked) {
    if ((Get-FileHash -LiteralPath $name).Hash -ne $hashes[$name]) { throw "Checkpoint changed during gate: $name" }
}
Copy-Item test-results/phase4_a1.xml test-results/phase4_b.xml
if (-not $CodeOnly) {
    & .venv/Scripts/python.exe scripts/verify_phase4_b_evidence.py
    if ($LASTEXITCODE -ne 0) { throw 'Observer evidence verification failed' }
}
Write-Output 'PASS: Phase 4B observer implementation and prior evidence gate; real EA smoke separately classified'
