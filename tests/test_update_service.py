from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

from tests._support import PROJECT_ROOT  # noqa: F401

from local_assistant.services.update_service import PatchLaunchPlan, ReleaseCheck, RuntimeManifest, UpdateService


class UpdateServiceTests(unittest.TestCase):
    @staticmethod
    def _manifest_payload(**overrides) -> dict[str, object]:
        payload: dict[str, object] = {
            "schema_version": 2,
            "app_version": "0.2.0",
            "runtime_version": "llama.cpp-b4179",
            "update_kind": "installer",
            "installer_asset_name": "LocalAssistantSetup.exe",
            "installer_sha256": "a" * 64,
            "patch_asset_name": "LocalAssistantPatch.zip",
            "patch_bundle_sha256": "1" * 64,
            "runtime_bundle_sha256": "",
            "runtime_files": {},
            "installer_source_url": "",
            "patch_bundle_url": "",
            "runtime_source_url": "https://github.com/ggml-org/llama.cpp",
            "requires_runtime_replace": True,
            "min_supported_from_version": "",
            "patched_files": [],
        }
        payload.update(overrides)
        return payload

    def test_load_bundled_manifest_accepts_schema_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "app_version": "0.1.0",
                        "runtime_version": "llama.cpp-b4179",
                        "update_kind": "installer",
                        "installer_asset_name": "LocalAssistantSetup.exe",
                        "installer_sha256": "0" * 64,
                        "patch_asset_name": "LocalAssistantPatch.zip",
                        "patch_bundle_sha256": "0" * 64,
                        "runtime_bundle_sha256": "",
                        "runtime_files": {},
                        "installer_source_url": "",
                        "patch_bundle_url": "",
                        "runtime_source_url": "https://github.com/ggml-org/llama.cpp",
                        "requires_runtime_replace": True,
                        "min_supported_from_version": "",
                        "patched_files": [],
                    }
                ),
                encoding="utf-8",
            )
            service = UpdateService(manifest_path=manifest_path)

            manifest = service.load_bundled_manifest()

            self.assertEqual(manifest.source, "bundled")
            self.assertEqual(manifest.error, "")
            self.assertEqual(manifest.schema_version, 2)

    def test_fetch_runtime_manifest_returns_soft_error(self) -> None:
        service = UpdateService(manifest_path=Path("unused.json"))
        service._fetch_json = lambda url: (None, "Network error while fetching runtime updates: offline")  # type: ignore[method-assign]

        manifest = service.fetch_runtime_manifest()

        self.assertEqual(manifest.source, "remote")
        self.assertIn("offline", manifest.error)

    def test_check_latest_release_detects_update(self) -> None:
        service = UpdateService(manifest_path=Path("unused.json"))
        release_payload = (  # type: ignore[method-assign]
            {
                "tag_name": "v0.2.1",
                "html_url": "https://example.com/release",
                "assets": [
                    {
                        "name": "LocalAssistantSetup.exe",
                        "browser_download_url": "https://example.com/LocalAssistantSetup.exe",
                    },
                    {
                        "name": "LocalAssistant-manifest.json",
                        "browser_download_url": "https://example.com/LocalAssistant-manifest.json",
                    }
                ],
            },
            "",
        )
        manifest_payload = {
            "schema_version": 2,
            "app_version": "0.2.1",
            "runtime_version": "llama.cpp-b4179",
            "update_kind": "installer",
            "installer_asset_name": "LocalAssistantSetup.exe",
            "installer_sha256": "a" * 64,
            "patch_asset_name": "LocalAssistantPatch.zip",
            "patch_bundle_sha256": "1" * 64,
            "runtime_bundle_sha256": "",
            "runtime_files": {},
            "installer_source_url": "",
            "patch_bundle_url": "",
            "runtime_source_url": "https://github.com/ggml-org/llama.cpp",
            "requires_runtime_replace": True,
            "min_supported_from_version": "",
            "patched_files": [],
        }
        service._fetch_json = lambda url: (manifest_payload, "") if "manifest" in url else release_payload  # type: ignore[method-assign]

        release = service.check_latest_release()

        self.assertIsInstance(release, ReleaseCheck)
        self.assertTrue(release.update_available)
        self.assertEqual(release.latest_version, "0.2.1")
        self.assertTrue(release.installer_available)
        self.assertEqual(release.installer_url, "https://example.com/LocalAssistantSetup.exe")
        self.assertEqual(release.update_kind, "installer")

    def test_check_latest_release_parses_manifest_asset(self) -> None:
        service = UpdateService(manifest_path=Path("unused.json"))
        release_payload = (
            {
                "tag_name": "v0.2.0",
                "html_url": "https://example.com/release",
                "assets": [
                    {
                        "name": "LocalAssistant-manifest.json",
                        "browser_download_url": "https://example.com/LocalAssistant-manifest.json",
                    }
                ],
            },
            "",
        )
        manifest_payload = {
            "schema_version": 2,
            "app_version": "0.2.0",
            "runtime_version": "llama.cpp-b4179",
            "update_kind": "installer",
            "installer_asset_name": "LocalAssistantSetup.exe",
            "installer_sha256": "a" * 64,
            "patch_asset_name": "LocalAssistantPatch.zip",
            "patch_bundle_sha256": "1" * 64,
            "runtime_bundle_sha256": "",
            "runtime_files": {},
            "installer_source_url": "",
            "patch_bundle_url": "",
            "runtime_source_url": "https://github.com/ggml-org/llama.cpp",
            "requires_runtime_replace": True,
            "min_supported_from_version": "",
            "patched_files": [],
        }
        service._fetch_json = lambda url: (manifest_payload, "") if "manifest" in url else release_payload  # type: ignore[method-assign]

        release = service.check_latest_release()

        self.assertEqual(release.manifest_url, "https://example.com/LocalAssistant-manifest.json")

    def test_check_latest_release_detects_patch_update(self) -> None:
        service = UpdateService(manifest_path=Path("unused.json"))
        release_payload = (
            {
                "tag_name": "v0.1.1",
                "html_url": "https://example.com/release",
                "assets": [
                    {
                        "name": "LocalAssistantSetup.exe",
                        "browser_download_url": "https://example.com/LocalAssistantSetup.exe",
                    },
                    {
                        "name": "LocalAssistantPatch.zip",
                        "browser_download_url": "https://example.com/LocalAssistantPatch.zip",
                    },
                    {
                        "name": "LocalAssistant-manifest.json",
                        "browser_download_url": "https://example.com/LocalAssistant-manifest.json",
                    },
                ],
            },
            "",
        )
        manifest_payload = {
            "schema_version": 2,
            "app_version": "0.1.1",
            "runtime_version": "llama.cpp-b4179",
            "update_kind": "patch",
            "installer_asset_name": "LocalAssistantSetup.exe",
            "installer_sha256": "a" * 64,
            "patch_asset_name": "LocalAssistantPatch.zip",
            "patch_bundle_sha256": "2" * 64,
            "runtime_bundle_sha256": "3" * 64,
            "runtime_files": {},
            "installer_source_url": "",
            "patch_bundle_url": "https://example.com/LocalAssistantPatch.zip",
            "runtime_source_url": "https://github.com/ggml-org/llama.cpp",
            "requires_runtime_replace": False,
            "min_supported_from_version": "0.1.0",
            "patched_files": ["LocalAssistant.exe"],
        }
        service._fetch_json = lambda url: (manifest_payload, "") if "manifest" in url else release_payload  # type: ignore[method-assign]

        release = service.check_latest_release()

        self.assertIsInstance(release, ReleaseCheck)
        self.assertTrue(release.patch_available)
        self.assertEqual(release.update_kind, "patch")
        self.assertEqual(release.patch_url, "https://example.com/LocalAssistantPatch.zip")

    def test_invalid_manifest_returns_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "manifest.json"
            manifest_path.write_text(json.dumps({"schema_version": 2, "app_version": "0.1.0"}), encoding="utf-8")
            service = UpdateService(manifest_path=manifest_path)

            manifest = service.load_bundled_manifest()

            self.assertIn("installer_sha256", manifest.error)

    def test_prepare_installer_rejects_checksum_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            installer_path = temp_root / "LocalAssistantSetup.exe"
            installer_path.write_bytes(b"demo-installer")
            manifest_path = temp_root / "LocalAssistant-manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "app_version": "0.1.0",
                        "runtime_version": "llama.cpp-b4179",
                        "update_kind": "installer",
                        "installer_asset_name": "LocalAssistantSetup.exe",
                        "installer_sha256": "1" * 64,
                        "patch_asset_name": "LocalAssistantPatch.zip",
                        "patch_bundle_sha256": "0" * 64,
                        "runtime_bundle_sha256": "",
                        "runtime_files": {},
                        "installer_source_url": "",
                        "patch_bundle_url": "",
                        "runtime_source_url": "https://github.com/ggml-org/llama.cpp",
                        "requires_runtime_replace": True,
                        "min_supported_from_version": "",
                        "patched_files": [],
                    }
                ),
                encoding="utf-8",
            )
            service = UpdateService(manifest_path=manifest_path, cache_dir=temp_root)
            service._check_authenticode_status = lambda path: "unsigned"  # type: ignore[method-assign]

            with self.assertRaises(RuntimeError):
                service.prepare_installer(prefer_latest=False)

    def test_prepare_installer_rejects_bundled_placeholder_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            installer_path = temp_root / "LocalAssistantSetup.exe"
            installer_path.write_bytes(b"demo-installer")
            bundled_manifest_path = temp_root / "updates-manifest.json"
            bundled_manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "app_version": "0.1.0",
                        "runtime_version": "llama.cpp-b4179",
                        "update_kind": "installer",
                        "installer_asset_name": "LocalAssistantSetup.exe",
                        "installer_sha256": "0" * 64,
                        "patch_asset_name": "LocalAssistantPatch.zip",
                        "patch_bundle_sha256": "0" * 64,
                        "runtime_bundle_sha256": "",
                        "runtime_files": {},
                        "installer_source_url": "",
                        "patch_bundle_url": "",
                        "runtime_source_url": "https://github.com/ggml-org/llama.cpp",
                        "requires_runtime_replace": True,
                        "min_supported_from_version": "",
                        "patched_files": [],
                    }
                ),
                encoding="utf-8",
            )
            service = UpdateService(manifest_path=bundled_manifest_path, cache_dir=temp_root)

            with self.assertRaisesRegex(RuntimeError, "Trusted release manifest is not available"):
                service.prepare_installer(prefer_latest=False)

    def test_check_latest_release_rejects_placeholder_release_manifest(self) -> None:
        service = UpdateService(manifest_path=Path("unused.json"))
        release_payload = (
            {
                "tag_name": "v0.2.0",
                "html_url": "https://example.com/release",
                "assets": [
                    {
                        "name": "LocalAssistantSetup.exe",
                        "browser_download_url": "https://example.com/LocalAssistantSetup.exe",
                    },
                    {
                        "name": "LocalAssistant-manifest.json",
                        "browser_download_url": "https://example.com/LocalAssistant-manifest.json",
                    },
                ],
            },
            "",
        )
        manifest_payload = {
            "schema_version": 2,
            "app_version": "0.2.0",
            "runtime_version": "llama.cpp-b4179",
            "update_kind": "installer",
            "installer_asset_name": "LocalAssistantSetup.exe",
            "installer_sha256": "0" * 64,
            "patch_asset_name": "LocalAssistantPatch.zip",
            "patch_bundle_sha256": "1" * 64,
            "runtime_bundle_sha256": "",
            "runtime_files": {},
            "installer_source_url": "",
            "patch_bundle_url": "",
            "runtime_source_url": "https://github.com/ggml-org/llama.cpp",
            "requires_runtime_replace": True,
            "min_supported_from_version": "",
            "patched_files": [],
        }
        service._fetch_json = lambda url: (manifest_payload, "") if "manifest" in url else release_payload  # type: ignore[method-assign]

        release = service.check_latest_release()

        self.assertFalse(release.installer_available)
        self.assertIn("missing or invalid", release.error)

    def test_prepare_patch_rejects_unexpected_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            patch_path = temp_root / "LocalAssistantPatch.zip"
            with ZipFile(patch_path, "w") as archive:
                archive.writestr("_internal/runtime/llama-server.exe", "bad")
            manifest_path = temp_root / "LocalAssistant-manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "app_version": "0.1.1",
                        "runtime_version": "llama.cpp-b4179",
                        "update_kind": "patch",
                        "installer_asset_name": "LocalAssistantSetup.exe",
                        "installer_sha256": "1" * 64,
                        "patch_asset_name": "LocalAssistantPatch.zip",
                        "patch_bundle_sha256": UpdateService._sha256_file(patch_path),
                        "runtime_bundle_sha256": "2" * 64,
                        "runtime_files": {},
                        "installer_source_url": "",
                        "patch_bundle_url": "https://example.com/LocalAssistantPatch.zip",
                        "runtime_source_url": "https://github.com/ggml-org/llama.cpp",
                        "requires_runtime_replace": False,
                        "min_supported_from_version": "0.1.0",
                        "patched_files": ["_internal/runtime/llama-server.exe"],
                    }
                ),
                encoding="utf-8",
            )
            service = UpdateService(manifest_path=manifest_path, cache_dir=temp_root)
            service._download_file = lambda url, destination: destination.write_bytes(patch_path.read_bytes())  # type: ignore[method-assign]

            with self.assertRaisesRegex(RuntimeError, "protected files"):
                service.prepare_patch("https://example.com/LocalAssistantPatch.zip", "", current_version="0.1.0")

    def test_prepare_patch_returns_launch_plan_for_valid_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            patch_path = temp_root / "LocalAssistantPatch.zip"
            with ZipFile(patch_path, "w") as archive:
                archive.writestr("LocalAssistant.exe", "patched")
            manifest_path = temp_root / "LocalAssistant-manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "app_version": "0.1.1",
                        "runtime_version": "llama.cpp-b4179",
                        "update_kind": "patch",
                        "installer_asset_name": "LocalAssistantSetup.exe",
                        "installer_sha256": "1" * 64,
                        "patch_asset_name": "LocalAssistantPatch.zip",
                        "patch_bundle_sha256": UpdateService._sha256_file(patch_path),
                        "runtime_bundle_sha256": "2" * 64,
                        "runtime_files": {},
                        "installer_source_url": "",
                        "patch_bundle_url": "https://example.com/LocalAssistantPatch.zip",
                        "runtime_source_url": "https://github.com/ggml-org/llama.cpp",
                        "requires_runtime_replace": False,
                        "min_supported_from_version": "0.1.0",
                        "patched_files": ["LocalAssistant.exe"],
                    }
                ),
                encoding="utf-8",
            )
            service = UpdateService(manifest_path=manifest_path, cache_dir=temp_root)
            service._download_file = lambda url, destination: destination.write_bytes(patch_path.read_bytes())  # type: ignore[method-assign]

            plan = service.prepare_patch("https://example.com/LocalAssistantPatch.zip", "", current_version="0.1.0")

            self.assertIsInstance(plan, PatchLaunchPlan)
            self.assertTrue(plan.patch_path.exists())

    def test_prepare_installer_persists_release_manifest_next_to_cached_installer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            installer_path = temp_root / "source-installer.exe"
            installer_path.write_bytes(b"demo-installer")
            installer_hash = UpdateService._sha256_file(installer_path)
            manifest_payload = {
                "schema_version": 2,
                "app_version": "0.2.0",
                "runtime_version": "llama.cpp-b4179",
                "update_kind": "installer",
                "installer_asset_name": "LocalAssistantSetup.exe",
                "installer_sha256": installer_hash,
                "patch_asset_name": "LocalAssistantPatch.zip",
                "patch_bundle_sha256": "1" * 64,
                "runtime_bundle_sha256": "",
                "runtime_files": {},
                "installer_source_url": "",
                "patch_bundle_url": "",
                "runtime_source_url": "https://github.com/ggml-org/llama.cpp",
                "requires_runtime_replace": True,
                "min_supported_from_version": "",
                "patched_files": [],
            }
            service = UpdateService(manifest_path=Path("unused.json"), cache_dir=temp_root)
            service._fetch_json = lambda url: (manifest_payload, "")  # type: ignore[method-assign]
            service._download_file = lambda url, destination: destination.write_bytes(installer_path.read_bytes())  # type: ignore[method-assign]
            service._check_authenticode_status = lambda path: "unsigned"  # type: ignore[method-assign]

            plan = service.prepare_installer(
                installer_url="https://example.com/LocalAssistantSetup.exe",
                manifest_url="https://example.com/LocalAssistant-manifest.json",
                prefer_latest=True,
            )

            self.assertTrue(plan.installer_path.exists())
            self.assertEqual(plan.manifest_source, "release")
            self.assertTrue((temp_root / "LocalAssistant-manifest.json").exists())

    def test_load_parse_fetch_and_download_helpers_cover_error_paths(self) -> None:
        service = UpdateService(manifest_path=Path("unused.json"))

        with tempfile.TemporaryDirectory() as temp_dir:
            invalid_manifest = Path(temp_dir) / "manifest.json"
            invalid_manifest.write_text("{oops", encoding="utf-8")
            loaded = service._load_manifest_from_path(invalid_manifest, source="local")  # noqa: SLF001
            self.assertIn("Unable to read", loaded.error)

        manifest = service._parse_manifest("oops", source="release")  # noqa: SLF001
        self.assertIn("invalid", manifest.error)
        manifest = service._parse_manifest(self._manifest_payload(update_kind="weird"), source="release")  # noqa: SLF001
        self.assertIn("update_kind", manifest.error)
        manifest = service._parse_manifest(self._manifest_payload(installer_sha256="bad"), source="release")  # noqa: SLF001
        self.assertIn("installer_sha256", manifest.error)
        manifest = service._parse_manifest(self._manifest_payload(update_kind="patch", patch_bundle_sha256="", patched_files=[]), source="release")  # noqa: SLF001
        self.assertIn("patch_bundle_sha256", manifest.error)
        manifest = service._parse_manifest(self._manifest_payload(runtime_files={"bad": "oops"}), source="release")  # noqa: SLF001
        self.assertIn("runtime_files", manifest.error)
        manifest = service._parse_manifest(self._manifest_payload(patched_files=["../evil"]), source="release")  # noqa: SLF001
        self.assertIn("patched_files", manifest.error)

        class FakeResponse:
            def __init__(self, payload: str) -> None:
                self._payload = payload

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self) -> bytes:
                return self._payload.encode("utf-8")

        with patch("local_assistant.services.update_service.urlopen", return_value=FakeResponse('{"ok": true}')):
            payload, error = service._fetch_json("https://example.com")  # noqa: SLF001
        self.assertEqual(payload, {"ok": True})
        self.assertEqual(error, "")

        with patch("local_assistant.services.update_service.urlopen", side_effect=HTTPError("https://example.com", 500, "boom", hdrs=None, fp=None)):
            self.assertIn("HTTP 500", service._fetch_json("https://example.com")[1])  # noqa: SLF001
        with patch("local_assistant.services.update_service.urlopen", side_effect=URLError("offline")):
            self.assertIn("offline", service._fetch_json("https://example.com")[1])  # noqa: SLF001
        with patch("local_assistant.services.update_service.urlopen", side_effect=TimeoutError):
            self.assertIn("timed out", service._fetch_json("https://example.com")[1])  # noqa: SLF001
        with patch("local_assistant.services.update_service.urlopen", return_value=FakeResponse("not json")):
            self.assertIn("valid JSON", service._fetch_json("https://example.com")[1])  # noqa: SLF001

        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "installer.exe"
            with patch("local_assistant.services.update_service.urlopen", return_value=FakeResponse("demo")):
                service._download_file("https://example.com/setup.exe", destination)  # noqa: SLF001
            self.assertEqual(destination.read_text(encoding="utf-8"), "demo")
            with patch("local_assistant.services.update_service.urlopen", side_effect=HTTPError("https://example.com", 404, "missing", hdrs=None, fp=None)):
                with self.assertRaisesRegex(RuntimeError, "HTTP 404"):
                    service._download_file("https://example.com/setup.exe", destination)  # noqa: SLF001
            with patch("local_assistant.services.update_service.urlopen", side_effect=URLError("offline")):
                with self.assertRaisesRegex(RuntimeError, "offline"):
                    service._download_file("https://example.com/setup.exe", destination)  # noqa: SLF001
            with patch("local_assistant.services.update_service.urlopen", side_effect=TimeoutError):
                with self.assertRaisesRegex(RuntimeError, "timed out"):
                    service._download_file("https://example.com/setup.exe", destination)  # noqa: SLF001

    def test_launch_and_manifest_resolution_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            installer = root / "LocalAssistantSetup.exe"
            installer.write_bytes(b"demo")
            service = UpdateService(cache_dir=root)

            with patch("local_assistant.services.update_service.subprocess.Popen") as popen_mock:
                service.launch_installer(installer)
            self.assertIn("/VERYSILENT", popen_mock.call_args.args[0])

            with self.assertRaisesRegex(RuntimeError, "Installer not found"):
                service.launch_installer(root / "missing.exe")

            patch_zip = root / "LocalAssistantPatch.zip"
            patch_zip.write_bytes(b"zip")
            updater_script = root / "_internal" / "updates" / "apply_patch_update.ps1"
            updater_script.parent.mkdir(parents=True, exist_ok=True)
            updater_script.write_text("Write-Host ok", encoding="utf-8")
            app_exe = root / "LocalAssistant.exe"
            app_exe.write_text("x", encoding="utf-8")
            with (
                patch("local_assistant.services.update_service.application_root", return_value=root),
                patch("local_assistant.services.update_service.bundled_manifest_path", return_value=root / "updates" / "LocalAssistant-manifest.json"),
                patch("local_assistant.services.update_service.subprocess.Popen") as popen_mock,
            ):
                service.launch_patch_updater(patch_zip, current_pid=99)
            command = popen_mock.call_args.args[0]
            self.assertIn("-WaitPid", command)
            self.assertIn("99", command)

            with self.assertRaisesRegex(RuntimeError, "Patch bundle not found"):
                service.launch_patch_updater(root / "missing.zip")

            app_exe.unlink()
            with (
                patch("local_assistant.services.update_service.application_root", return_value=root),
                patch("local_assistant.services.update_service.bundled_manifest_path", return_value=root / "updates" / "LocalAssistant-manifest.json"),
            ):
                with self.assertRaisesRegex(RuntimeError, "Application executable is missing"):
                    service.launch_patch_updater(patch_zip)

            release_manifest = RuntimeManifest(**self._manifest_payload(), source="release", error="")
            local_manifest = root / "LocalAssistant-manifest.json"
            local_manifest.write_text(json.dumps(self._manifest_payload(installer_sha256="0" * 64)), encoding="utf-8")
            service._fetch_json = lambda url: (self._manifest_payload(), "")  # type: ignore[method-assign]
            resolved = service._resolve_manifest_for_launch("https://example.com/manifest.json", root, purpose="installer")  # noqa: SLF001
            self.assertEqual(resolved.source, "release")
            self.assertTrue(local_manifest.exists())
            local_manifest.write_text(json.dumps(self._manifest_payload(installer_sha256="0" * 64)), encoding="utf-8")
            service._fetch_json = lambda url: (None, "offline")  # type: ignore[method-assign]
            unresolved = service._resolve_manifest_for_launch("https://example.com/manifest.json", root, purpose="installer")  # noqa: SLF001
            self.assertIn("missing or invalid", unresolved.error)
            _ = release_manifest

    def test_verification_and_helper_statics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            installer = root / "LocalAssistantSetup.exe"
            installer.write_bytes(b"demo-installer")
            patch_zip = root / "LocalAssistantPatch.zip"
            with ZipFile(patch_zip, "w") as archive:
                archive.writestr("LocalAssistant.exe", "patched")
            service = UpdateService(cache_dir=root)

            installer_manifest = RuntimeManifest(**self._manifest_payload(installer_sha256=UpdateService._sha256_file(installer)), source="release", error="")
            with patch.object(service, "_check_authenticode_status", return_value="invalid"):
                with self.assertRaisesRegex(RuntimeError, "signature is invalid"):
                    service._verify_installer(installer, installer_manifest)  # noqa: SLF001

            patch_manifest = RuntimeManifest(
                **self._manifest_payload(
                    update_kind="patch",
                    requires_runtime_replace=False,
                    patch_bundle_sha256=UpdateService._sha256_file(patch_zip),
                    patched_files=["LocalAssistant.exe"],
                ),
                source="release",
                error="",
            )
            service._verify_patch_bundle(patch_zip, patch_manifest)  # noqa: SLF001

            with self.assertRaisesRegex(RuntimeError, "checksum mismatch"):
                service._verify_patch_bundle(  # noqa: SLF001
                    patch_zip,
                    RuntimeManifest(
                        **self._manifest_payload(
                            update_kind="patch",
                            requires_runtime_replace=False,
                            patch_bundle_sha256="f" * 64,
                            patched_files=["LocalAssistant.exe"],
                        ),
                        source="release",
                        error="",
                    ),
                )

            bad_zip = root / "bad.zip"
            bad_zip.write_text("not zip", encoding="utf-8")
            bad_zip_manifest = RuntimeManifest(
                **self._manifest_payload(
                    update_kind="patch",
                    requires_runtime_replace=False,
                    patch_bundle_sha256=UpdateService._sha256_file(bad_zip),
                    patched_files=["LocalAssistant.exe"],
                ),
                source="release",
                error="",
            )
            with self.assertRaisesRegex(RuntimeError, "valid zip archive"):
                service._verify_patch_bundle(bad_zip, bad_zip_manifest)  # noqa: SLF001

            empty_zip = root / "empty.zip"
            with ZipFile(empty_zip, "w"):
                pass
            empty_manifest = RuntimeManifest(
                **self._manifest_payload(
                    update_kind="patch",
                    requires_runtime_replace=False,
                    patch_bundle_sha256=UpdateService._sha256_file(empty_zip),
                    patched_files=["LocalAssistant.exe"],
                ),
                source="release",
                error="",
            )
            with self.assertRaisesRegex(RuntimeError, "bundle is empty"):
                service._verify_patch_bundle(empty_zip, empty_manifest)  # noqa: SLF001

        self.assertEqual(UpdateService._find_installer_asset_url({"assets": [{"name": "LocalAssistantSetup.exe", "browser_download_url": "x"}]}), "x")
        self.assertEqual(UpdateService._find_manifest_asset_url({"assets": [{"name": "LocalAssistant-manifest.json", "browser_download_url": "y"}]}), "y")
        self.assertEqual(UpdateService._find_patch_asset_url({"assets": [{"name": "LocalAssistantPatch.zip", "browser_download_url": "z"}]}), "z")
        self.assertEqual(UpdateService._find_installer_asset_url({"assets": "bad"}), "")
        self.assertEqual(UpdateService._normalize_patch_entry("\\foo\\bar"), "foo/bar")
        with self.assertRaisesRegex(RuntimeError, "invalid path"):
            UpdateService._normalize_patch_entry("../evil")
        self.assertTrue(UpdateService._is_sha256("a" * 64))
        self.assertFalse(UpdateService._is_sha256("bad"))
        self.assertTrue(UpdateService._is_placeholder_sha256("0" * 64))
        self.assertFalse(UpdateService._is_placeholder_sha256("a" * 64))
        self.assertEqual(UpdateService._version_tuple("v1.2.3"), (1, 2, 3))
        self.assertEqual(UpdateService._version_tuple("oops"), (0,))

        manifest = RuntimeManifest(**self._manifest_payload(installer_sha256="0" * 64), source="release", error="")
        service = UpdateService()
        self.assertFalse(service._is_trusted_manifest_for_launch(manifest, purpose="installer"))  # noqa: SLF001
        self.assertIn("invalid", service._manifest_trust_error(manifest, purpose="installer"))  # noqa: SLF001
        self.assertFalse(service._is_trusted_manifest_for_launch(RuntimeManifest(**self._manifest_payload(), source="bundled", error=""), purpose="installer"))  # noqa: SLF001

        completed = Mock(returncode=0, stdout="Valid\n")
        with patch("local_assistant.services.update_service.subprocess.run", return_value=completed):
            self.assertEqual(UpdateService._check_authenticode_status(Path("demo.exe")), "valid")
        completed = Mock(returncode=0, stdout="NotSigned\n")
        with patch("local_assistant.services.update_service.subprocess.run", return_value=completed):
            self.assertEqual(UpdateService._check_authenticode_status(Path("demo.exe")), "unsigned")
        completed = Mock(returncode=0, stdout="HashMismatch\n")
        with patch("local_assistant.services.update_service.subprocess.run", return_value=completed):
            self.assertEqual(UpdateService._check_authenticode_status(Path("demo.exe")), "invalid")
        with patch("local_assistant.services.update_service.subprocess.run", side_effect=OSError):
            self.assertEqual(UpdateService._check_authenticode_status(Path("demo.exe")), "unknown")


if __name__ == "__main__":
    unittest.main()
