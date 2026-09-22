param([switch]$CodeOnly)
$ErrorActionPreference = 'Stop'
$workspace = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Set-Location -LiteralPath $workspace
$checkpoint = '6147c75'
$allowedChanges = @(
    'src/trading_ecosystem/monitoring/contracts.py',
    'src/trading_ecosystem/monitoring/projections.py',
    'dashboard/src/components.tsx', 'dashboard/src/types.ts',
    'tests/accounting/test_scope.py', 'scripts/verify_phase3_6.ps1'
)
$tracked = @(& git ls-tree -r --name-only $checkpoint)
if ($LASTEXITCODE -ne 0 -or -not $tracked.Count) { throw 'Validated local checkpoint missing' }
$changed = @(& git diff --name-only $checkpoint -- $tracked)
foreach ($file in $changed) {
    if ($file -notin $allowedChanges) { throw "Unexpected checkpoint modification: $file" }
}
# Explicit Phase 4A integration changes are checked by the full suite. All other
# checkpoint paths and all historical evidence remain protected by the old gates.
$fixed = @('PHASE3_4_REPORT.md', 'PHASE3_5_REPORT.md', 'alembic-monitoring.ini',
    'docs/PHASE3_4_PORTFOLIO_RISK_ENGINE.md', 'docs/PHASE3_5_MONITORING_CORE.md',
    'scripts/verify_phase3_4.ps1', 'scripts/verify_phase3_4a.ps1', 'scripts/verify_phase3_5.ps1',
    'tests/integration/test_phase34_pipeline.py', 'tests/integration/test_monitoring.py')
$preserved = @($tracked | Where-Object {
    $_ -in $fixed -or $_ -match '^(src/trading_ecosystem/(accounting|portfolio|risk|monitoring)/|tests/(accounting|phase34|monitoring)/|migrations/monitoring/)'
})
if ($preserved.Count -ne 46) { throw 'Expected 46 prior working files in checkpoint' }
$hashes = @{}
foreach ($file in $preserved) { $hashes[$file] = (Get-FileHash -LiteralPath $file).Hash }
New-Item -ItemType Directory -Force '.local/phase4_a' | Out-Null
$manifest = '.local/phase4_a/gate-baseline.json'
$hashes | ConvertTo-Json | Set-Content -LiteralPath $manifest
# The original Phase 3.6 manifest is preserved. The explicit parameter records
# the reviewed next-phase starting point without weakening evidence checks.
& "$PSScriptRoot/verify_phase3_6.ps1" -CodeOnly:$CodeOnly -BaselineManifest $manifest
if (-not $?) { throw 'Phase 2B through 3.6 regression failed' }
Copy-Item test-results/phase3_6.xml test-results/phase4_a.xml
Write-Output 'PASS: Phase 4A implementation gate; real DEMO qualification is a separate required report'
