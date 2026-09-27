$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath ([IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')))
if (-not $env:TE_TEST_DATABASE_URL) { throw 'Set TE_TEST_DATABASE_URL for fresh PostgreSQL regression' }
& .venv/Scripts/python.exe scripts/verify_phase5_b_scope.py
if ($LASTEXITCODE -ne 0) { throw 'Phase 5B scope or frozen checkpoint failed' }
# The unchanged Phase 5A gate discovers ALL old and new tests and all quality checks.
& ./scripts/verify_phase5_a.ps1
if ($LASTEXITCODE -ne 0) { throw 'Phase 5A regression gate failed' }
& .venv/Scripts/python.exe scripts/verify_phase5_b_evidence.py
if ($LASTEXITCODE -ne 0) { throw 'Phase 5B evidence readback failed' }
& .venv/Scripts/python.exe scripts/verify_phase5_b_scope.py
if ($LASTEXITCODE -ne 0) { throw 'Final Phase 5B scope failed' }
& git diff --check
if ($LASTEXITCODE -ne 0) { throw 'Whitespace failed' }
Write-Output 'PASS: Phase 5B tooling gate; real acceptance status must be reported separately'
