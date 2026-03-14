$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    throw "Virtual environment not found. Create .venv and install dependencies first."
}

$env:PYTHONPATH = "src"
if (-not $env:LOCAL_ASSISTANT_HOME) {
    $env:LOCAL_ASSISTANT_HOME = Join-Path (Get-Location) ".local-runtime"
}
& ".\.venv\Scripts\python.exe" -m local_assistant
