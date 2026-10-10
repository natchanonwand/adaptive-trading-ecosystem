$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath ([IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')))
& .venv/Scripts/python.exe scripts/verify_phase5_c0_scope.py
if ($LASTEXITCODE -ne 0) { throw 'Phase 5C.0 scope failed' }
& ./scripts/verify_phase5_a.ps1
if ($LASTEXITCODE -ne 0) { throw 'Full regression failed' }
& .venv/Scripts/python.exe scripts/verify_phase5_b_evidence.py
if ($LASTEXITCODE -ne 0) { throw 'Phase 5B evidence failed' }
& .venv/Scripts/python.exe scripts/verify_phase5_c0_evidence.py
if ($LASTEXITCODE -ne 0) { throw 'Historical database preservation failed' }
& .venv/Scripts/python.exe scripts/verify_phase5_c0_scope.py
if ($LASTEXITCODE -ne 0) { throw 'Final scope failed' }
& git diff --check
if ($LASTEXITCODE -ne 0) { throw 'Whitespace failed' }
Write-Output 'PASS: Phase 5C.0 full gate; contracts only; no real experiment executed'
