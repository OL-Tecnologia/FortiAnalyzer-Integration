#Requires -Version 5.1
<#
.SYNOPSIS
    Compila FortiAnalyzer Reports (aplicacao completa) com PyInstaller.
    Saida: dist\FortiAnalyzer-Reports\ (instalacao limpa - sem tenants / LGPD)
#>
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host ""
Write-Host "  Build FortiAnalyzer-Reports (aplicacao completa - limpa / LGPD)" -ForegroundColor Cyan
Write-Host ""

# Evita WinError 5 / remoção do .env com o app ainda em execução
Get-Process -Name "FortiAnalyzer-Reports" -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Host ("==> Encerrando processo em execucao (PID {0})..." -f $_.Id) -ForegroundColor Yellow
    Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 1

$venvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "Criando .venv..." -ForegroundColor Yellow
    py -3 -m venv .venv
    & $venvPython -m pip install --upgrade pip wheel setuptools -q
    & $venvPython -m pip install -e . -q
}

# Preserva .env do dist (senha admin local) — o PyInstaller apaga a pasta inteira
$distEnvPath = Join-Path $ProjectRoot "dist\FortiAnalyzer-Reports\.env"
$envBackupPath = Join-Path $env:TEMP "forti_dist_env_backup.env"
if (Test-Path $distEnvPath) {
    Copy-Item $distEnvPath $envBackupPath -Force
    Write-Host "==> Backup do .env do dist (senha admin sera restaurada apos o build)..." -ForegroundColor Yellow
} elseif (Test-Path $envBackupPath) {
    Remove-Item $envBackupPath -Force -ErrorAction SilentlyContinue
}

Write-Host "==> Instalando PyInstaller..."
& $venvPython -m pip install pyinstaller --quiet

Write-Host "==> Compilando..."
& $venvPython -m PyInstaller install\forti_app.spec --noconfirm --clean

$distRoot = Join-Path $ProjectRoot "dist\FortiAnalyzer-Reports"
$appExe = Join-Path $distRoot "FortiAnalyzer-Reports.exe"
if (-not (Test-Path $appExe)) {
    Write-Host "ERRO: exe nao gerado." -ForegroundColor Red
    exit 1
}

Write-Host "==> Sanitizando pacote (LGPD: sem tenants, logos de clientes)..."
Get-ChildItem $distRoot -Recurse -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -eq "clients" -and $_.Parent.Name -eq "assets" } |
    ForEach-Object {
        Write-Host ("    removendo {0}" -f $_.FullName)
        Remove-Item $_.FullName -Recurse -Force
    }

Get-ChildItem $distRoot -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match '(?i)logo_cruz|cruz-azul|cruz_azul' } |
    ForEach-Object {
        Write-Host ("    removendo {0}" -f $_.FullName)
        Remove-Item $_.FullName -Force
    }

# Remove .env/.secret embutidos no bundle (nao o runtime que vamos restaurar)
Get-ChildItem $distRoot -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object {
        ($_.Name -eq ".env" -or $_.Name -eq ".env.local" -or $_.Extension -eq ".secret") -and
        $_.DirectoryName -ne $distRoot
    } |
    ForEach-Object {
        Write-Host ("    removendo {0}" -f $_.FullName)
        Remove-Item $_.FullName -Force
    }

$clientsOut = Join-Path $distRoot "configs\clients"
New-Item -ItemType Directory -Path $clientsOut -Force | Out-Null
$readmeSrc = Join-Path $ProjectRoot "configs\clients\README.md"
if (Test-Path $readmeSrc) {
    Copy-Item $readmeSrc (Join-Path $clientsOut "README.md") -Force
}

New-Item -ItemType Directory -Path (Join-Path $distRoot "assets\clients") -Force | Out-Null

Copy-Item (Join-Path $ProjectRoot "LEIA-ME.txt") (Join-Path $distRoot "LEIA-ME.txt") -Force

# Restaura .env de teste local (ou sincroniza senha admin do .env do projeto)
$distEnvPath = Join-Path $distRoot ".env"
$projEnv = Join-Path $ProjectRoot ".env"
$templateEnv = Join-Path $ProjectRoot "install\config.env"
if (Test-Path $envBackupPath) {
    Copy-Item $envBackupPath $distEnvPath -Force
    Write-Host "==> .env local restaurado (PORTAL_ADMIN_PASSWORD preservada)." -ForegroundColor Yellow
} elseif (Test-Path $templateEnv) {
    Copy-Item $templateEnv $distEnvPath -Force
    if (Test-Path $projEnv) {
        $adminLine = Select-String -Path $projEnv -Pattern '^PORTAL_ADMIN_PASSWORD=\S+' |
            Select-Object -First 1
        if ($adminLine) {
            $txt = Get-Content $distEnvPath -Raw
            $txt = [regex]::Replace($txt, '(?m)^PORTAL_ADMIN_PASSWORD=.*$', $adminLine.Line)
            Set-Content -Path $distEnvPath -Value $txt -NoNewline
            Write-Host "==> PORTAL_ADMIN_PASSWORD sincronizado do .env do projeto." -ForegroundColor Yellow
        }
    }
}

$sizeMb = [math]::Round((Get-Item $appExe).Length / 1MB, 2)
$folderMb = [math]::Round(
    (Get-ChildItem $distRoot -Recurse | Measure-Object Length -Sum).Sum / 1MB,
    2
)

Write-Host ""
Write-Host ("  OK: dist\FortiAnalyzer-Reports\FortiAnalyzer-Reports.exe ({0} MB)" -f $sizeMb) -ForegroundColor Green
Write-Host ("  Pasta total: dist\FortiAnalyzer-Reports\ ({0} MB)" -f $folderMb) -ForegroundColor Green
Write-Host "  Pacote sem tenants/logos; .env local restaurado quando existir." -ForegroundColor Green
Write-Host ""
Write-Host "  Distribua a pasta dist\FortiAnalyzer-Reports\ ao time." -ForegroundColor White
Write-Host "  Super Admin: valor de PORTAL_ADMIN_PASSWORD no .env ao lado do .exe." -ForegroundColor Yellow
Write-Host ""
