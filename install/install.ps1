#Requires -Version 5.1
param(
    [switch]$Force,
    [switch]$ForceEnv,
    [switch]$CreateShortcut,
    [switch]$Silent
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

function Show-Msg($text, $title = "FortiAnalyzer Reports") {
    Add-Type -AssemblyName System.Windows.Forms -ErrorAction SilentlyContinue
    [System.Windows.Forms.MessageBox]::Show($text, $title) | Out-Null
}

function Write-Step($msg) { if (-not $Silent) { Write-Host "`n==> $msg" -ForegroundColor Cyan } }
function Write-Ok($msg)   { if (-not $Silent) { Write-Host "    OK: $msg" -ForegroundColor Green } }
function Write-Warn($msg) { if (-not $Silent) { Write-Host "    AVISO: $msg" -ForegroundColor Yellow } }

if (-not $Silent) {
    Write-Host ""
    Write-Host "  FortiAnalyzer Reports - Instalador" -ForegroundColor White
    Write-Host "  Cruz Azul | OL Tecnologia" -ForegroundColor DarkGray
    Write-Host ""
}

Write-Step "Verificando Python 3.11+"
$python = $null
foreach ($candidate in @("py -3.11", "py -3.12", "py -3.13", "py -3", "python")) {
    $parts = $candidate -split " ", 2
    if ($parts.Count -eq 2) {
        $exe = $parts[0]
        $arg = $parts[1]
        if (Get-Command $exe -ErrorAction SilentlyContinue) {
            try {
                $ver = & $exe $arg -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
                if ($ver -match "^3\.(\d+)$") {
                    if ([int]$Matches[1] -ge 11) {
                        $python = @{ Exe = $exe; Arg = $arg; Version = $ver }
                        break
                    }
                }
            } catch { }
        }
    } else {
        if (Get-Command $candidate -ErrorAction SilentlyContinue) {
            try {
                $ver = & $candidate -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
                if ($ver -match "^3\.(\d+)$") {
                    if ([int]$Matches[1] -ge 11) {
                        $python = @{ Exe = $candidate; Arg = $null; Version = $ver }
                        break
                    }
                }
            } catch { }
        }
    }
}

if (-not $python) {
    $msg = "Python 3.11 ou superior nao encontrado.`n`nInstale em python.org marcando 'Add python.exe to PATH' e execute novamente."
    if ($Silent) { Write-Host "ERRO: $msg" -ForegroundColor Red } else { Show-Msg $msg }
    Start-Process "https://www.python.org/downloads/" | Out-Null
    exit 1
}
Write-Ok "Python $($python.Version)"

function Invoke-Python {
    param([string[]]$PythonArgs)
    if ($python.Arg) { & $python.Exe $python.Arg @PythonArgs }
    else { & $python.Exe @PythonArgs }
    if ($LASTEXITCODE -ne 0) { throw "Comando Python falhou (exit $LASTEXITCODE)" }
}

$venvPath = Join-Path $ProjectRoot ".venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"

Write-Step "Ambiente virtual"
if ($Force -and (Test-Path $venvPath)) {
    Remove-Item -Recurse -Force $venvPath
}
if (-not (Test-Path $venvPython)) {
    Invoke-Python @("-m", "venv", $venvPath)
    Write-Ok "Ambiente criado"
} else {
    Write-Ok "Ambiente ja existe"
}

Write-Step "Dependencias"
& $venvPython -m pip install --upgrade pip wheel setuptools --quiet
& $venvPython -m pip install -e . --quiet
Write-Ok "Software instalado"

Write-Step "Pastas"
@("output", "output\faz_mensal", "output\chart_cache") | ForEach-Object {
    $p = Join-Path $ProjectRoot $_
    if (-not (Test-Path $p)) { New-Item -ItemType Directory -Path $p -Force | Out-Null }
}
Write-Ok "Pastas de saida prontas"

Write-Step "Configuracao"
$configEnv = Join-Path $PSScriptRoot "config.env"
$envFile = Join-Path $ProjectRoot ".env"
if (Test-Path $configEnv) {
    if (-not (Test-Path $envFile) -or $ForceEnv) {
        Copy-Item $configEnv $envFile -Force
        Write-Ok "Configuracao Cruz Azul aplicada (.env)"
    } else {
        Write-Ok ".env mantido (ja existia)"
    }
} else {
    Write-Warn "install\config.env nao encontrado"
}

Write-Step "Verificacao"
$check = & $venvPython -c 'import forti_report; from forti_report.config import get_settings; print(get_settings().faz_adom)' 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Ok "Sistema OK (ADOM: $check)"
} else {
    Write-Warn "Verificacao falhou: $check"
}

if ($CreateShortcut) {
    Write-Step "Atalho na area de trabalho"
    $bat = Join-Path $ProjectRoot "FortiAnalyzer Reports.bat"
    $desktop = [Environment]::GetFolderPath("Desktop")
    $lnk = Join-Path $desktop "FortiAnalyzer Reports.lnk"
    $WshShell = New-Object -ComObject WScript.Shell
    $sc = $WshShell.CreateShortcut($lnk)
    $sc.TargetPath = $bat
    $sc.WorkingDirectory = $ProjectRoot
    $sc.Description = "Relatorio MENSAL FortiAnalyzer - Cruz Azul"
    $sc.Save()
    Write-Ok "Atalho criado"
}

if (-not $Silent) {
    Write-Host ""
    Write-Host "  Instalacao concluida." -ForegroundColor Green
    Write-Host ""
    Write-Host "  Use o atalho 'FortiAnalyzer Reports' ou execute:" -ForegroundColor White
    Write-Host "  FortiAnalyzer Reports.bat" -ForegroundColor Gray
    Write-Host ""
}
