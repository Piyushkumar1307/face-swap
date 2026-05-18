@echo off
REM Permanent URL: faceswap.yourdomain.com via named Cloudflare tunnel.
REM Requires: deploy\cloudflared\config.yml (copy from config.example.yml)
REM One-time: cloudflared tunnel login / create / route dns (see config.example.yml)

cd /d "%~dp0\.."

if not exist "deploy\cloudflared\config.yml" (
  echo ERROR: Create deploy\cloudflared\config.yml from config.example.yml first.
  pause
  exit /b 1
)

start "Face Swap API" cmd /k "deploy\start-windows.bat"
timeout /t 8 /nobreak >nul

echo Tunnel running — use your configured hostname, e.g. https://faceswap.yourdomain.com
cloudflared tunnel --config "%~dp0cloudflared\config.yml" run face-swap

pause
