@echo off
REM Start Face Swap API on Windows (run from repo root).
cd /d "%~dp0\.."
cd backend
set PATH=%CD%\bin;%PATH%
if exist "venv-ff\Scripts\python.exe" (
  set FACEFUSION_PYTHON=venv-ff\Scripts\python.exe
)
if exist "venv\Scripts\python.exe" (
  "venv\Scripts\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8000
) else (
  echo ERROR: Run scripts\self_host_setup_windows.ps1 first.
  exit /b 1
)
