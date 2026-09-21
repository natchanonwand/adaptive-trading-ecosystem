param([switch]$CodeOnly)
$ErrorActionPreference = 'Stop'
$workspace = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Set-Location -LiteralPath $workspace

function Get-Phase34BaselineHashes {
    $paths = @(
        'src/trading_ecosystem/accounting', 'src/trading_ecosystem/portfolio',
        'src/trading_ecosystem/risk', 'tests/accounting', 'tests/phase34'
    )
    $files = @('PHASE3_4_REPORT.md', 'docs/PHASE3_4_PORTFOLIO_RISK_ENGINE.md',
        'scripts/verify_phase3_4.ps1', 'scripts/verify_phase3_4a.ps1',
        'tests/integration/test_phase34_pipeline.py')
    foreach ($path in $paths) {
        $files += Get-ChildItem -LiteralPath $path -File -Filter '*.py' |
            ForEach-Object { [IO.Path]::GetRelativePath($workspace, $_.FullName) }
    }
    $hashes = @{}
    foreach ($file in $files) {
        $hashes[$file] = (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash
    }
    if ($hashes.Count -ne 24) { throw 'Expected the 24 preserved Phase 3.4 files' }
    return $hashes
}

$before = Get-Phase34BaselineHashes
Write-Output "Phase 3.4 baseline captured: $($before.Count) files"
# The unchanged Phase 3.4 verifier runs the entire suite, PostgreSQL, lint, typing,
# secrets, Phase 2B real data, Phase 3.3B/3.3C evidence and 874-file hash comparison.
& "$PSScriptRoot/verify_phase3_4.ps1" -CodeOnly:$CodeOnly
if (-not $?) { throw 'Phase 3.5 regression gate failed' }
$after = Get-Phase34BaselineHashes
foreach ($name in $before.Keys) {
    if (-not $after.ContainsKey($name) -or $before[$name] -ne $after[$name]) {
        throw "Preserved Phase 3.4 file changed: $name"
    }
}
if ($before.Count -ne $after.Count) { throw 'Phase 3.4 file set changed' }
[xml]$results = Get-Content -LiteralPath 'test-results/phase3_3b.xml' -Raw
$suite = $results.testsuites.testsuite
if ([int]$suite.failures -or [int]$suite.errors -or [int]$suite.skipped) {
    throw 'The complete regression must have zero failures, errors or skips'
}
Copy-Item -LiteralPath 'test-results/phase3_3b.xml' -Destination 'test-results/phase3_5.xml'
Write-Output "PASS: Phase 3.5; $($suite.tests) tests; all 24 Phase 3.4 files unchanged"
if ($CodeOnly) {
    Write-Output 'CodeOnly does not verify historical dataset/research evidence'
} else {
    Write-Output 'PASS: Phase 3.5 full gate, including frozen historical evidence verification'
}
