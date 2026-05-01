from __future__ import annotations

import json
import os
import subprocess
import sys
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
    completed = subprocess.run(
        command,
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    parsed = _parse_last_json(completed.stdout)
    ok = completed.returncode == 0 and parsed.get("ok") is True
    result = {
        "ok": ok,
        "repo": str(repo),
        "command": command,
        "returncode": completed.returncode,
        "m35PlatformAdapters": parsed.get("m35PlatformAdapters", {}),
        "capability": parsed.get("capability"),
        "action": parsed.get("action"),
        "targetRole": parsed.get("targetRole"),
        "failure": "" if ok else parsed.get("error") or completed.stderr.strip() or completed.stdout[-2000:],
    }
    return result
