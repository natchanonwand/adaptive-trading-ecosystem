param([switch]$CodeOnly)
$ErrorActionPreference = 'Stop'
$workspace = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Set-Location -LiteralPath $workspace
if (-not $env:TE_TEST_DATABASE_URL) { throw 'Set TE_TEST_DATABASE_URL for PostgreSQL tests' }
function Get-PreservedHashes {
    $files = @('PHASE3_4_REPORT.md', 'PHASE3_5_REPORT.md', 'alembic-monitoring.ini',
        'docs/PHASE3_4_PORTFOLIO_RISK_ENGINE.md', 'docs/PHASE3_5_MONITORING_CORE.md',
        'scripts/verify_phase3_4.ps1', 'scripts/verify_phase3_4a.ps1',
        'scripts/verify_phase3_5.ps1', 'tests/integration/test_phase34_pipeline.py',
        'tests/integration/test_monitoring.py')
    foreach ($path in @('src/trading_ecosystem/accounting', 'src/trading_ecosystem/portfolio',
        'src/trading_ecosystem/risk', 'src/trading_ecosystem/monitoring',
        'tests/accounting', 'tests/phase34', 'tests/monitoring', 'migrations/monitoring')) {
        $files += Get-ChildItem -LiteralPath $path -Recurse -File |
            Where-Object { $_.FullName -notmatch '__pycache__' } |
            ForEach-Object { [IO.Path]::GetRelativePath($workspace, $_.FullName).Replace('\', '/') }
    }
    $hashes = @{}
    foreach ($file in $files) { $hashes[$file] = (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash }
    if ($hashes.Count -ne 46) { throw "Expected 46 preserved files; found $($hashes.Count)" }
    return $hashes
}
$before = Get-PreservedHashes
if (Test-Path -LiteralPath '.local/phase3_6/baseline.json') {
    $original = Get-Content -LiteralPath '.local/phase3_6/baseline.json' -Raw | ConvertFrom-Json -AsHashtable
    if ($original.Count -ne $before.Count) { throw 'Original working baseline file count changed' }
    foreach ($file in $original.Keys) {
        if ($before[$file] -ne $original[$file]) { throw "Original working baseline changed: $file" }
    }
}
New-Item -ItemType Directory -Force -Path 'test-results' | Out-Null
Push-Location -LiteralPath 'dashboard'
try {
    & npm.cmd ci
    if ($LASTEXITCODE -ne 0) { throw 'Locked frontend install failed' }
    foreach ($task in @('typecheck', 'lint', 'format')) {
        & npm.cmd run $task
        if ($LASTEXITCODE -ne 0) { throw "Frontend $task failed" }
    }
    & npm.cmd run test -- --reporter=default --reporter=junit --outputFile.junit=../test-results/phase3_6-frontend.xml
    if ($LASTEXITCODE -ne 0) { throw 'Frontend tests failed' }
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend production build failed' }
} finally { Pop-Location }
# Preserve the existing trusted verifier composition and its real evidence checks.
& "$PSScriptRoot/verify_phase3_5.ps1" -CodeOnly:$CodeOnly
if (-not $?) { throw 'Phase 3.5 regression failed' }
$after = Get-PreservedHashes
foreach ($file in $before.Keys) {
    if ($after[$file] -ne $before[$file]) { throw "Preserved file changed: $file" }
}
Copy-Item -LiteralPath 'test-results/phase3_5.xml' -Destination 'test-results/phase3_6.xml'
Write-Output 'PASS: Phase 3.6 frontend and backend gates; 46 prior working files unchanged'
if ($CodeOnly) { Write-Output 'CodeOnly: historical evidence verification excluded' }
else { Write-Output 'PASS: Phase 3.6 full gate, including frozen historical evidence' }
