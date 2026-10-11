$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath ([IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')))
if (-not $env:TE_TEST_DATABASE_URL) { throw 'Set TE_TEST_DATABASE_URL for isolated PostgreSQL regression' }
New-Item -ItemType Directory -Force test-results | Out-Null
foreach ($check in @('verify_phase5_c1.py', 'verify_phase5_c0_evidence.py', 'verify_phase5_b_evidence.py')) {
    & .venv/Scripts/python.exe "scripts/$check"
    if ($LASTEXITCODE -ne 0) { throw "Pre-gate $check failed" }
}
& .venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --junitxml=test-results/phase5_c1.xml
if ($LASTEXITCODE -ne 0) { throw 'Backend, PostgreSQL or migration regression failed' }
& .venv/Scripts/python.exe -m ruff check .
if ($LASTEXITCODE -ne 0) { throw 'Ruff failed' }
& .venv/Scripts/python.exe -m ruff format --check .
if ($LASTEXITCODE -ne 0) { throw 'Python format failed' }
& .venv/Scripts/python.exe -m mypy
if ($LASTEXITCODE -ne 0) { throw 'Strict mypy failed' }
& .venv/Scripts/python.exe scripts/secret_scan.py
if ($LASTEXITCODE -ne 0) { throw 'Secret scan failed' }
& .venv/Scripts/python.exe -m trading_ecosystem.benchmarks.hashing
if ($LASTEXITCODE -ne 0) { throw 'Frozen registry failed' }
Push-Location dashboard
try {
    foreach ($task in @('typecheck', 'lint', 'format', 'test', 'build')) {
        if ($task -eq 'format') { & npm.cmd run format -- --end-of-line auto }
        else { & npm.cmd run $task }
        if ($LASTEXITCODE -ne 0) { throw "Frontend $task failed" }
    }
} finally { Pop-Location }
foreach ($check in @('verify_phase5_c1.py', 'verify_phase5_c0_evidence.py', 'verify_phase5_b_evidence.py')) {
    & .venv/Scripts/python.exe "scripts/$check"
    if ($LASTEXITCODE -ne 0) { throw "Post-gate $check failed" }
}
& git diff --check
if ($LASTEXITCODE -ne 0) { throw 'Whitespace failed' }
Write-Output 'PASS: Phase 5C.1 full regression, isolated PostgreSQL migrations, frontend and preservation'
