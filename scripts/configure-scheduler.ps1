#Requires -Version 5.1
<#
.SYNOPSIS
    Assistente interativo para configurar agendamento mensal + e-mail no .env.
#>
param(
    [switch]$Show
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "ERRO: Ambiente virtual nao encontrado. Execute install.bat primeiro." -ForegroundColor Red
    exit 1
}

Set-Location $ProjectRoot

$pyArgs = @()
if ($Show) { $pyArgs += "--show" }

& $venvPython (Join-Path $PSScriptRoot "configure_scheduler.py") @pyArgs
exit $LASTEXITCODE
