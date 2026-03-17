param(
    [Parameter(Mandatory = $true)]
    [string]$AppRoot,
    [Parameter(Mandatory = $true)]
    [string]$PatchZip,
    [Parameter(Mandatory = $true)]
    [string]$AppExe,
    [Parameter(Mandatory = $true)]
    [int]$WaitPid
)

$ErrorActionPreference = "Stop"

function Wait-ProcessExit([int]$Pid, [int]$TimeoutSeconds) {
    if ($Pid -le 0) {
        return
    }
    try {
        $process = Get-Process -Id $Pid -ErrorAction Stop
        $null = $process.WaitForExit($TimeoutSeconds * 1000)
    } catch {
        return
    }
}

function Copy-Tree([string]$SourceRoot, [string]$TargetRoot, [string]$BackupRoot) {
    $files = Get-ChildItem -Path $SourceRoot -Recurse -File
    foreach ($file in $files) {
        $relative = [System.IO.Path]::GetRelativePath($SourceRoot, $file.FullName)
        $targetPath = Join-Path $TargetRoot $relative
        $backupPath = Join-Path $BackupRoot $relative
        $targetDir = Split-Path -Parent $targetPath
        $backupDir = Split-Path -Parent $backupPath
        if (-not (Test-Path $targetDir)) {
            New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
        }
        if (-not (Test-Path $backupDir)) {
            New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
        }
        if (Test-Path $targetPath) {
            Copy-Item $targetPath $backupPath -Force
        }
        Copy-Item $file.FullName $targetPath -Force
    }
}

function Restore-Tree([string]$BackupRoot, [string]$TargetRoot) {
    if (-not (Test-Path $BackupRoot)) {
        return
    }
    $files = Get-ChildItem -Path $BackupRoot -Recurse -File
    foreach ($file in $files) {
        $relative = [System.IO.Path]::GetRelativePath($BackupRoot, $file.FullName)
        $targetPath = Join-Path $TargetRoot $relative
        $targetDir = Split-Path -Parent $targetPath
        if (-not (Test-Path $targetDir)) {
            New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
        }
        Copy-Item $file.FullName $targetPath -Force
    }
}

$appRootPath = [System.IO.Path]::GetFullPath($AppRoot)
$patchZipPath = [System.IO.Path]::GetFullPath($PatchZip)
$appExePath = [System.IO.Path]::GetFullPath($AppExe)

if (-not (Test-Path $patchZipPath)) {
    throw "Patch bundle not found: $patchZipPath"
}

Wait-ProcessExit -Pid $WaitPid -TimeoutSeconds 60

$sessionRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("local-assistant-patch-" + [guid]::NewGuid().ToString())
$extractRoot = Join-Path $sessionRoot "extract"
$backupRoot = Join-Path $sessionRoot "backup"
New-Item -ItemType Directory -Force -Path $extractRoot | Out-Null
New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null

try {
    Expand-Archive -Path $patchZipPath -DestinationPath $extractRoot -Force
    Copy-Tree -SourceRoot $extractRoot -TargetRoot $appRootPath -BackupRoot $backupRoot
} catch {
    Restore-Tree -BackupRoot $backupRoot -TargetRoot $appRootPath
    throw
} finally {
    if (Test-Path $sessionRoot) {
        Remove-Item -Recurse -Force $sessionRoot -ErrorAction SilentlyContinue
    }
}

Start-Process -FilePath $appExePath -WorkingDirectory (Split-Path -Parent $appExePath)
