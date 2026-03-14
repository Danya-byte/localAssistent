$ErrorActionPreference = "Stop"

function Get-IsccPath {
    $command = Get-Command iscc -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $candidates = @(
        "C:\Program Files\Inno Setup 6\ISCC.exe",
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe")
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    throw "Inno Setup compiler not found. Install Inno Setup 6 or add ISCC.exe to PATH."
}

function Assert-Path([string]$path, [string]$message) {
    if (-not (Test-Path $path)) {
        throw $message
    }
}

$projectRoot = Get-Location
$distDir = Join-Path $projectRoot "dist"
$releaseDir = Join-Path $projectRoot "release"
$installerPath = Join-Path $distDir "LocalAssistantSetup.exe"
$zipPath = Join-Path $releaseDir "LocalAssistant-win64.zip"
$zipHashPath = Join-Path $releaseDir "LocalAssistant-win64.sha256.txt"
$tempRoot = Join-Path $projectRoot ("build\release-stage\" + [guid]::NewGuid().ToString())
$stageDir = Join-Path $tempRoot "LocalAssistant-win64"
$buildScript = Join-Path $projectRoot "scripts\build.ps1"
$installerScript = Join-Path $projectRoot "scripts\installer.iss"

New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null
New-Item -ItemType Directory -Force -Path $stageDir | Out-Null

powershell -ExecutionPolicy Bypass -File $buildScript

Assert-Path (Join-Path $distDir "LocalAssistant\LocalAssistant.exe") "Portable build is missing after PyInstaller step."

$isccPath = Get-IsccPath
& $isccPath $installerScript

Assert-Path $installerPath "Installer build did not produce dist\LocalAssistantSetup.exe."

$installerHash = Get-FileHash -Algorithm SHA256 $installerPath
$installerHashContent = @(
    "File: LocalAssistantSetup.exe",
    "SHA256: $($installerHash.Hash)"
) -join [Environment]::NewLine

Copy-Item $installerPath (Join-Path $stageDir "LocalAssistantSetup.exe") -Force
Copy-Item (Join-Path $projectRoot "README.md") (Join-Path $stageDir "README.md") -Force
[System.IO.File]::WriteAllText((Join-Path $stageDir "INSTALLER_SHA256.txt"), $installerHashContent, [System.Text.Encoding]::UTF8)

Compress-Archive -Path (Join-Path $stageDir "*") -DestinationPath $zipPath -Force

$zipHash = Get-FileHash -Algorithm SHA256 $zipPath
$zipHashContent = @(
    "File: LocalAssistant-win64.zip",
    "SHA256: $($zipHash.Hash)"
) -join [Environment]::NewLine
[System.IO.File]::WriteAllText($zipHashPath, $zipHashContent, [System.Text.Encoding]::UTF8)

Write-Host "Portable bundle:" (Join-Path $distDir "LocalAssistant")
Write-Host "Installer:" $installerPath
Write-Host "ZIP release:" $zipPath
Write-Host "ZIP checksum:" $zipHashPath
