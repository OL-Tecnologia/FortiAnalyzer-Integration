@echo off
title Desinstalar FortiAnalyzer Reports
setlocal

cd /d "%~dp0"

echo.
echo  FortiAnalyzer Reports - Desinstalacao
echo.
echo  Isso vai remover:
echo    - .venv (ambiente virtual)
echo    - output\ (arquivos gerados/caches)
echo    - Atalho da area de trabalho "FortiAnalyzer Reports.lnk"
echo.
echo  Seus fontes e scripts NAO serao apagados.
echo.

choice /M "Confirmar desinstalacao"
if errorlevel 2 exit /b 0

echo.
echo  Removendo atalho da area de trabalho...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$desktop=[Environment]::GetFolderPath('Desktop'); $lnk=Join-Path $desktop 'FortiAnalyzer Reports.lnk'; if (Test-Path $lnk) { Remove-Item -Force $lnk; 'OK' } else { 'Nao encontrado' }" ^
  1>nul 2>nul

echo  Removendo .venv...
if exist ".venv" rmdir /s /q ".venv"

echo  Removendo output...
if exist "output" rmdir /s /q "output"

echo.
echo  Pronto. Se quiser, agora voce pode apagar a pasta inteira do projeto.
echo.
pause
