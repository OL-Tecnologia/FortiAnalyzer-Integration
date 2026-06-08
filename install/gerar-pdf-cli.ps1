#Requires -Version 5.1
<#
.SYNOPSIS
    Gera o PDF MENSAL unificado via linha de comando (usa credenciais do .env).
#>
param(
    [int]$Days = 60,
    [switch]$ForceDownload,
    [switch]$NoCharts
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "ERRO: Execute install.bat primeiro." -ForegroundColor Red
    exit 1
}

Set-Location $ProjectRoot

$args = @("-m", "forti_report.cli", "generate-mensal-unified", "--days", "$Days")
if ($ForceDownload) { $args += "--force-download" }
if ($NoCharts) { $args += "--no-charts" }

Write-Host "Gerando PDF MENSAL (days=$Days)..." -ForegroundColor Cyan
& $venvPython @args
