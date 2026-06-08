@echo off
title FortiAnalyzer Reports
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo.
  echo  Sistema nao instalado — abrindo assistente...
  echo.
  call "%~dp0install.bat"
  exit /b 0
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install\iniciar-portal.ps1"
