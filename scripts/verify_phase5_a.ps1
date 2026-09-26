$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath ([IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')))
if (-not $env:TE_TEST_DATABASE_URL) { throw 'Set TE_TEST_DATABASE_URL for fresh PostgreSQL regression' }
New-Item -ItemType Directory -Force test-results | Out-Null
& .venv/Scripts/python.exe scripts/verify_phase5_a_scope.py
if ($LASTEXITCODE -ne 0) { throw 'Phase 5A scope or frozen baseline failed' }
& .venv/Scripts/python.exe scripts/verify_phase4_e_evidence.py
if ($LASTEXITCODE -ne 0) { throw 'Frozen evidence changed' }
& .venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --junitxml=test-results/phase5_a.xml
if ($LASTEXITCODE -ne 0) { throw 'Backend regression or PostgreSQL migration checks failed' }
& .venv/Scripts/python.exe -m ruff check .
if ($LASTEXITCODE -ne 0) { throw 'Ruff failed' }
& .venv/Scripts/python.exe -m ruff format --check .
if ($LASTEXITCODE -ne 0) { throw 'Format failed' }
& .venv/Scripts/python.exe -m mypy
if ($LASTEXITCODE -ne 0) { throw 'Strict mypy failed' }
& .venv/Scripts/python.exe scripts/secret_scan.py
if ($LASTEXITCODE -ne 0) { throw 'Secret scan failed' }
& .venv/Scripts/python.exe -m trading_ecosystem.benchmarks.hashing
if ($LASTEXITCODE -ne 0) { throw 'Frozen registry failed' }
Push-Location dashboard
try {
    foreach ($task in @('typecheck', 'lint', 'format', 'test', 'build')) {
        if ($task -eq 'format') {
            # Git-managed Windows checkouts may use CRLF; retain every other style check.
            & npm.cmd run format -- --end-of-line auto
        } else {
            & npm.cmd run $task
        }
        if ($LASTEXITCODE -ne 0) { throw "Frontend $task failed" }
    }
} finally { Pop-Location }
& .venv/Scripts/python.exe scripts/verify_phase5_a_scope.py
if ($LASTEXITCODE -ne 0) { throw 'Final scope check failed' }
& .venv/Scripts/python.exe scripts/verify_phase4_e_evidence.py
if ($LASTEXITCODE -ne 0) { throw 'Final evidence preservation failed' }
& git diff --check
if ($LASTEXITCODE -ne 0) { throw 'Whitespace failed' }
Write-Output 'PASS: Phase 5A full regression, PostgreSQL migrations, frontend build and preservation'
