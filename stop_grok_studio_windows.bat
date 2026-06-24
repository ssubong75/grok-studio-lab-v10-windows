@echo off
setlocal
cd /d "%~dp0"

if not exist "python\python.exe" exit /b 0
"%~dp0python\python.exe" -c "import json,urllib.request; r=urllib.request.Request('http://127.0.0.1:8765/api/shutdown',data=json.dumps({'immediate':True}).encode(),headers={'Content-Type':'application/json'},method='POST'); urllib.request.urlopen(r,timeout=2).read()" >nul 2>&1
exit /b 0
