$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath ([IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')))
if (-not $env:TE_TEST_DATABASE_URL) { throw 'Isolated PostgreSQL test URL required' }
& .venv/Scripts/python.exe scripts/verify_phase5_c2d.py
if ($LASTEXITCODE -ne 0) { throw 'Preservation failed' }
& .venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --junitxml=test-results/phase5_c2d.xml
if ($LASTEXITCODE -ne 0) { throw 'Backend/integration/migrations failed' }
& .venv/Scripts/python.exe -m ruff check .
if ($LASTEXITCODE -ne 0) { throw 'Ruff failed' }
& .venv/Scripts/python.exe -m ruff format --check .
if ($LASTEXITCODE -ne 0) { throw 'Python format failed' }
& .venv/Scripts/python.exe -m mypy
if ($LASTEXITCODE -ne 0) { throw 'Strict mypy failed' }
& .venv/Scripts/python.exe scripts/secret_scan.py
if ($LASTEXITCODE -ne 0) { throw 'Secret scan failed' }
& .venv/Scripts/python.exe -m trading_ecosystem.benchmarks.hashing
if ($LASTEXITCODE -ne 0) { throw 'Registry failed' }
Push-Location dashboard
try {
    foreach ($task in @('typecheck','lint','format','test','build')) {
        if ($task -eq 'format') { & npm.cmd run format -- --end-of-line auto }
        else { & npm.cmd run $task }
        if ($LASTEXITCODE -ne 0) { throw "Frontend $task failed" }
    }
} finally { Pop-Location }
& .venv/Scripts/python.exe scripts/verify_phase5_c2d.py
if ($LASTEXITCODE -ne 0) { throw 'Final preservation failed' }
& .venv/Scripts/python.exe scripts/verify_phase5_b_evidence.py
if ($LASTEXITCODE -ne 0) { throw 'Historical run evidence failed' }
& git diff --check
if ($LASTEXITCODE -ne 0) { throw 'Diff check failed' }
Write-Output 'PASS: Phase 5C.2D full gate; no native campaign execution'
