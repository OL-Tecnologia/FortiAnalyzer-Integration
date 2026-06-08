@echo off
title Instalador FortiAnalyzer Reports
cd /d "%~dp0"

echo.
echo  Abrindo assistente de instalacao...
echo.
py -3 -m install.wizard_server 2>nul
if errorlevel 1 python -m install.wizard_server 2>nul
if errorlevel 1 (
  echo.
  echo  Python 3.11+ necessario. Instale em python.org com "Add to PATH".
  pause
  exit /b 1
)
