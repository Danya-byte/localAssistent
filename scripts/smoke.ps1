param(
    [string]$ExecutablePath = ".\\dist\\LocalAssistant\\LocalAssistant.exe",
    [int]$WaitSeconds = 4
)

$ErrorActionPreference = "Stop"

$resolvedExe = Resolve-Path $ExecutablePath -ErrorAction Stop
$smokeRoot = Join-Path (Get-Location) "build\\smoke"
$logPath = Join-Path $smokeRoot "logs\\app.log"

if (Test-Path $smokeRoot) {
    Remove-Item -Recurse -Force $smokeRoot
}

New-Item -ItemType Directory -Force -Path $smokeRoot | Out-Null

$previousPlatform = $env:QT_QPA_PLATFORM
$previousHome = $env:LOCAL_ASSISTANT_HOME
$env:QT_QPA_PLATFORM = "offscreen"
$env:LOCAL_ASSISTANT_HOME = $smokeRoot
$process = $null

try {
    $process = Start-Process -FilePath $resolvedExe -PassThru
    Start-Sleep -Seconds $WaitSeconds

    if ($process.HasExited) {
        throw "Smoke launch exited early with code $($process.ExitCode)."
    }

    if (-not (Test-Path $logPath)) {
        throw "Smoke launch did not create the expected log file at $logPath."
    }

    Get-Content -Path $logPath
} finally {
    if ($process -and -not $process.HasExited) {
        Stop-Process -Id $process.Id -Force
    }

    if ($null -eq $previousPlatform) {
        Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
    } else {
        $env:QT_QPA_PLATFORM = $previousPlatform
    }

    if ($null -eq $previousHome) {
        Remove-Item Env:LOCAL_ASSISTANT_HOME -ErrorAction SilentlyContinue
    } else {
        $env:LOCAL_ASSISTANT_HOME = $previousHome
    }
}
