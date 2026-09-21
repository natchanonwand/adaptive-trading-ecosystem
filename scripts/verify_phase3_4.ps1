param([switch]$CodeOnly)
$ErrorActionPreference = 'Stop'
$workspace = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Set-Location -LiteralPath $workspace
if (-not $env:TE_TEST_DATABASE_URL) { throw 'Set TE_TEST_DATABASE_URL for fresh PostgreSQL regression' }
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { throw 'uv must be on PATH' }

function Get-Phase34EvidenceHashes {
    $hashes = @{}
    foreach ($root in @('data/datasets', 'data/research')) {
        if (-not (Test-Path -LiteralPath $root)) { throw "Missing frozen evidence root: $root" }
        foreach ($file in (Get-ChildItem -LiteralPath $root -File -Recurse)) {
            $relative = [IO.Path]::GetRelativePath($workspace, $file.FullName)
            $hashes[$relative] = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
        }
    }
    return $hashes
}

if ($CodeOnly) {
    & "$PSScriptRoot/verify_phase3_3b.ps1" -CodeOnly
    if (-not $?) { throw 'Phase 3.4 all-code gate failed' }
    Write-Output 'PASS: Phase 3.4 full suite, including portfolio/risk, scope and PostgreSQL tests'
    return
}

$before = Get-Phase34EvidenceHashes
Write-Output "Frozen evidence baseline captured: $($before.Count) files"
# Existing official gates remain authoritative; their full suites include the new tests.
& "$PSScriptRoot/verify_phase2b.ps1" -DatasetRoot 'data/datasets/20260911T161046Z-ee75c598' -RequireRealDatasets
if (-not $?) { throw 'Phase 2B regression failed' }
& "$PSScriptRoot/verify_phase3_3b.ps1" -RequireResults
if (-not $?) { throw 'Phase 3.3B regression failed' }
& uv run --locked --extra discovery python -m trading_ecosystem.portfolios verify
if ($LASTEXITCODE -ne 0) { throw 'Frozen Phase 3.3C verification failed' }
$after = Get-Phase34EvidenceHashes
if ($before.Count -ne $after.Count) { throw 'Frozen evidence file set changed' }
foreach ($name in $before.Keys) {
    if (-not $after.ContainsKey($name) -or $after[$name] -ne $before[$name]) {
        throw "Frozen evidence bytes changed: $name"
    }
}
& git diff --check
if ($LASTEXITCODE -ne 0) { throw 'Whitespace verification failed' }
Write-Output "PASS: Phase 3.4 complete gate; all $($before.Count) frozen evidence files byte-for-byte unchanged"
