param([switch]$CodeOnly, [switch]$RequireResults)
$ErrorActionPreference = 'Stop'
$workspace = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Set-Location -LiteralPath $workspace
if (-not $env:TE_TEST_DATABASE_URL) { throw 'Set TE_TEST_DATABASE_URL for fresh PostgreSQL regression' }
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { throw 'uv must be on PATH' }
& uv sync --locked --extra discovery
if ($LASTEXITCODE -ne 0) { throw 'Locked dependency sync failed' }
New-Item -ItemType Directory -Force -Path 'test-results' | Out-Null
# All prior-phase tests use synthetic fixtures; the integration fixture creates a fresh database.
& uv run --locked --extra discovery pytest -q -p no:cacheprovider --junitxml=test-results/phase3_3c.xml
if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
# The full suite above includes tests/portfolios/test_scope.py and prior safety checks.
& uv run --locked --extra discovery ruff check .
if ($LASTEXITCODE -ne 0) { throw 'Ruff failed' }
& uv run --locked --extra discovery ruff format --check .
if ($LASTEXITCODE -ne 0) { throw 'Format failed' }
& uv run --locked --extra discovery mypy
if ($LASTEXITCODE -ne 0) { throw 'Strict mypy failed' }
& uv run --locked --extra discovery python scripts/secret_scan.py
if ($LASTEXITCODE -ne 0) { throw 'Secret scan failed' }
& uv run --locked --extra discovery python -m trading_ecosystem.benchmarks.hashing
if ($LASTEXITCODE -ne 0) { throw 'Registry artifact verification failed' }
& git diff --check
if ($LASTEXITCODE -ne 0) { throw 'Whitespace failed' }
Write-Output 'PASS: Phase 3.3C code and deterministic synthetic replay, prior-phase tests, fresh PostgreSQL and scope/safety checks'



if (-not $CodeOnly) {
    & uv run --locked --extra discovery python scripts/verify_phase3_3b_evidence.py
    if ($LASTEXITCODE -ne 0) { throw 'Dataset or research evidence verification failed' }
    & uv run --locked --extra discovery python -m trading_ecosystem.portfolios verify
    if ($LASTEXITCODE -ne 0) { throw 'Portfolio evidence verification failed' }
}

