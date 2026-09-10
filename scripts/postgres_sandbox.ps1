param([ValidateSet('Start', 'Stop')][string]$Action = 'Start')
$ErrorActionPreference = 'Stop'
$workspace = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$localRoot = [IO.Path]::GetFullPath((Join-Path $workspace '.local\phase1-postgres'))
if (-not $localRoot.StartsWith($workspace + [IO.Path]::DirectorySeparatorChar)) {
    throw 'Invalid sandbox path'
}
$pgBin = 'C:\Program Files\PostgreSQL\17\bin'
$pgData = Join-Path $localRoot 'data'
New-Item -ItemType Directory -Force -Path $localRoot | Out-Null
if ($Action -eq 'Stop') {
    & (Join-Path $pgBin 'pg_ctl.exe') -D $pgData -w stop
    if ($LASTEXITCODE -ne 0) { throw 'Sandbox stop failed' }
    exit
}
if (-not (Test-Path -LiteralPath (Join-Path $pgData 'PG_VERSION'))) {
    $initArgs = @('-D', "`"$pgData`"", '-U', 'phase1_test', '--auth=trust', '--encoding=UTF8', '--no-locale')
    $init = Start-Process -FilePath (Join-Path $pgBin 'initdb.exe') -ArgumentList $initArgs -WindowStyle Hidden -Wait -PassThru -RedirectStandardOutput (Join-Path $localRoot 'init.log') -RedirectStandardError (Join-Path $localRoot 'init-error.log')
    if ($init.ExitCode -ne 0) { throw 'Sandbox initialization failed; inspect ignored local logs' }
}
& (Join-Path $pgBin 'pg_ctl.exe') -D $pgData status *> $null
if ($LASTEXITCODE -ne 0) {
    $startArgs = @('-D', "`"$pgData`"", '-o', '"-p 55439 -h 127.0.0.1"', '-l', "`"$(Join-Path $localRoot 'postgres.log')`"", '-w', 'start')
    $start = Start-Process -FilePath (Join-Path $pgBin 'pg_ctl.exe') -ArgumentList $startArgs -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $localRoot 'start.log') -RedirectStandardError (Join-Path $localRoot 'start-error.log')
    # Wait only for pg_ctl, not its persistent PostgreSQL descendant process.
    $start.WaitForExit()
    if ($start.ExitCode -ne 0) { throw 'Sandbox start failed; inspect ignored local logs' }
}
Write-Output 'Isolated PostgreSQL test instance ready on loopback port 55439. No existing service changed.'
