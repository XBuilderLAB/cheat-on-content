[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$CheatArgs
)

$ErrorActionPreference = 'Stop'
$Cli = Join-Path $PSScriptRoot 'cheat_cli.py'
$Python = Get-Command python -ErrorAction SilentlyContinue
if (-not $Python) {
    throw 'Python was not found. Install Python 3.10+ and add python to PATH.'
}

$env:PYTHONUTF8 = '1'
& $Python.Source $Cli @CheatArgs
exit $LASTEXITCODE
