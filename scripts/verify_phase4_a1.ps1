param([switch]$CodeOnly, [string[]]$ReviewedIntegrationFiles = @())
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath ([IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')))
$checkpoint = 'c1e354c'
$allowed = @('src/trading_ecosystem/mt5/client.py', 'tests/mt5/test_boundaries.py')
foreach ($file in $ReviewedIntegrationFiles) {
    if ($file -notin @('dashboard/src/App.tsx', 'dashboard/tests/components.test.tsx', 'scripts/verify_phase4_a.ps1')) {
        throw "Unsupported reviewed integration file: $file"
    }
}
$allowed += $ReviewedIntegrationFiles
$tracked = @(& git ls-tree -r --name-only $checkpoint)
if ($LASTEXITCODE -ne 0 -or -not $tracked.Count) { throw 'Phase 4A checkpoint missing' }
$changed = @(& git diff --name-only $checkpoint -- $tracked)
foreach ($name in $changed) {
    if ($name -notin $allowed) { throw "Unexpected Phase 4A checkpoint change: $name" }
}
& "$PSScriptRoot/verify_phase4_a.ps1" -CodeOnly:$CodeOnly -ReviewedIntegrationFiles $ReviewedIntegrationFiles
if (-not $?) { throw 'Phase 4A regression failed' }
Copy-Item test-results/phase4_a.xml test-results/phase4_a1.xml
if (-not $CodeOnly) {
    & .venv/Scripts/python.exe scripts/verify_phase4_a1_evidence.py
    if ($LASTEXITCODE -ne 0) { throw 'Phase 4A.1 real evidence verification failed' }
}
Write-Output 'PASS: Phase 4A.1 gate; no execution or Phase 4B initiated'
