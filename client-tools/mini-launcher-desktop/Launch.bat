@echo off
set "WAKFU_LAUNCHER_ROOT=%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  python "%~dp0mini-launcher\launcher_entry.py" %*
) else (
  py -3 "%~dp0mini-launcher\launcher_entry.py" %*
)
