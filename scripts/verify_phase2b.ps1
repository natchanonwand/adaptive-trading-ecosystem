param([string]$DatasetRoot = '', [switch]$RequireRealDatasets)
$ErrorActionPreference = 'Stop'
$workspace = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Set-Location -LiteralPath $workspace
if (-not $env:TE_TEST_DATABASE_URL) { throw 'Set TE_TEST_DATABASE_URL for fresh PostgreSQL regression' }
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { throw 'uv must be on PATH' }
& uv sync --locked --extra discovery
if ($LASTEXITCODE -ne 0) { throw 'Locked dependency sync failed' }
New-Item -ItemType Directory -Force -Path 'test-results' | Out-Null
# The existing integration fixture creates a new database and migrates it on every run.
& uv run --locked --extra discovery pytest -q -p no:cacheprovider --junitxml=test-results/phase2b.xml
if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
& uv run --locked --extra discovery ruff check .
if ($LASTEXITCODE -ne 0) { throw 'Ruff failed' }
& uv run --locked --extra discovery ruff format --check .
if ($LASTEXITCODE -ne 0) { throw 'Format failed' }
& uv run --locked --extra discovery mypy
if ($LASTEXITCODE -ne 0) { throw 'Strict mypy failed' }
& uv run --locked --extra discovery python scripts/secret_scan.py
if ($LASTEXITCODE -ne 0) { throw 'Secret scan failed' }
foreach ($name in @('normalized.parquet','manifest.json','quality.json','chunk-0000.json','metadata.json')) {
    & git check-ignore --quiet --no-index "data/datasets/ignore-check/$name"
    if ($LASTEXITCODE -ne 0) { throw 'Generated evidence is not ignored' }
}
# Synthetic round-trip/hash/lineage verification always runs in pytest above.
# Real evidence verification becomes mandatory when a completed dataset exists.
if (-not $DatasetRoot -and (Test-Path 'data/datasets')) {
    if ($RequireRealDatasets) {
        # Check the newest attempted run, never silently fall back to an older success.
        $latestRun = Get-ChildItem -LiteralPath 'data/datasets' -Directory | Sort-Object Name -Descending | Select-Object -First 1
        if ($latestRun) { $DatasetRoot = $latestRun.FullName }
    } else { $DatasetRoot = 'data/datasets' }
}
if ($RequireRealDatasets -and -not $DatasetRoot) { throw 'Real dataset verification pending: no evidence root' }
if ($DatasetRoot) {
    $verifyArgs = @($DatasetRoot)
    if ($RequireRealDatasets) { $verifyArgs += '--require-all-assets' }
    & uv run --locked --extra discovery python -m trading_ecosystem.datasets.verify @verifyArgs
    if ($LASTEXITCODE -ne 0) { throw 'Dataset verification failed' }
}
& git diff --check
if ($LASTEXITCODE -ne 0) { throw 'Whitespace failed' }
if (-not $DatasetRoot) { Write-Output 'Real ingestion verification pending; this is the code gate only' }
Write-Output 'PASS: Phase 2B code and Phase 1/2A regressions, fresh PostgreSQL, safety, schema and hash checks'
