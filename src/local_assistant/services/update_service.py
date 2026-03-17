from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..config import (
    APP_VERSION,
    GITHUB_RELEASE_API_URL,
    INSTALLER_ASSET_NAME,
    PATCH_BUNDLE_ASSET_NAME,
    PATCH_UPDATER_SCRIPT_NAME,
    RUNTIME_MANIFEST_ASSET_NAME,
    RUNTIME_MANIFEST_URL,
    RUNTIME_UPDATE_TIMEOUT_SECONDS,
    RUNTIME_UPDATE_USER_AGENT,
    application_root,
    bundled_manifest_path,
)
from ..models import InstalledLocalModel, LocalModelDescriptor, ModelDescriptor, ProviderHealth


@dataclass(slots=True)
class RuntimeManifest:
    schema_version: int = 0
    app_version: str = ""
    runtime_version: str = ""
    update_kind: str = "installer"
    installer_asset_name: str = ""
    installer_sha256: str = ""
    patch_asset_name: str = ""
    patch_bundle_sha256: str = ""
    runtime_bundle_sha256: str = ""
    runtime_files: dict[str, str] | None = None
    installer_source_url: str = ""
    patch_bundle_url: str = ""
    runtime_source_url: str = ""
    requires_runtime_replace: bool = False
    min_supported_from_version: str = ""
    patched_files: list[str] | None = None
    source: str = ""
    error: str = ""


@dataclass(slots=True)
class ReleaseCheck:
    current_version: str
    latest_version: str = ""
    release_url: str = ""
    installer_url: str = ""
    patch_url: str = ""
    manifest_url: str = ""
    installer_available: bool = False
    patch_available: bool = False
    update_kind: str = "installer"
    requires_runtime_replace: bool = False
    update_available: bool = False
    error: str = ""


@dataclass(slots=True)
class RuntimeStatus:
    current_version: str
    latest_version: str = ""
    release_url: str = ""
    installer_url: str = ""
    patch_url: str = ""
    manifest_url: str = ""
    installer_available: bool = False
    patch_available: bool = False
    update_kind: str = "installer"
    last_check_status: str = "idle"
    last_check_error: str = ""
    last_checked_at: str = ""
    update_available: bool = False
    repair_required: bool = False
    repair_reason: str = ""


@dataclass(slots=True)
class RuntimeRefreshResult:
    status: RuntimeStatus
    update_available: bool = False
    local_status: str = "error"
    local_detail: str = ""
    active_model_id: str = ""
    runtime_ready: bool = False
    installer_url: str = ""
    patch_url: str = ""
    manifest_url: str = ""
    installer_available: bool = False
    patch_available: bool = False
    update_kind: str = "installer"
    repair_required: bool = False
    repair_reason: str = ""
    error: str = ""
    provider_health: ProviderHealth | None = None
    provider_models: list[ModelDescriptor] | None = None
    local_models: list[LocalModelDescriptor] | None = None
    installed_local_models: list[InstalledLocalModel] | None = None
    runtime_binary_available: bool = False


@dataclass(slots=True)
class InstallerLaunchPlan:
    installer_path: Path
    source: str
    installer_url: str = ""
    manifest_source: str = ""
    signature_status: str = ""


@dataclass(slots=True)
class PatchLaunchPlan:
    patch_path: Path
    source: str
    patch_url: str = ""
    manifest_source: str = ""


class UpdateService:
    TRUSTED_MANIFEST_UNAVAILABLE = "Trusted release manifest is not available for update verification."
    RELEASE_MANIFEST_INVALID = "Release manifest is missing or invalid for this release."

    def __init__(
        self,
        manifest_path: Path | None = None,
        manifest_url: str = RUNTIME_MANIFEST_URL,
        release_api_url: str = GITHUB_RELEASE_API_URL,
        cache_dir: Path | None = None,
    ) -> None:
        self.manifest_path = manifest_path or bundled_manifest_path()
        self.manifest_url = manifest_url
        self.release_api_url = release_api_url
        self.cache_dir = cache_dir

    def load_bundled_manifest(self) -> RuntimeManifest:
        return self._load_manifest_from_path(self.manifest_path, source="bundled")

    def fetch_runtime_manifest(self) -> RuntimeManifest:
        payload, error = self._fetch_json(self.manifest_url)
        if error:
            return RuntimeManifest(source="remote", error=error)
        return self._parse_manifest(payload, source="remote")

    def check_latest_release(self) -> ReleaseCheck:
        payload, error = self._fetch_json(self.release_api_url)
        if error:
            return ReleaseCheck(current_version=APP_VERSION, error=error)
        if not isinstance(payload, dict):
            return ReleaseCheck(current_version=APP_VERSION, error="Release metadata payload is invalid.")
        latest_version = str(payload.get("tag_name", "")).strip().removeprefix("v")
        release_url = str(payload.get("html_url", "")).strip()
        installer_url = self._find_installer_asset_url(payload)
        patch_url = self._find_patch_asset_url(payload)
        manifest_url = self._find_manifest_asset_url(payload)
        if not latest_version:
            return ReleaseCheck(current_version=APP_VERSION, error="Latest release version is missing.")
        manifest = RuntimeManifest(source="release")
        if manifest_url:
            manifest_payload, manifest_error = self._fetch_json(manifest_url)
            if manifest_error:
                return ReleaseCheck(current_version=APP_VERSION, error=manifest_error)
            manifest = self._parse_manifest(manifest_payload, source="release")
            if manifest.error:
                return ReleaseCheck(current_version=APP_VERSION, error=manifest.error)
            if not self._is_trusted_manifest_for_launch(manifest, purpose=manifest.update_kind):
                return ReleaseCheck(
                    current_version=APP_VERSION,
                    latest_version=latest_version,
                    release_url=release_url,
                    installer_url=installer_url,
                    patch_url=patch_url,
                    manifest_url=manifest_url,
                    error=self.RELEASE_MANIFEST_INVALID,
                )
            if manifest.patch_bundle_url:
                patch_url = manifest.patch_bundle_url
        elif installer_url or patch_url:
            return ReleaseCheck(
                current_version=APP_VERSION,
                latest_version=latest_version,
                release_url=release_url,
                installer_url=installer_url,
                patch_url=patch_url,
                error=self.RELEASE_MANIFEST_INVALID,
            )
        return ReleaseCheck(
            current_version=APP_VERSION,
            latest_version=latest_version,
            release_url=release_url,
            installer_url=installer_url,
            patch_url=patch_url,
            manifest_url=manifest_url,
            installer_available=bool(installer_url),
            patch_available=bool(patch_url) and manifest.update_kind == "patch",
            update_kind=manifest.update_kind,
            requires_runtime_replace=manifest.requires_runtime_replace,
            update_available=self._version_tuple(latest_version) > self._version_tuple(APP_VERSION),
        )

    def find_local_installer(self) -> Path | None:
        roots: list[Path] = [application_root()]
        if self.cache_dir is not None:
            roots.append(self.cache_dir)
        parent = application_root().parent
        if parent not in roots:
            roots.append(parent)
        for root in roots:
            candidate = root / INSTALLER_ASSET_NAME
            if candidate.exists():
                return candidate
        return None

    def prepare_installer(
        self,
        installer_url: str = "",
        manifest_url: str = "",
        *,
        prefer_latest: bool = False,
    ) -> InstallerLaunchPlan:
        local_installer = self.find_local_installer()
        if local_installer is not None and not prefer_latest:
            manifest = self._resolve_manifest_for_launch(manifest_url, local_installer.parent, purpose="installer")
            if manifest.error:
                raise RuntimeError(manifest.error)
            if not manifest.installer_sha256:
                raise RuntimeError("Trusted installer hash is missing from the runtime manifest.")
            signature_status = self._verify_installer(local_installer, manifest)
            return InstallerLaunchPlan(
                installer_path=local_installer,
                source="local",
                manifest_source=manifest.source,
                signature_status=signature_status,
            )
        if not installer_url.strip():
            raise RuntimeError("Installer is not available for this release.")
        if self.cache_dir is None:
            raise RuntimeError("Installer cache directory is not configured.")
        manifest = self._resolve_manifest_for_launch(manifest_url, self.cache_dir, purpose="installer")
        if manifest.error:
            raise RuntimeError(manifest.error)
        if not manifest.installer_sha256:
            raise RuntimeError("Trusted installer hash is missing from the runtime manifest.")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        destination = self.cache_dir / INSTALLER_ASSET_NAME
        self._download_file(installer_url, destination)
        signature_status = self._verify_installer(destination, manifest)
        return InstallerLaunchPlan(
            installer_path=destination,
            source="downloaded",
            installer_url=installer_url,
            manifest_source=manifest.source,
            signature_status=signature_status,
        )

    def prepare_patch(
        self,
        patch_url: str = "",
        manifest_url: str = "",
        *,
        current_version: str = APP_VERSION,
    ) -> PatchLaunchPlan:
        if self.cache_dir is None:
            raise RuntimeError("Patch cache directory is not configured.")
        manifest = self._resolve_manifest_for_launch(manifest_url, self.cache_dir, purpose="patch")
        if manifest.error:
            raise RuntimeError(manifest.error)
        if manifest.update_kind != "patch":
            raise RuntimeError("This release requires the installer update path.")
        if manifest.requires_runtime_replace:
            raise RuntimeError("Runtime updates require the installer update path.")
        if manifest.min_supported_from_version:
            if self._version_tuple(current_version) < self._version_tuple(manifest.min_supported_from_version):
                raise RuntimeError("This patch does not support the current installed version.")
        resolved_patch_url = manifest.patch_bundle_url or patch_url.strip()
        if not resolved_patch_url:
            raise RuntimeError("Patch bundle is not available for this release.")
        if not manifest.patch_bundle_sha256 or not self._is_sha256(manifest.patch_bundle_sha256):
            raise RuntimeError("Trusted patch hash is missing from the runtime manifest.")

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        destination = self.cache_dir / PATCH_BUNDLE_ASSET_NAME
        self._download_file(resolved_patch_url, destination)
        self._verify_patch_bundle(destination, manifest)
        return PatchLaunchPlan(
            patch_path=destination,
            source="downloaded",
            patch_url=resolved_patch_url,
            manifest_source=manifest.source,
        )

    def launch_installer(self, installer_path: Path) -> None:
        if not installer_path.exists():
            raise RuntimeError(f"Installer not found: {installer_path}")
        subprocess.Popen(  # noqa: S603
            [str(installer_path), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
            cwd=str(installer_path.parent),
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0),
        )

    def launch_patch_updater(self, patch_path: Path, *, current_pid: int | None = None) -> None:
        if not patch_path.exists():
            raise RuntimeError(f"Patch bundle not found: {patch_path}")
        updater_script = application_root() / "_internal" / "updates" / PATCH_UPDATER_SCRIPT_NAME
        if not updater_script.exists():
            updater_script = application_root() / "updates" / PATCH_UPDATER_SCRIPT_NAME
        if not updater_script.exists():
            updater_script = bundled_manifest_path().parent / PATCH_UPDATER_SCRIPT_NAME
        if not updater_script.exists():
            raise RuntimeError("Patch updater helper is missing from this installation.")
        app_executable = application_root() / "LocalAssistant.exe"
        if not app_executable.exists():
            raise RuntimeError("Application executable is missing from this installation.")
        pid = current_pid if current_pid is not None else os.getpid()
        subprocess.Popen(  # noqa: S603
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(updater_script),
                "-AppRoot",
                str(application_root()),
                "-PatchZip",
                str(patch_path),
                "-AppExe",
                str(app_executable),
                "-WaitPid",
                str(pid),
            ],
            cwd=str(application_root()),
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0),
        )

    def _load_manifest_from_path(self, path: Path, source: str) -> RuntimeManifest:
        if not path.exists():
            return RuntimeManifest(source=source, error=f"Manifest file not found: {path.name}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception as exc:  # noqa: BLE001
            return RuntimeManifest(source=source, error=f"Unable to read {source} manifest: {exc}")
        return self._parse_manifest(payload, source=source)

    def _parse_manifest(self, payload: Any, source: str) -> RuntimeManifest:
        if not isinstance(payload, dict):
            return RuntimeManifest(source=source, error=f"{source.capitalize()} manifest payload is invalid.")
        try:
            schema_version = int(payload.get("schema_version", 0) or 0)
        except (TypeError, ValueError):
            schema_version = 0
        app_version = str(payload.get("app_version", "")).strip()
        update_kind = str(payload.get("update_kind", "installer")).strip().lower() or "installer"
        installer_sha256 = str(payload.get("installer_sha256", "")).strip().lower()
        patch_bundle_sha256 = str(payload.get("patch_bundle_sha256", "")).strip().lower()
        runtime_bundle_sha256 = str(payload.get("runtime_bundle_sha256", "")).strip().lower()
        runtime_version = str(payload.get("runtime_version", "")).strip()
        installer_asset_name = str(payload.get("installer_asset_name", "")).strip() or INSTALLER_ASSET_NAME
        patch_asset_name = str(payload.get("patch_asset_name", "")).strip() or PATCH_BUNDLE_ASSET_NAME
        installer_source_url = str(payload.get("installer_source_url", "")).strip()
        patch_bundle_url = str(payload.get("patch_bundle_url", "")).strip()
        runtime_source_url = str(payload.get("runtime_source_url", "")).strip()
        requires_runtime_replace = bool(payload.get("requires_runtime_replace", False))
        min_supported_from_version = str(payload.get("min_supported_from_version", "")).strip()
        runtime_files_payload = payload.get("runtime_files", {})
        runtime_files = runtime_files_payload if isinstance(runtime_files_payload, dict) else {}
        patched_files_payload = payload.get("patched_files", [])
        patched_files = patched_files_payload if isinstance(patched_files_payload, list) else []

        if schema_version != 2:
            return RuntimeManifest(source=source, error=f"{source.capitalize()} manifest schema_version must be 2.")
        if not app_version:
            return RuntimeManifest(source=source, error=f"{source.capitalize()} manifest is missing app_version.")
        if update_kind not in {"patch", "installer"}:
            return RuntimeManifest(source=source, error=f"{source.capitalize()} manifest has an invalid update_kind.")
        if not installer_sha256 or not self._is_sha256(installer_sha256):
            return RuntimeManifest(source=source, error=f"{source.capitalize()} manifest has an invalid installer_sha256.")
        if patch_bundle_sha256 and not self._is_sha256(patch_bundle_sha256):
            return RuntimeManifest(source=source, error=f"{source.capitalize()} manifest has an invalid patch_bundle_sha256.")
        if runtime_bundle_sha256 and not self._is_sha256(runtime_bundle_sha256):
            return RuntimeManifest(source=source, error=f"{source.capitalize()} manifest has an invalid runtime_bundle_sha256.")
        normalized_runtime_files: dict[str, str] = {}
        for relative_path, file_hash in runtime_files.items():
            key = str(relative_path).replace("\\", "/").strip()
            value = str(file_hash).strip().lower()
            if not key or not self._is_sha256(value):
                return RuntimeManifest(source=source, error=f"{source.capitalize()} manifest has an invalid runtime_files entry.")
            normalized_runtime_files[key] = value
        normalized_patched_files: list[str] = []
        for relative_path in patched_files:
            key = str(relative_path).replace("\\", "/").strip()
            if not key or key.startswith("/") or ".." in key.split("/"):
                return RuntimeManifest(source=source, error=f"{source.capitalize()} manifest has an invalid patched_files entry.")
            normalized_patched_files.append(key)
        if update_kind == "patch":
            if not patch_bundle_sha256:
                return RuntimeManifest(source=source, error=f"{source.capitalize()} manifest is missing patch_bundle_sha256.")
            if not normalized_patched_files:
                return RuntimeManifest(source=source, error=f"{source.capitalize()} manifest is missing patched_files.")
            if requires_runtime_replace:
                return RuntimeManifest(source=source, error=f"{source.capitalize()} patch manifest cannot require runtime replacement.")
        return RuntimeManifest(
            schema_version=schema_version,
            app_version=app_version,
            runtime_version=runtime_version,
            update_kind=update_kind,
            installer_asset_name=installer_asset_name,
            installer_sha256=installer_sha256,
            patch_asset_name=patch_asset_name,
            patch_bundle_sha256=patch_bundle_sha256,
            runtime_bundle_sha256=runtime_bundle_sha256,
            runtime_files=normalized_runtime_files,
            installer_source_url=installer_source_url,
            patch_bundle_url=patch_bundle_url,
            runtime_source_url=runtime_source_url,
            requires_runtime_replace=requires_runtime_replace,
            min_supported_from_version=min_supported_from_version,
            patched_files=normalized_patched_files,
            source=source,
        )

    def _fetch_json(self, url: str) -> tuple[Any | None, str]:
        request = Request(url=url, method="GET")
        request.add_header("User-Agent", RUNTIME_UPDATE_USER_AGENT)
        request.add_header("Accept", "application/json")
        try:
            with urlopen(request, timeout=RUNTIME_UPDATE_TIMEOUT_SECONDS) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            return None, f"HTTP {exc.code} while fetching runtime updates."
        except URLError as exc:
            return None, f"Network error while fetching runtime updates: {exc.reason}"
        except TimeoutError:
            return None, "Runtime update request timed out."
        try:
            return json.loads(raw), ""
        except json.JSONDecodeError:
            return None, "Runtime update payload is not valid JSON."

    def _download_file(self, url: str, destination: Path) -> None:
        request = Request(url=url, method="GET")
        request.add_header("User-Agent", RUNTIME_UPDATE_USER_AGENT)
        try:
            with urlopen(request, timeout=max(30, RUNTIME_UPDATE_TIMEOUT_SECONDS)) as response:
                destination.write_bytes(response.read())
        except HTTPError as exc:
            raise RuntimeError(f"HTTP {exc.code} while downloading installer.") from exc
        except URLError as exc:
            raise RuntimeError(f"Network error while downloading installer: {exc.reason}") from exc
        except TimeoutError as exc:
            raise RuntimeError("Installer download timed out.") from exc

    @staticmethod
    def _find_installer_asset_url(payload: dict[str, Any]) -> str:
        assets = payload.get("assets")
        if not isinstance(assets, list):
            return ""
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            name = str(asset.get("name", "")).strip()
            if name != INSTALLER_ASSET_NAME:
                continue
            return str(asset.get("browser_download_url", "")).strip()
        return ""

    @staticmethod
    def _find_manifest_asset_url(payload: dict[str, Any]) -> str:
        assets = payload.get("assets")
        if not isinstance(assets, list):
            return ""
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            name = str(asset.get("name", "")).strip()
            if name != RUNTIME_MANIFEST_ASSET_NAME:
                continue
            return str(asset.get("browser_download_url", "")).strip()
        return ""

    @staticmethod
    def _find_patch_asset_url(payload: dict[str, Any]) -> str:
        assets = payload.get("assets")
        if not isinstance(assets, list):
            return ""
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            name = str(asset.get("name", "")).strip()
            if name != PATCH_BUNDLE_ASSET_NAME:
                continue
            return str(asset.get("browser_download_url", "")).strip()
        return ""

    def _resolve_manifest_for_launch(self, manifest_url: str, local_dir: Path | None = None, *, purpose: str) -> RuntimeManifest:
        local_error = ""
        if local_dir is not None:
            sibling_manifest = local_dir / RUNTIME_MANIFEST_ASSET_NAME
            if sibling_manifest.exists():
                manifest = self._load_manifest_from_path(sibling_manifest, source="local")
                if not manifest.error and self._is_trusted_manifest_for_launch(manifest, purpose=purpose):
                    return manifest
                local_error = manifest.error or self._manifest_trust_error(manifest, purpose=purpose)
        if manifest_url.strip():
            payload, error = self._fetch_json(manifest_url)
            if not error:
                manifest = self._parse_manifest(payload, source="release")
                if not manifest.error and self._is_trusted_manifest_for_launch(manifest, purpose=purpose):
                    if local_dir is not None:
                        sibling_manifest = local_dir / RUNTIME_MANIFEST_ASSET_NAME
                        sibling_manifest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
                    return manifest
                if manifest.error:
                    return manifest
                return RuntimeManifest(source=manifest.source, error=self._manifest_trust_error(manifest, purpose=purpose))
        if local_error:
            return RuntimeManifest(source="local", error=local_error)
        return RuntimeManifest(source="release", error=self.TRUSTED_MANIFEST_UNAVAILABLE)

    def _verify_installer(self, installer_path: Path, manifest: RuntimeManifest) -> str:
        if not installer_path.exists():
            raise RuntimeError(f"Installer not found: {installer_path}")
        digest = self._sha256_file(installer_path)
        if digest.lower() != manifest.installer_sha256.lower():
            raise RuntimeError("Installer verification failed: checksum mismatch.")
        signature_status = self._check_authenticode_status(installer_path)
        if signature_status not in {"valid", "unsigned"}:
            raise RuntimeError("Installer verification failed: signature is invalid.")
        return signature_status

    def _verify_patch_bundle(self, patch_path: Path, manifest: RuntimeManifest) -> None:
        if not patch_path.exists():
            raise RuntimeError(f"Patch bundle not found: {patch_path}")
        digest = self._sha256_file(patch_path)
        if digest.lower() != manifest.patch_bundle_sha256.lower():
            raise RuntimeError("Patch verification failed: checksum mismatch.")
        allowed_files = set(manifest.patched_files or [])
        if not allowed_files:
            raise RuntimeError("Patch verification failed: no approved files were provided.")
        try:
            with zipfile.ZipFile(patch_path) as archive:
                archive_names = {
                    self._normalize_patch_entry(name)
                    for name in archive.namelist()
                    if not name.endswith("/")
                }
        except zipfile.BadZipFile as exc:
            raise RuntimeError("Patch verification failed: bundle is not a valid zip archive.") from exc
        if not archive_names:
            raise RuntimeError("Patch verification failed: bundle is empty.")
        disallowed = sorted(name for name in archive_names if name not in allowed_files)
        if disallowed:
            raise RuntimeError(f"Patch verification failed: bundle contains unexpected files: {', '.join(disallowed[:5])}")
        forbidden_roots = ("_internal/runtime/", "runtime/", "models/", "data/")
        if any(name.startswith(forbidden_roots) or name == INSTALLER_ASSET_NAME for name in archive_names):
            raise RuntimeError("Patch verification failed: bundle attempts to replace protected files.")

    @staticmethod
    def _normalize_patch_entry(value: str) -> str:
        normalized = str(value).replace("\\", "/").strip().lstrip("/")
        if not normalized or ".." in normalized.split("/"):
            raise RuntimeError("Patch verification failed: bundle contains an invalid path.")
        return normalized

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _check_authenticode_status(path: Path) -> str:
        escaped_path = str(path).replace("'", "''")
        command = [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            f"(Get-AuthenticodeSignature -LiteralPath '{escaped_path}').Status",
        ]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError:
            return "unknown"
        status = (completed.stdout or "").strip()
        if completed.returncode != 0:
            return "unknown"
        normalized = status.lower()
        if normalized == "valid":
            return "valid"
        if normalized in {"notsigned", "unknownerror", ""}:
            return "unsigned"
        return "invalid"

    @staticmethod
    def _is_sha256(value: str) -> bool:
        return bool(re.fullmatch(r"[a-fA-F0-9]{64}", value))

    @staticmethod
    def _is_placeholder_sha256(value: str) -> bool:
        normalized = value.strip().lower()
        return bool(normalized) and len(normalized) == 64 and set(normalized) == {"0"}

    def _is_trusted_manifest_for_launch(self, manifest: RuntimeManifest, *, purpose: str) -> bool:
        if manifest.error:
            return False
        if manifest.source == "bundled":
            return False
        if self._is_placeholder_sha256(manifest.installer_sha256):
            return False
        if purpose == "patch" and self._is_placeholder_sha256(manifest.patch_bundle_sha256):
            return False
        return True

    def _manifest_trust_error(self, manifest: RuntimeManifest, *, purpose: str) -> str:
        if manifest.error:
            return manifest.error
        if manifest.source == "bundled":
            return self.TRUSTED_MANIFEST_UNAVAILABLE
        if self._is_placeholder_sha256(manifest.installer_sha256):
            return self.RELEASE_MANIFEST_INVALID
        if purpose == "patch" and self._is_placeholder_sha256(manifest.patch_bundle_sha256):
            return self.RELEASE_MANIFEST_INVALID
        return self.RELEASE_MANIFEST_INVALID

    @staticmethod
    def _version_tuple(value: str) -> tuple[int, ...]:
        numbers = re.findall(r"\d+", value)
        return tuple(int(item) for item in numbers) if numbers else (0,)
