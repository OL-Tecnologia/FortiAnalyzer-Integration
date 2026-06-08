#Requires -Version 5.1
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Add-Type -AssemblyName System.Windows.Forms -ErrorAction SilentlyContinue
    [System.Windows.Forms.MessageBox]::Show(
        "Execute primeiro: FortiAnalyzer Reports.bat",
        "FortiAnalyzer Reports"
    ) | Out-Null
    exit 1
}

Set-Location $ProjectRoot
$url = "http://localhost:8000/login.html"

Write-Host ""
Write-Host "  FortiAnalyzer Reports" -ForegroundColor Cyan
Write-Host "  Portal: $url" -ForegroundColor White
Write-Host "  Feche esta janela ou Ctrl+C para encerrar o servidor." -ForegroundColor DarkGray
Write-Host ""

Start-Process $url | Out-Null
& $venvPython -m forti_report.api.app
