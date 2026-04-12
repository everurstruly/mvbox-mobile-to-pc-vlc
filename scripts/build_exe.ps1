# MovieBox Sync Build Script
# This script bundles the application into a single executable using PyInstaller.

Write-Host "--- Starting MovieBox Sync Build Process ---" -ForegroundColor Cyan

# 1. Ensure dependencies are installed
Write-Host "[1/3] Installing dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt

# 2. Build the executable
Write-Host "[2/3] Building executable with PyInstaller..." -ForegroundColor Yellow
pyinstaller --clean moviebox_sync.spec

# 3. Cleanup
Write-Host "[3/3] Build complete. Output located in 'dist/' directory." -ForegroundColor Green
Write-Host "Executable: dist/MovieBoxSync.exe" -ForegroundColor White
