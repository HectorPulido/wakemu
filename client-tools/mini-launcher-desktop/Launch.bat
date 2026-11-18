@echo off
set "WAKFU_LAUNCHER_ROOT=%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  python "%~dp0mini-launcher\launcher_entry.py" %*
) else (
  for %%V in (3.14 3.13 3.12 3.11 3.10) do (
    py -%%V -c "import sys" >nul 2>nul
    if not errorlevel 1 (
      py -%%V "%~dp0mini-launcher\launcher_entry.py" %*
      exit /b
    )
  )
  echo Install Python 3.14 x64, then open Launch.bat again.
  exit /b 1
)
