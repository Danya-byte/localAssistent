$ErrorActionPreference = "Stop"

$iconPath = Join-Path (Get-Location) "assets\branding\app.ico"
$readmePath = Join-Path (Get-Location) "README.md"

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    throw "Virtual environment not found. Create .venv and install dependencies first."
}

if (-not (Test-Path $iconPath)) {
    throw "Brand icon not found at assets\branding\app.ico."
}

if (-not (Test-Path $readmePath)) {
    throw "README.md not found."
}

try {
    & ".\.venv\Scripts\python.exe" -c "import PyInstaller" | Out-Null
} catch {
    throw "PyInstaller is not installed. Run 'pip install -e .[dev]'."
}

New-Item -ItemType Directory -Force -Path "dist" | Out-Null
New-Item -ItemType Directory -Force -Path "build\pyinstaller" | Out-Null

& ".\.venv\Scripts\python.exe" -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name "LocalAssistant" `
    --icon $iconPath `
    --specpath "build\pyinstaller" `
    --workpath "build\pyinstaller" `
    --paths "src" `
    --hidden-import "PySide6.QtCore" `
    --hidden-import "PySide6.QtGui" `
    --hidden-import "PySide6.QtWidgets" `
    --hidden-import "shiboken6" `
    --add-data "${readmePath};." `
    "src\launcher.py"
