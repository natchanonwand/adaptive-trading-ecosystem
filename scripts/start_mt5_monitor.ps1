param([Parameter(Mandatory=$true)][string]$Config, [int]$Seconds = 0, [int]$Port = 8765)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath ([IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')))
if (-not $env:TE_DATABASE_URL) { throw 'Set the local monitoring TE_DATABASE_URL first' }
if (-not (Test-Path -LiteralPath $Config)) { throw 'Explicit alias configuration required' }
& uv run --locked --extra discovery python -m trading_ecosystem.mt5 --config $Config --seconds $Seconds --port $Port
if ($LASTEXITCODE -ne 0) { throw 'Read-only bridge stopped without qualification; inspect health' }
