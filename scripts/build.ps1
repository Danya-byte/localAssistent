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

function Assert-Path([string]$path, [string]$message) {
    if (-not (Test-Path $path)) {
        throw $message
    }
}

function Test-FlatRuntimeBundle([string]$runtimeRoot) {
    $requiredFiles = @(
        "llama-server.exe",
        "llama.dll",
        "ggml.dll",
        "ggml-base.dll",
        "ggml-cpu.dll",
        "ggml-rpc.dll",
        "llava_shared.dll",
        "llama.cpp.txt"
    )
    foreach ($name in $requiredFiles) {
        Assert-Path (Join-Path $runtimeRoot $name) "Required runtime file is missing: runtime\\$name"
    }

    $unexpectedExecutables = Get-ChildItem -Path $runtimeRoot -Filter *.exe -File | Where-Object { $_.Name -ne "llama-server.exe" }
    if ($unexpectedExecutables) {
        throw "Runtime bundle contains unexpected executables: $($unexpectedExecutables.Name -join ', ')"
    }

    $unexpectedDirectories = Get-ChildItem -Path $runtimeRoot -Directory
    if ($unexpectedDirectories) {
        throw "Runtime bundle contains unexpected directories: $($unexpectedDirectories.Name -join ', ')"
    }

    & (Join-Path $runtimeRoot "llama-server.exe") --help | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Bundled local runtime failed verification. Check the runtime bundle in runtime\\."
    }
}

$projectRoot = Get-Location
$iconPath = Join-Path $projectRoot "assets\branding\app.ico"
$brandingPath = Join-Path $projectRoot "assets\branding"
$modelsPath = Join-Path $projectRoot "assets\models"
$photoPath = Join-Path $projectRoot "assets\photo"
$runtimePath = Join-Path $projectRoot "runtime"
$updatesPath = Join-Path $projectRoot "updates"
$readmePath = Join-Path $projectRoot "README.md"
$noticesPath = Join-Path $projectRoot "THIRD_PARTY_NOTICES.md"
$versionPath = Join-Path $projectRoot "VERSION.txt"
$pythonExe = Get-PythonExecutable

Assert-Path $iconPath "Brand icon not found at assets\branding\app.ico."
Assert-Path $brandingPath "Brand assets not found at assets\branding."
Assert-Path $photoPath "Photo assets not found at assets\photo."
Assert-Path $modelsPath "Model catalog assets not found at assets\models."
Assert-Path $updatesPath "Runtime update assets not found at updates."
Assert-Path $readmePath "README.md not found."
Assert-Path $noticesPath "THIRD_PARTY_NOTICES.md not found."
Assert-Path $versionPath "VERSION.txt not found."

Test-FlatRuntimeBundle -runtimeRoot $runtimePath

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
    --add-data "${brandingPath};assets\branding" `
    --add-data "${modelsPath};assets\models" `
    --add-data "${photoPath};assets\photo" `
    --add-data "${runtimePath};runtime" `
    --add-data "${updatesPath};updates" `
    --add-data "${readmePath};." `
    --add-data "${noticesPath};." `
    --add-data "${versionPath};." `
    "src\launcher.py"

$builtExe = Join-Path $projectRoot "build\pyinstaller\LocalAssistant\LocalAssistant.exe"
$distExe = Join-Path $projectRoot "dist\LocalAssistant\LocalAssistant.exe"
Assert-Path $builtExe "PyInstaller did not produce build\\pyinstaller\\LocalAssistant\\LocalAssistant.exe."
Copy-Item $builtExe $distExe -Force
