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

function Get-HashHex([string]$path) {
    return (Get-FileHash -Algorithm SHA256 $path).Hash.ToLowerInvariant()
}

function Get-RelativeUnixPath([string]$root, [string]$path) {
    $normalizedRoot = [System.IO.Path]::GetFullPath($root)
    $normalizedPath = [System.IO.Path]::GetFullPath($path)
    if ($normalizedPath.StartsWith($normalizedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        $relative = $normalizedPath.Substring($normalizedRoot.Length).TrimStart("\")
        return $relative.Replace("\", "/")
    }
    return [System.IO.Path]::GetFileName($normalizedPath)
}

function Get-RuntimeInfo([string]$runtimeDir) {
    $runtimeFiles = [ordered]@{}
    $hashLines = New-Object System.Collections.Generic.List[string]
    foreach ($file in Get-ChildItem -Path $runtimeDir -File | Sort-Object Name) {
        $relativePath = Get-RelativeUnixPath $runtimeDir $file.FullName
        $hash = Get-HashHex $file.FullName
        $runtimeFiles[$relativePath] = $hash
        $hashLines.Add("$relativePath=$hash")
    }
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes(($hashLines -join "`n"))
        $runtimeBundleHash = [System.BitConverter]::ToString($sha.ComputeHash($bytes)).Replace("-", "").ToLowerInvariant()
    } finally {
        $sha.Dispose()
    }
    return @{
        RuntimeFiles = $runtimeFiles
        RuntimeBundleHash = $runtimeBundleHash
    }
}

function Load-BundledManifest([string]$manifestPath) {
    if (-not (Test-Path $manifestPath)) {
        return $null
    }
    try {
        return Get-Content -Path $manifestPath -Raw | ConvertFrom-Json
    } catch {
        return $null
    }
}

function New-PatchStage([string]$sourceDir, [string]$stageDir) {
    New-Item -ItemType Directory -Force -Path $stageDir | Out-Null
    $itemsToCopy = @(
        "LocalAssistant.exe",
        "_internal\assets",
        "_internal\README.md",
        "_internal\THIRD_PARTY_NOTICES.md",
        "_internal\VERSION.txt",
        "_internal\updates\apply_patch_update.ps1"
    )
    foreach ($relativePath in $itemsToCopy) {
        $sourcePath = Join-Path $sourceDir $relativePath
        if (-not (Test-Path $sourcePath)) {
            continue
        }
        $destinationPath = Join-Path $stageDir $relativePath
        $destinationParent = Split-Path -Parent $destinationPath
        if (-not (Test-Path $destinationParent)) {
            New-Item -ItemType Directory -Force -Path $destinationParent | Out-Null
        }
        Copy-Item $sourcePath $destinationPath -Recurse -Force
    }
}

function Get-PatchInventory([string]$stageDir) {
    $patchedFiles = New-Object System.Collections.Generic.List[string]
    foreach ($file in Get-ChildItem -Path $stageDir -Recurse -File | Sort-Object FullName) {
        $patchedFiles.Add((Get-RelativeUnixPath $stageDir $file.FullName))
    }
    return $patchedFiles
}

function New-ReleaseManifest(
    [string]$version,
    [string]$installerPath,
    [string]$patchPath,
    [string]$runtimeDir,
    [string]$outputPath,
    [string]$updateKind,
    [bool]$requiresRuntimeReplace,
    [string]$baselineVersion,
    [System.Collections.Generic.List[string]]$patchedFiles
) {
    $runtimeInfo = Get-RuntimeInfo $runtimeDir
    $manifest = [ordered]@{
        schema_version = 2
        app_version = $version
        runtime_version = "llama.cpp-b4179"
        update_kind = $updateKind
        installer_asset_name = "LocalAssistantSetup.exe"
        installer_sha256 = (Get-HashHex $installerPath)
        patch_asset_name = "LocalAssistantPatch.zip"
        patch_bundle_sha256 = (Get-HashHex $patchPath)
        runtime_bundle_sha256 = $runtimeInfo.RuntimeBundleHash
        runtime_files = $runtimeInfo.RuntimeFiles
        installer_source_url = ""
        patch_bundle_url = ""
        runtime_source_url = "https://github.com/ggml-org/llama.cpp"
        requires_runtime_replace = $requiresRuntimeReplace
        min_supported_from_version = $baselineVersion
        patched_files = @($patchedFiles)
    }

    $json = $manifest | ConvertTo-Json -Depth 6
    [System.IO.File]::WriteAllText($outputPath, $json, [System.Text.Encoding]::UTF8)
}

$projectRoot = Get-Location
$distDir = Join-Path $projectRoot "dist"
$releaseDir = Join-Path $projectRoot "release"
$installerPath = Join-Path $distDir "LocalAssistantSetup.exe"
$patchPath = Join-Path $releaseDir "LocalAssistantPatch.zip"
$manifestPath = Join-Path $releaseDir "LocalAssistant-manifest.json"
$installerHashPath = Join-Path $releaseDir "LocalAssistantSetup.sha256.txt"
$patchHashPath = Join-Path $releaseDir "LocalAssistantPatch.sha256.txt"
$zipPath = Join-Path $releaseDir "LocalAssistant-win64.zip"
$zipHashPath = Join-Path $releaseDir "LocalAssistant-win64.sha256.txt"
$tempRoot = Join-Path $projectRoot ("build\release-stage\" + [guid]::NewGuid().ToString())
$stageDir = Join-Path $tempRoot "LocalAssistant-win64"
$patchStageDir = Join-Path $tempRoot "patch-stage"
$buildScript = Join-Path $projectRoot "scripts\build.ps1"
$installerScript = Join-Path $projectRoot "scripts\installer.iss"
$runtimeDir = Join-Path $distDir "LocalAssistant\_internal\runtime"
$bundledManifestPath = Join-Path $projectRoot "updates\manifest.json"
$noticesPath = Join-Path $projectRoot "THIRD_PARTY_NOTICES.md"
$versionPath = Join-Path $projectRoot "VERSION.txt"
$version = (Get-Content -Path $versionPath -Raw).Trim()

New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null
New-Item -ItemType Directory -Force -Path $stageDir | Out-Null
New-Item -ItemType Directory -Force -Path $patchStageDir | Out-Null

powershell -ExecutionPolicy Bypass -File $buildScript

Assert-Path (Join-Path $distDir "LocalAssistant\LocalAssistant.exe") "Portable build is missing after PyInstaller step."
Assert-Path $runtimeDir "Minimal runtime bundle is missing after PyInstaller step."
Assert-Path $noticesPath "THIRD_PARTY_NOTICES.md not found."

$runtimeInfo = Get-RuntimeInfo $runtimeDir
$baselineManifest = Load-BundledManifest $bundledManifestPath
$baselineRuntimeHash = ""
$baselineVersion = ""
if ($null -ne $baselineManifest) {
    $baselineRuntimeHash = [string]$baselineManifest.runtime_bundle_sha256
    $baselineVersion = [string]$baselineManifest.app_version
}

$forceInstaller = $env:LOCAL_ASSISTANT_FORCE_INSTALLER_UPDATE -eq "1"
$runtimeUnchanged = (-not [string]::IsNullOrWhiteSpace($baselineRuntimeHash)) -and ($baselineRuntimeHash -eq $runtimeInfo.RuntimeBundleHash)
$requiresRuntimeReplace = -not $runtimeUnchanged
$updateKind = if ($forceInstaller -or $requiresRuntimeReplace) { "installer" } else { "patch" }

New-PatchStage -sourceDir (Join-Path $distDir "LocalAssistant") -stageDir $patchStageDir
$patchedFiles = Get-PatchInventory $patchStageDir
Compress-Archive -Path (Join-Path $patchStageDir "*") -DestinationPath $patchPath -Force

$isccPath = Get-IsccPath
& $isccPath "/DAppVersion=$version" $installerScript

Assert-Path $installerPath "Installer build did not produce dist\LocalAssistantSetup.exe."

New-ReleaseManifest `
    -version $version `
    -installerPath $installerPath `
    -patchPath $patchPath `
    -runtimeDir $runtimeDir `
    -outputPath $manifestPath `
    -updateKind $updateKind `
    -requiresRuntimeReplace $requiresRuntimeReplace `
    -baselineVersion $baselineVersion `
    -patchedFiles $patchedFiles

$installerHashContent = @(
    "File: LocalAssistantSetup.exe",
    "SHA256: $(Get-HashHex $installerPath)"
) -join [Environment]::NewLine
[System.IO.File]::WriteAllText($installerHashPath, $installerHashContent, [System.Text.Encoding]::UTF8)

$patchHashContent = @(
    "File: LocalAssistantPatch.zip",
    "SHA256: $(Get-HashHex $patchPath)"
) -join [Environment]::NewLine
[System.IO.File]::WriteAllText($patchHashPath, $patchHashContent, [System.Text.Encoding]::UTF8)

Copy-Item $installerPath (Join-Path $stageDir "LocalAssistantSetup.exe") -Force
Copy-Item $patchPath (Join-Path $stageDir "LocalAssistantPatch.zip") -Force
Copy-Item $manifestPath (Join-Path $stageDir "LocalAssistant-manifest.json") -Force
Copy-Item $installerHashPath (Join-Path $stageDir "LocalAssistantSetup.sha256.txt") -Force
Copy-Item $patchHashPath (Join-Path $stageDir "LocalAssistantPatch.sha256.txt") -Force
Copy-Item (Join-Path $projectRoot "README.md") (Join-Path $stageDir "README.md") -Force
Copy-Item $noticesPath (Join-Path $stageDir "THIRD_PARTY_NOTICES.md") -Force
Copy-Item $versionPath (Join-Path $stageDir "VERSION.txt") -Force

Compress-Archive -Path (Join-Path $stageDir "*") -DestinationPath $zipPath -Force

$zipHashContent = @(
    "File: LocalAssistant-win64.zip",
    "SHA256: $(Get-HashHex $zipPath)"
) -join [Environment]::NewLine
[System.IO.File]::WriteAllText($zipHashPath, $zipHashContent, [System.Text.Encoding]::UTF8)

Write-Host "Update kind:" $updateKind
Write-Host "Portable bundle:" (Join-Path $distDir "LocalAssistant")
Write-Host "Installer:" $installerPath
Write-Host "Patch bundle:" $patchPath
Write-Host "Installer manifest:" $manifestPath
Write-Host "Installer checksum:" $installerHashPath
Write-Host "Patch checksum:" $patchHashPath
Write-Host "ZIP release:" $zipPath
Write-Host "ZIP checksum:" $zipHashPath
