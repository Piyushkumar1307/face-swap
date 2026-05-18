@echo off
REM Run Face Swap API + public HTTPS URL via Cloudflare quick tunnel (no domain required).
REM Good for testing "access from anywhere". URL changes each run unless you use config.yml.
REM
REM 1. Install cloudflared: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
REM 2. Run this script from repo root (starts API in a new window, then tunnel).

cd /d "%~dp0\.."

echo Starting Face Swap API on port 8000...
start "Face Swap API" cmd /k "deploy\start-windows.bat"

echo Waiting for API to boot...
timeout /t 8 /nobreak >nul

echo.
echo Starting Cloudflare Tunnel (public HTTPS link will appear below)...
echo Share that URL to open the app from anywhere.
echo.
cloudflared tunnel --url http://127.0.0.1:8000

pause
