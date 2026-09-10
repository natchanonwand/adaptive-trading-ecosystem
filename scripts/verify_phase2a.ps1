$ErrorActionPreference = 'Stop'
$env:PATH = "$env:USERPROFILE\.local\bin;$env:PATH"
$workspace = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Set-Location -LiteralPath $workspace
if (-not $env:TE_TEST_DATABASE_URL) { throw 'Set TE_TEST_DATABASE_URL for isolated PostgreSQL tests' }
New-Item -ItemType Directory -Force -Path 'test-results' | Out-Null
& uv sync --locked --extra discovery
if ($LASTEXITCODE -ne 0) { throw 'Locked dependency sync failed' }
& uv run --locked --extra discovery pytest -q -p no:cacheprovider --junitxml=test-results/phase2a.xml
if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
& uv run --locked --extra discovery ruff check .
if ($LASTEXITCODE -ne 0) { throw 'Ruff lint failed' }
& uv run --locked --extra discovery ruff format --check .
if ($LASTEXITCODE -ne 0) { throw 'Ruff format failed' }
& uv run --locked --extra discovery mypy
if ($LASTEXITCODE -ne 0) { throw 'mypy failed' }
& uv run --locked --extra discovery python scripts/secret_scan.py
if ($LASTEXITCODE -ne 0) { throw 'Secret scan failed' }
& git diff --check
if ($LASTEXITCODE -ne 0) { throw 'Whitespace check failed' }
Write-Output 'PASS: Phase 1 regressions and Phase 2A verification; no terminal reads performed by tests'
