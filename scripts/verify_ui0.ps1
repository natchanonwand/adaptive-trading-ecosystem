$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath ([IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')))
& .venv/Scripts/python.exe scripts/verify_ui0.py
if ($LASTEXITCODE -ne 0) { throw 'UI-0 preservation failed' }
& .venv/Scripts/python.exe scripts/verify_phase5_c0_evidence.py
if ($LASTEXITCODE -ne 0) { throw 'Phase 5B database or experiment preservation failed' }
& .venv/Scripts/python.exe scripts/verify_phase5_b_evidence.py
if ($LASTEXITCODE -ne 0) { throw 'Phase 5B run evidence failed' }
& .venv/Scripts/python.exe -m ruff check .
if ($LASTEXITCODE -ne 0) { throw 'Ruff failed' }
& .venv/Scripts/python.exe -m ruff format --check .
if ($LASTEXITCODE -ne 0) { throw 'Python format failed' }
& .venv/Scripts/python.exe -m mypy
if ($LASTEXITCODE -ne 0) { throw 'Strict mypy failed' }
& .venv/Scripts/python.exe scripts/secret_scan.py
if ($LASTEXITCODE -ne 0) { throw 'Secret scan failed' }
Push-Location dashboard
try {
    foreach ($task in @('typecheck', 'lint', 'format', 'test', 'build')) {
        if ($task -eq 'format') { & npm.cmd run format -- --end-of-line auto }
        else { & npm.cmd run $task }
        if ($LASTEXITCODE -ne 0) { throw "Frontend $task failed" }
    }
} finally { Pop-Location }
& .venv/Scripts/python.exe scripts/verify_ui0.py
if ($LASTEXITCODE -ne 0) { throw 'Final preservation failed' }
Write-Output 'PASS: UI-0 frontend and broader research preservation gate'
