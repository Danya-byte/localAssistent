$ErrorActionPreference = "Stop"

function Get-PythonExecutable {
    $venvPython = Join-Path (Get-Location) ".venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        return (Resolve-Path $venvPython).Path
    }

    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        return $pythonCommand.Source
    }

    throw "Python executable not found. Create .venv or install Python 3.12 and add it to PATH."
}

$iconPath = Join-Path (Get-Location) "assets\branding\app.ico"
$readmePath = Join-Path (Get-Location) "README.md"
$pythonExe = Get-PythonExecutable

if (-not (Test-Path $iconPath)) {
    throw "Brand icon not found at assets\branding\app.ico."
}

if (-not (Test-Path $readmePath)) {
    throw "README.md not found."
}

try {
    & $pythonExe -c "import PyInstaller" | Out-Null
} catch {
    throw "PyInstaller is not installed in the active Python environment. Run 'pip install -e .[dev]'."
}

New-Item -ItemType Directory -Force -Path "dist" | Out-Null
New-Item -ItemType Directory -Force -Path "build\pyinstaller" | Out-Null

& $pythonExe -m PyInstaller `
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
