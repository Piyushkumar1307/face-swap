# One-time setup on Windows (PowerShell). Run from repo root:
#   powershell -ExecutionPolicy Bypass -File scripts\self_host_setup_windows.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Backend = Join-Path $Root "backend"
$FF = Join-Path $Backend "facefusion"
$Venv = Join-Path $Backend "venv"
$VenvFF = Join-Path $Backend "venv-ff"

Write-Host "==> API venv"
python -m venv $Venv
& "$Venv\Scripts\pip.exe" install -U pip wheel
& "$Venv\Scripts\pip.exe" install -r "$Backend\requirements.txt"

Write-Host "==> FaceFusion clone + venv-ff"
if (-not (Test-Path "$FF\facefusion.py")) {
  git clone --depth 1 https://github.com/facefusion/facefusion.git $FF
}
python -m venv $VenvFF
& "$VenvFF\Scripts\pip.exe" install -U pip wheel
& "$VenvFF\Scripts\pip.exe" install -r "$FF\requirements.txt" imageio-ffmpeg
# GPU: replace CPU onnxruntime with GPU build (CUDA 12)
& "$VenvFF\Scripts\pip.exe" uninstall -y onnxruntime 2>$null
& "$VenvFF\Scripts\pip.exe" install "onnxruntime-gpu==1.24.4"

$Bin = Join-Path $Backend "bin"
New-Item -ItemType Directory -Force -Path $Bin | Out-Null
$FfExe = & "$VenvFF\Scripts\python.exe" -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"
$FfLink = Join-Path $Bin "ffmpeg.exe"
Copy-Item $FfExe $FfLink -Force

Write-Host "==> Download models (2-4 GB)"
$env:FACEFUSION_PYTHON = "$VenvFF\Scripts\python.exe"
$env:PATH = "$Bin;$env:PATH"
& $env:FACEFUSION_PYTHON "$Backend\scripts\download_swap_models.py"

Write-Host "==> Frontend build (requires Node.js)"
Push-Location (Join-Path $Root "frontend")
npm install
npm run build
$Static = Join-Path $Backend "static"
if (Test-Path $Static) { Remove-Item $Static -Recurse -Force }
New-Item -ItemType Directory -Force -Path $Static | Out-Null
Copy-Item -Path "dist\*" -Destination $Static -Recurse -Force
Pop-Location

$EnvExample = Join-Path $Root "deploy\windows.env.example"
$EnvFile = Join-Path $Backend ".env"
if (-not (Test-Path $EnvFile)) {
  Copy-Item $EnvExample $EnvFile
  Write-Host "Created backend\.env from deploy\windows.env.example"
}

Write-Host ""
Write-Host "Done. Next:"
Write-Host "  1. Edit backend\.env (Cloudinary keys)"
Write-Host "  2. deploy\start-windows.bat"
Write-Host "  3. Open http://localhost:8000  or http://YOUR_PC_IP:8000"
