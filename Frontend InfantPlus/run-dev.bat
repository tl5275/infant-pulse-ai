@echo off
cd /d "%~dp0"

set "NODE_EXE=C:\Program Files\nodejs\node.exe"

if not exist "%NODE_EXE%" (
  echo Node.js was not found at "%NODE_EXE%".
  echo Install Node.js or update run-dev.bat with the correct path.
  pause
  exit /b 1
)

"%NODE_EXE%" .\node_modules\next\dist\bin\next dev
