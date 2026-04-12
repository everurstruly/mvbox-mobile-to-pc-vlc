# MovieBox Sync - Universal Build Script
# Generates both Single-File Exe and prepares Full Setup Installer assets.

Write-Host "--- Starting MovieBox Sync Universal Build ---" -ForegroundColor Cyan

# 1. Verification
if (!(Test-Path "src/ui/assets/logo.ico")) {
    Write-Error "Branding assets not found! Run asset generation first."
    exit
}

# 2. Build Single-File Executable
Write-Host "[1/2] Building Single-File Executable..." -ForegroundColor Yellow
pyinstaller --clean moviebox_sync.spec

# 3. Installer Support
Write-Host "[2/2] Build complete. Single-file exe is at dist/MovieBoxSync.exe" -ForegroundColor Green

if (Get-Command "iscc" -ErrorAction SilentlyContinue) {
    Write-Host "Inno Setup (ISCC) detected. Generating full installer..." -ForegroundColor Yellow
    iscc moviebox_sync_installer.iss
    Write-Host "Full Installer: dist/MovieBoxSync_Setup.exe" -ForegroundColor Green
} else {
    Write-Host "Inno Setup not found in PATH." -ForegroundColor Gray
    Write-Host "To create the full installer, open 'moviebox_sync_installer.iss' in Inno Setup and click 'Compile'." -ForegroundColor White
}

Write-Host "`n--- All tasks completed ---" -ForegroundColor Cyan
