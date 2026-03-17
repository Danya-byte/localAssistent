from __future__ import annotations

import contextlib
import json
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from ..config import DEFAULT_LOCAL_CONTEXT, DEFAULT_LOCAL_RUNTIME_PORT, LOCAL_RUNTIME_BINARY_NAME, AppPaths, application_root, resolve_asset
from ..exceptions import ProviderError


@dataclass(slots=True)
class RuntimeVerification:
    status: str
    detail: str = ""
    binary_path: Path | None = None


class LocalRuntimeService:
    def __init__(self, paths: AppPaths) -> None:
        self.paths = paths
        self.host = "127.0.0.1"
        self.port = DEFAULT_LOCAL_RUNTIME_PORT
        self._process: subprocess.Popen[str] | None = None
        self._active_model_path: str | None = None

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}/v1"

    def runtime_binary_path(self) -> Path | None:
        verification = self.verify_runtime_bundle()
        return verification.binary_path

    def verify_runtime_bundle(self) -> RuntimeVerification:
        for candidate in self._candidate_runtime_paths():
            if not candidate.exists():
                continue
            runtime_dir = candidate.parent
            missing_files = [name for name in ("llama.dll", "ggml.dll", "ggml-base.dll", "ggml-cpu.dll") if not (runtime_dir / name).exists()]
            if missing_files:
                continue
            try:
                result = subprocess.run(  # noqa: S603
                    [str(candidate), "--help"],
                    cwd=str(runtime_dir),
                    capture_output=True,
                    text=True,
                    timeout=10,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    check=False,
                )
            except OSError as exc:
                continue
            except subprocess.TimeoutExpired:
                continue
            if result.returncode == 0:
                return RuntimeVerification(status="ready", binary_path=candidate)
        if any(path.exists() for path in self._candidate_runtime_paths()):
            return RuntimeVerification(status="invalid_bundle", detail="Bundled local runtime is incomplete or damaged.")
        return RuntimeVerification(status="missing_binary", detail="Bundled local runtime is missing from this installation.")

    def is_binary_available(self) -> bool:
        return self.verify_runtime_bundle().status == "ready"

    def ensure_runtime(self, model_path: str, context_length: int = DEFAULT_LOCAL_CONTEXT) -> None:
        verification = self.verify_runtime_bundle()
        if verification.status != "ready" or verification.binary_path is None:
            raise ProviderError(verification.detail or "Local runtime is not installed yet.")
        if self._process and self._process.poll() is None and self._active_model_path == model_path and self._is_ready():
            return
        self.stop()
        binary = verification.binary_path
        log_path = self.paths.logs_dir / "llama-server.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        command = [
            str(binary),
            "--host",
            self.host,
            "--port",
            str(self.port),
            "--model",
            model_path,
            "--ctx-size",
            str(max(2048, context_length)),
            "--n-predict",
            "512",
        ]
        with log_path.open("a", encoding="utf-8") as log_file:
            self._process = subprocess.Popen(  # noqa: S603
                command,
                cwd=str(binary.parent),
                stdout=log_file,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        self._active_model_path = model_path
        deadline = time.time() + 25
        while time.time() < deadline:
            if self._process and self._process.poll() is not None:
                raise ProviderError(self._runtime_start_failure_detail(log_path))
            if self._is_ready():
                return
            time.sleep(0.4)
        raise ProviderError("Local runtime did not become ready in time.")

    def stop(self) -> None:
        if self._process is None:
            return
        if self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
        self._process = None
        self._active_model_path = None

    def is_port_in_use(self) -> bool:
        with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            sock.settimeout(0.3)
            return sock.connect_ex((self.host, self.port)) == 0

    def _is_ready(self) -> bool:
        try:
            with urlopen(f"{self.base_url}/models", timeout=2) as response:  # noqa: S310
                payload = json.loads(response.read().decode("utf-8"))
            return isinstance(payload, dict) and isinstance(payload.get("data"), list)
        except (OSError, ValueError, URLError):
            return False

    def _candidate_runtime_paths(self) -> list[Path]:
        app_root = application_root()
        candidates: list[Path] = []
        if not getattr(sys, "frozen", False):
            candidates.append(self.paths.runtime_dir / LOCAL_RUNTIME_BINARY_NAME)
        candidates.extend(
            [
                app_root / "runtime" / LOCAL_RUNTIME_BINARY_NAME,
                resolve_asset("runtime", LOCAL_RUNTIME_BINARY_NAME),
            ]
        )

        unique: list[Path] = []
        seen: set[Path] = set()
        for candidate in candidates:
            resolved = candidate.resolve()
            if resolved not in seen:
                seen.add(resolved)
                unique.append(candidate)
        return unique

    @staticmethod
    def _runtime_start_failure_detail(log_path: Path) -> str:
        if not log_path.exists():
            return "Local runtime exited before it became ready."
        try:
            tail = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()[-40:]
        except OSError:
            return "Local runtime exited before it became ready."
        for line in reversed(tail):
            lowered = line.lower()
            if "unknown pre-tokenizer type" in lowered:
                detail = line.strip()
                return f"Local runtime could not load the selected model. {detail}"
            if "failed to load model" in lowered or "error loading model" in lowered:
                detail = line.strip()
                return f"Local runtime could not load the selected model. {detail}"
        return "Local runtime exited before it became ready."
