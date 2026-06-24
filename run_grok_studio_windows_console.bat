@echo off
setlocal
cd /d "%~dp0"

if not exist "python\python.exe" (
  echo The bundled Python runtime was not found.
  echo Extract the complete Grok Studio Lab Windows folder and try again.
  pause
  exit /b 1
)

set "GROK_STUDIO_DATA_DIR=%~dp0grok_studio_data"
if not exist "grok_studio_data\logs" mkdir "grok_studio_data\logs"
"%~dp0python\python.exe" "%~dp0grok_studio.py" --host 127.0.0.1 --port 8765 --open
pause
