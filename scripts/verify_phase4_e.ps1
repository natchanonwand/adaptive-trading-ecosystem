param([switch]$CodeOnly)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath ([IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')))
$checkpoint = '4ce8a06'
$tracked = @(& git ls-tree -r --name-only $checkpoint)
if ($LASTEXITCODE -ne 0 -or -not $tracked.Count) { throw 'Phase 4D checkpoint missing' }
$changed = @(& git diff --name-only $checkpoint -- $tracked)
if ($LASTEXITCODE -ne 0 -or $changed.Count) { throw "Frozen Phase 4D files changed: $changed" }
$before = @{}
foreach ($name in $tracked) { $before[$name] = (Get-FileHash -LiteralPath $name).Hash }
& .venv/Scripts/python.exe scripts/verify_phase4_e_evidence.py
if ($LASTEXITCODE -ne 0) { throw 'Phase 4E preservation or read-only audit failed' }
& .venv/Scripts/python.exe -m pytest tests/campaigns tests/integration/test_campaigns.py -q --junitxml=test-results/phase4_e-targeted.xml
if ($LASTEXITCODE -ne 0) { throw 'Phase 4E targeted tests failed' }
# Equivalent Phase 4D checks, excluding its readiness collector, which rewrites
# frozen .local/phase4_d/readiness.json. Do not mutate that prior evidence.
& .venv/Scripts/python.exe -m pytest tests/behavioral_research tests/integration/test_behavioral_research.py -q --junitxml=test-results/phase4_d-targeted.xml
if ($LASTEXITCODE -ne 0) { throw 'Phase 4D targeted regression failed' }
& "$PSScriptRoot/verify_phase4_c.ps1" -CodeOnly:$CodeOnly
if (-not $?) { throw 'Phase 2B through 4C regression failed' }
if (-not $CodeOnly) {
    & .venv/Scripts/python.exe scripts/verify_phase4_d_evidence.py
    if ($LASTEXITCODE -ne 0) { throw 'Frozen Phase 4D research verification failed' }
}
foreach ($name in $tracked) {
    if ((Get-FileHash -LiteralPath $name).Hash -ne $before[$name]) { throw "Frozen file changed: $name" }
}
& .venv/Scripts/python.exe scripts/verify_phase4_e_evidence.py
if ($LASTEXITCODE -ne 0) { throw 'Final preservation check failed' }
& git check-ignore --quiet --no-index '.local/phase4_e/campaigns/ignore-check/manifest.json'
if ($LASTEXITCODE -ne 0) { throw 'Campaign evidence must be Git ignored' }
Copy-Item test-results/phase4_c.xml test-results/phase4_e.xml
Write-Output 'PASS: Phase 4E tooling gate. Real EA campaign qualification is reported separately.'
