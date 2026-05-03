from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from aibenchie.local_nullbridge_runner import find_repo_root


def _parse_last_json(stdout: str) -> dict[str, Any]:
    text = stdout.strip()
    if not text:
        return {}
    candidates = [0]
    candidates.extend(index + 1 for index, char in enumerate(text) if char == "\n")
    for start in reversed(candidates):
        fragment = text[start:].strip()
        if not fragment.startswith("{"):
            continue
        try:
            parsed = json.loads(fragment)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return {}


def _free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _m35_env_with_isolated_defaults(auth_db: Path) -> tuple[dict[str, str], dict[str, Any]]:
    env = os.environ.copy()
    backend_port = env.get("NULLBRIDGE_M35_BACKEND_PORT", "").strip()
    manager_port = env.get("NULLBRIDGE_M35_MANAGER_PORT", "").strip()
    backend_url = env.get("NULLBRIDGE_M35_BACKEND_URL", "").strip()
    auth_db_value = env.get("NULLBRIDGE_M35_AUTH_DB", "").strip()

    assigned_backend_port = backend_port or str(_free_loopback_port())
    assigned_manager_port = manager_port or str(_free_loopback_port())
    env["NULLBRIDGE_M35_BACKEND_PORT"] = assigned_backend_port
    env["NULLBRIDGE_M35_MANAGER_PORT"] = assigned_manager_port
    env["NULLBRIDGE_M35_BACKEND_URL"] = backend_url or f"http://127.0.0.1:{assigned_backend_port}"
    env["NULLBRIDGE_M35_AUTH_DB"] = auth_db_value or str(auth_db)

    return (
        env,
        {
            "backendPort": int(assigned_backend_port),
            "managerPort": int(assigned_manager_port),
            "backendUrl": env["NULLBRIDGE_M35_BACKEND_URL"],
            "authDb": "caller-configured" if auth_db_value else "isolated-temp",
            "ports": "caller-configured" if backend_port and manager_port else "isolated-loopback",
        },
    )


def run_from_env() -> dict[str, Any]:
    repo = find_repo_root()
    if repo is None:
        return {
            "ok": False,
            "failure": "NullBridge repo not found; set AIBENCHIE_NULLBRIDGE_REPO",
            "m35PlatformAdapters": {},
        }
    script = repo / "backend" / "scripts" / "nullbridge_m35_platform_adapters_e2e.py"
    if not script.is_file():
        return {
            "ok": False,
            "failure": f"M35 E2E script not found: {script}",
            "m35PlatformAdapters": {},
        }
    timeout = int(os.getenv("AIBENCHIE_NULLBRIDGE_PLATFORM_ADAPTER_TIMEOUT", "180"))
    command = [sys.executable, str(script)]
    with tempfile.TemporaryDirectory(prefix="aibenchie-m35-") as temp_dir:
        env, isolation = _m35_env_with_isolated_defaults(Path(temp_dir) / "m35-platform-adapter-auth.db")
        completed = subprocess.run(
            command,
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    parsed = _parse_last_json(completed.stdout)
    ok = completed.returncode == 0 and parsed.get("ok") is True
    result = {
        "ok": ok,
        "repo": str(repo),
        "command": command,
        "returncode": completed.returncode,
        "isolation": isolation,
        "m35PlatformAdapters": parsed.get("m35PlatformAdapters", {}),
        "capability": parsed.get("capability"),
        "action": parsed.get("action"),
        "targetRole": parsed.get("targetRole"),
        "failure": "" if ok else parsed.get("error") or completed.stderr.strip() or completed.stdout[-2000:],
    }
    return result
