$ErrorActionPreference = 'Stop'
$env:PATH = "$env:USERPROFILE\.local\bin;$env:PATH"
$workspace = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Set-Location -LiteralPath $workspace
if (-not $env:TE_TEST_DATABASE_URL) { throw 'Set TE_TEST_DATABASE_URL for the isolated test instance' }
New-Item -ItemType Directory -Force -Path 'test-results' | Out-Null
& uv sync --locked
if ($LASTEXITCODE -ne 0) { throw 'Locked dependency sync failed' }
& uv run --locked pytest -q -p no:cacheprovider --junitxml=test-results/phase1.xml
if ($LASTEXITCODE -ne 0) { throw 'Phase 1 tests failed' }
& uv run --locked ruff check .
if ($LASTEXITCODE -ne 0) { throw 'Ruff lint failed' }
& uv run --locked ruff format --check .
if ($LASTEXITCODE -ne 0) { throw 'Ruff format failed' }
& uv run --locked mypy
if ($LASTEXITCODE -ne 0) { throw 'mypy failed' }
& uv run --locked python scripts/secret_scan.py
if ($LASTEXITCODE -ne 0) { throw 'Secret scan failed' }
& git diff --check
if ($LASTEXITCODE -ne 0) { throw 'Git whitespace check failed' }
Write-Output 'PASS: complete Phase 1 verification suite'
