#Requires -Version 5.1
<#
.SYNOPSIS
    Compila FortiAnalyzer Reports (aplicacao completa) com PyInstaller.
    Saida: dist\FortiAnalyzer-Reports\
#>
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host ""
Write-Host "  Build FortiAnalyzer-Reports (aplicacao completa)" -ForegroundColor Cyan
Write-Host ""

$venvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "Criando .venv..." -ForegroundColor Yellow
    py -3 -m venv .venv
    & $venvPython -m pip install --upgrade pip wheel setuptools -q
    & $venvPython -m pip install -e . -q
}

Write-Host "==> Instalando PyInstaller..."
& $venvPython -m pip install pyinstaller --quiet

Write-Host "==> Compilando..."
& $venvPython -m PyInstaller install\forti_app.spec --noconfirm --clean

$appExe = Join-Path $ProjectRoot "dist\FortiAnalyzer-Reports\FortiAnalyzer-Reports.exe"
if (-not (Test-Path $appExe)) {
    Write-Host "ERRO: exe nao gerado." -ForegroundColor Red
    exit 1
}

$sizeMb = [math]::Round((Get-Item $appExe).Length / 1MB, 2)
$folderMb = [math]::Round(
    (Get-ChildItem (Join-Path $ProjectRoot "dist\FortiAnalyzer-Reports") -Recurse | Measure-Object Length -Sum).Sum / 1MB,
    2
)

Write-Host ""
Write-Host "  OK: dist\FortiAnalyzer-Reports\FortiAnalyzer-Reports.exe ($sizeMb MB)" -ForegroundColor Green
Write-Host "  Pasta total: dist\FortiAnalyzer-Reports\ ($folderMb MB)" -ForegroundColor Green
Write-Host ""
Copy-Item (Join-Path $ProjectRoot "LEIA-ME.txt") (Join-Path $ProjectRoot "dist\FortiAnalyzer-Reports\LEIA-ME.txt") -Force

Write-Host "  Distribua a pasta dist\FortiAnalyzer-Reports\ ao time." -ForegroundColor White
Write-Host "  O usuario executa FortiAnalyzer-Reports.exe (portal abre automaticamente)." -ForegroundColor White
Write-Host ""
