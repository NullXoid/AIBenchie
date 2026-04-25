from __future__ import annotations

import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aibenchie import live_trust_path


BACKEND_IDS = [
    "website_backend",
    "wrapper_backend",
    "windows_backend",
    "android_backend",
    "ios_backend",
]


def find_repo_root() -> Path | None:
    configured = os.getenv("AIBENCHIE_NULLBRIDGE_REPO", "").strip()
    candidates = []
    if configured:
        candidates.append(Path(configured))
    here = Path(__file__).resolve()
    candidates.extend(
        [
            here.parents[2] / "NullBridge",
            here.parents[3] / "NullBridge",
        ]
    )
    for candidate in candidates:
        backend = candidate / "backend"
        if (backend / "scripts" / "nullbridge_api.py").is_file() and (backend / "infra" / "nullbridge").is_dir():
            return candidate
    return None


def free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def generate_service_secrets() -> dict[str, str]:
    return {backend_id: secrets.token_urlsafe(32) for backend_id in BACKEND_IDS}


def copy_static_nullbridge_policy(nullbridge_repo: Path, temp_backend_root: Path) -> None:
    source = nullbridge_repo / "backend" / "infra" / "nullbridge"
    target = temp_backend_root / "infra" / "nullbridge"
    target.mkdir(parents=True, exist_ok=True)
    for path in source.iterdir():
        if path.is_file() and path.suffix.lower() in {".json", ".md"} and path.name != "audit-log.jsonl":
            shutil.copy2(path, target / path.name)


@dataclass
class LocalNullBridgeRun:
    base_url: str
    service_secrets: dict[str, str]
    temp_root: Path
    process: subprocess.Popen

    def stop(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()


class LocalNullBridgeRunner:
    def __init__(self, nullbridge_repo: Path | None = None, timeout_seconds: float = 10.0):
        self.nullbridge_repo = nullbridge_repo or find_repo_root()
        self.timeout_seconds = timeout_seconds
        self._tmp: tempfile.TemporaryDirectory[str] | None = None
        self.run: LocalNullBridgeRun | None = None

    def __enter__(self) -> LocalNullBridgeRun:
        if self.nullbridge_repo is None:
            raise FileNotFoundError("NullBridge repo not found; set AIBENCHIE_NULLBRIDGE_REPO")
        self._tmp = tempfile.TemporaryDirectory(prefix="aibenchie-nullbridge-")
        temp_root = Path(self._tmp.name) / "backend"
        copy_static_nullbridge_policy(self.nullbridge_repo, temp_root)
        secrets_map = generate_service_secrets()
        port = free_loopback_port()
        env = os.environ.copy()
        env.update(
            {
                "NULLBRIDGE_ROOT": str(temp_root),
                "AUTH_MODE": "legacy",
                "NULLBRIDGE_SERVICE_AUTH_METHOD": "signed_jwt",
                "NULLBRIDGE_SERVICE_JWT_SECRETS": json.dumps(secrets_map),
                "NULLBRIDGE_AUTH_DB": str(temp_root / "infra" / "nullbridge" / "state" / "auth" / "auth.db"),
            }
        )
        backend = self.nullbridge_repo / "backend"
        process = subprocess.Popen(
            [
                sys.executable,
                str(backend / "scripts" / "nullbridge_api.py"),
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=str(backend),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        run = LocalNullBridgeRun(
            base_url=f"http://127.0.0.1:{port}",
            service_secrets=secrets_map,
            temp_root=temp_root,
            process=process,
        )
        self.run = run
        try:
            self._wait_for_health(run)
        except Exception:
            run.stop()
            raise
        return run

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.run is not None:
            self.run.stop()
        if self._tmp is not None:
            self._tmp.cleanup()

    def _wait_for_health(self, run: LocalNullBridgeRun) -> None:
        deadline = time.time() + self.timeout_seconds
        last: tuple[int, dict[str, Any]] | None = None
        while time.time() < deadline:
            if run.process.poll() is not None:
                output = run.process.stdout.read() if run.process.stdout else ""
                raise RuntimeError(f"NullBridge exited early: {output[-1000:]}")
            try:
                last = live_trust_path.health(run.base_url)
                if last[0] == 200 and last[1].get("ok") is True:
                    return
            except Exception:
                pass
            time.sleep(0.2)
        raise TimeoutError(f"NullBridge health check did not pass: {last}")


def run_local_trust_path() -> dict[str, Any]:
    with LocalNullBridgeRunner() as bridge:
        allow_status, allow_body = live_trust_path.route_check(
            base_url=bridge.base_url,
            caller="android_backend",
            secret=bridge.service_secrets["android_backend"],
            target_role="primary_api",
            capability="chat.stream",
            platform="android",
        )
        deny_status, deny_body = live_trust_path.route_check(
            base_url=bridge.base_url,
            caller="android_backend",
            secret=bridge.service_secrets["android_backend"],
            target_role="codex_tools",
            capability="codex.run",
            platform="android",
        )
        ok = allow_status == 202 and allow_body.get("accepted") is True and deny_status == 403
        return {
            "ok": ok,
            "base_url": bridge.base_url,
            "allow": {"status": allow_status, "body": allow_body},
            "deny": {"status": deny_status, "body": deny_body},
            "secrets_persisted": False,
        }


def main() -> int:
    result = run_local_trust_path()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
