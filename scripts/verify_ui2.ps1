$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath ([IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')))
foreach ($check in @('verify_ui2.py', 'verify_phase5_c0_evidence.py', 'verify_phase5_b_evidence.py')) {
    & .venv/Scripts/python.exe "scripts/$check"
    if ($LASTEXITCODE -ne 0) { throw "Pre-gate $check failed" }
}
Push-Location dashboard
try {
    foreach ($task in @('typecheck', 'lint', 'format', 'test', 'build')) {
        if ($task -eq 'format') { & npm.cmd run format -- --end-of-line auto }
        else { & npm.cmd run $task }
        if ($LASTEXITCODE -ne 0) { throw "Frontend $task failed" }
    }
} finally { Pop-Location }
& .venv/Scripts/python.exe -m ruff check .
if ($LASTEXITCODE -ne 0) { throw 'Ruff failed' }
& .venv/Scripts/python.exe -m ruff format --check .
if ($LASTEXITCODE -ne 0) { throw 'Python format failed' }
& .venv/Scripts/python.exe -m mypy
if ($LASTEXITCODE -ne 0) { throw 'Strict mypy failed' }
& .venv/Scripts/python.exe scripts/secret_scan.py
if ($LASTEXITCODE -ne 0) { throw 'Secret scan failed' }
foreach ($check in @('verify_ui2.py', 'verify_phase5_c0_evidence.py', 'verify_phase5_b_evidence.py')) {
    & .venv/Scripts/python.exe "scripts/$check"
    if ($LASTEXITCODE -ne 0) { throw "Post-gate $check failed" }
}
& git diff --check
if ($LASTEXITCODE -ne 0) { throw 'Whitespace failed' }
Write-Output 'PASS: UI-2 frontend, build, quality, scope, lineage and research preservation'
