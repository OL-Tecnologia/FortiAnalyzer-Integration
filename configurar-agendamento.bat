@echo off
title Configurar agendamento - FortiAnalyzer Reports
cd /d "%~dp0"

set PY=
if exist ".venv\Scripts\python.exe" set PY=.venv\Scripts\python.exe
if not defined PY (
  where py >nul 2>&1 && set PY=py -3
)
if not defined PY (
  echo.
  echo  Python nao encontrado. Execute install.bat primeiro.
  pause
  exit /b 1
)

echo.
echo  Assistente de configuracao — agendamento mensal + e-mail
echo.

"%PY%" scripts\configure_scheduler.py %*
set EXIT=%ERRORLEVEL%

echo.
pause
exit /b %EXIT%
