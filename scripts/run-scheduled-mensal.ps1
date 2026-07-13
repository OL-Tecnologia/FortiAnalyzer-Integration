#Requires -Version 5.1
<#
.SYNOPSIS
    Rotina agendada: gera PDF MENSAL e envia por e-mail.
.DESCRIPTION
    Use no Agendador de Tarefas do Windows (dia 5, 06:00) ou manualmente.
    Requer FAZ_USER/FAZ_PASSWORD e SMTP_* no .env.
#>
param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "ERRO: Execute install.bat primeiro." -ForegroundColor Red
    exit 1
}

Set-Location $ProjectRoot

$args = @("-m", "forti_report.cli", "run-scheduled-mensal")
if ($Force) { $args += "--force" }

Write-Host "Rotina agendada MENSAL (Cruz Azul)..." -ForegroundColor Cyan
& $venvPython @args
exit $LASTEXITCODE
