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

$pythonExe = Get-PythonExecutable
& $pythonExe -m coverage erase
& $pythonExe -m coverage run --branch -m unittest discover -s tests -t .
& $pythonExe -m coverage report --show-missing --skip-covered --fail-under=90
& $pythonExe -m coverage xml -o coverage.xml
