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

$projectRoot = Get-Location
$pythonExe = Get-PythonExecutable
$installerPath = Join-Path $projectRoot "dist\LocalAssistantSetup.exe"
$manifestPath = Join-Path $projectRoot "release\LocalAssistant-manifest.json"
$patchPath = Join-Path $projectRoot "release\LocalAssistantPatch.zip"

Assert-Path $installerPath "Installer artifact is missing at dist\LocalAssistantSetup.exe."
Assert-Path $manifestPath "Release manifest is missing at release\LocalAssistant-manifest.json."
Assert-Path $patchPath "Patch bundle is missing at release\LocalAssistantPatch.zip."

$env:PYTHONPATH = "src;."
@'
import json
import shutil
import tempfile
from pathlib import Path

from local_assistant.services.update_service import UpdateService

project_root = Path.cwd()
installer_path = project_root / "dist" / "LocalAssistantSetup.exe"
manifest_path = project_root / "release" / "LocalAssistant-manifest.json"
patch_path = project_root / "release" / "LocalAssistantPatch.zip"

manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
service = UpdateService(manifest_path=project_root / "updates" / "manifest.json")

if UpdateService._sha256_file(installer_path) != manifest["installer_sha256"]:
    raise SystemExit("Release manifest installer_sha256 does not match dist\\LocalAssistantSetup.exe.")

if UpdateService._sha256_file(patch_path) != manifest["patch_bundle_sha256"]:
    raise SystemExit("Release manifest patch_bundle_sha256 does not match release\\LocalAssistantPatch.zip.")

cache_root = Path(tempfile.mkdtemp(prefix="local-assistant-release-verify-"))
try:
    cached_installer = cache_root / "LocalAssistantSetup.exe"
    cached_manifest = cache_root / "LocalAssistant-manifest.json"
    shutil.copy2(installer_path, cached_installer)
    shutil.copy2(manifest_path, cached_manifest)

    verification_service = UpdateService(
        manifest_path=project_root / "updates" / "manifest.json",
        cache_dir=cache_root,
    )
    verification_service._check_authenticode_status = lambda path: "unsigned"  # type: ignore[method-assign]
    plan = verification_service.prepare_installer(prefer_latest=False)
    if plan.installer_path != cached_installer:
        raise SystemExit("Installer verification did not use the cached release installer.")
    if plan.manifest_source != "local":
        raise SystemExit("Installer verification did not use the cached release manifest.")
finally:
    shutil.rmtree(cache_root, ignore_errors=True)
'@ | & $pythonExe -
