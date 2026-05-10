from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


TRUE_VALUES = {"1", "true", "yes", "on"}
ENV_REF_RE = re.compile(r"^\$\{ENV:([A-Za-z_][A-Za-z0-9_]*)(?::-(.*))?\}$")


@dataclass
class UniversalE2EResult:
    ok: bool
    verdict: str
    manifest: str
    suite_id: str
    lanes: list[dict[str, Any]]
    started_at: str
    finished_at: str
    duration_ms: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": "aibenchie.universal-e2e.verdict.v1",
            "ok": self.ok,
            "verdict": self.verdict,
            "manifest": self.manifest,
            "suite_id": self.suite_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_ms": self.duration_ms,
            "lanes": self.lanes,
            "summary": _summary(self.lanes),
        }


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _summary(lanes: list[dict[str, Any]]) -> dict[str, int]:
    targets = [target for lane in lanes for target in lane.get("targets", [])]
    return {
        "lanes": len(lanes),
        "targets": len(targets),
        "pass": sum(1 for target in targets if target.get("status") == "pass"),
        "fail": sum(1 for target in targets if target.get("status") == "fail"),
        "skip": sum(1 for target in targets if target.get("status") == "skip"),
    }


def _load_manifest(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() in {".yaml", ".yml"}:
        payload = yaml.safe_load(text)
    else:
        payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("Universal E2E manifest must be a JSON/YAML object.")
    return payload


def _resolve_value(value: Any, env: dict[str, str]) -> Any:
    if isinstance(value, str):
        match = ENV_REF_RE.match(value.strip())
        if match:
            env_name = match.group(1)
            fallback = match.group(2) or ""
            return env.get(env_name, fallback)
        return value
    if isinstance(value, list):
        return [_resolve_value(item, env) for item in value]
    if isinstance(value, dict):
        return {key: _resolve_value(item, env) for key, item in value.items()}
    return value


def _join_url(base_url: str, request_path: str) -> str:
    return f"{base_url.rstrip('/')}/{request_path.lstrip('/')}"


def _http_json(base_url: str, request_path: str, timeout_seconds: float) -> tuple[int, Any, str]:
    url = _join_url(base_url, request_path)
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            text = response.read().decode("utf-8-sig", errors="replace")
            payload = json.loads(text) if text else None
            return response.status, payload, ""
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8-sig", errors="replace")
        return exc.code, None, text[:500]
    except Exception as exc:  # pragma: no cover - exact socket errors vary by platform
        return 0, None, str(exc)


def _check_expected_json(payload: Any, expected: dict[str, Any]) -> tuple[bool, str]:
    if not expected:
        return True, ""
    if not isinstance(payload, dict):
        return False, "response_not_json_object"
    for key, expected_value in expected.items():
        actual = payload.get(key)
        if actual != expected_value:
            return False, f"json_mismatch:{key}"
    return True, ""


def _run_http_target(target: dict[str, Any]) -> dict[str, Any]:
    base_url = str(target.get("base_url") or "").strip()
    required = bool(target.get("required", True))
    timeout_seconds = float(target.get("timeout_seconds") or 10)
    checks = target.get("checks") if isinstance(target.get("checks"), list) else []
    if not base_url:
        return _target_result(target, "fail" if required else "skip", "missing_base_url", [])

    evidence: list[dict[str, Any]] = []
    ok = True
    failure = ""
    for check in checks:
        if not isinstance(check, dict):
            continue
        request_path = str(check.get("path") or "/").strip()
        expected_status = int(check.get("expect_status") or 200)
        status, payload, error = _http_json(base_url, request_path, timeout_seconds)
        expected_ok, expected_failure = _check_expected_json(
            payload,
            check.get("expect_json") if isinstance(check.get("expect_json"), dict) else {},
        )
        check_ok = status == expected_status and expected_ok
        evidence.append(
            {
                "kind": "http",
                "path": request_path,
                "status": status,
                "ok": check_ok,
                "failure": "" if check_ok else error or expected_failure or f"status_{status}",
            }
        )
        if not check_ok and ok:
            ok = False
            failure = evidence[-1]["failure"]

    return _target_result(target, "pass" if ok else "fail", failure, evidence)


def _run_command_target(target: dict[str, Any], manifest_dir: Path, env: dict[str, str]) -> dict[str, Any]:
    command = target.get("command")
    if not isinstance(command, list) or not command:
        return _target_result(target, "fail", "missing_command", [])
    cwd = Path(str(target.get("cwd") or "."))
    if not cwd.is_absolute():
        cwd = (manifest_dir / cwd).resolve()
    timeout_seconds = int(target.get("timeout_seconds") or 180)
    command_parts = [str(part) for part in command]
    if command_parts:
        command_parts[0] = _resolve_command_executable(command_parts[0])
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command_parts,
            cwd=cwd,
            env={**os.environ, **env},
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError as exc:
        return _target_result(
            target,
            "fail",
            "command_not_found",
            [{"kind": "command", "command": command_parts, "error": str(exc)}],
        )
    except subprocess.TimeoutExpired as exc:
        return _target_result(
            target,
            "fail",
            "timeout",
            [{"kind": "command", "duration_ms": int((time.monotonic() - started) * 1000), "stdout_tail": str(exc.stdout or "")[-1000:], "stderr_tail": str(exc.stderr or "")[-1000:]}],
        )
    evidence = [
        {
            "kind": "command",
            "returncode": completed.returncode,
            "duration_ms": int((time.monotonic() - started) * 1000),
            "stdout_tail": completed.stdout[-1000:],
            "stderr_tail": completed.stderr[-1000:],
        }
    ]
    return _target_result(target, "pass" if completed.returncode == 0 else "fail", "" if completed.returncode == 0 else f"exit_{completed.returncode}", evidence)


def _resolve_command_executable(executable: str) -> str:
    if os.name != "nt" or Path(executable).suffix:
        return executable
    resolved = shutil.which(executable) or shutil.which(f"{executable}.cmd") or shutil.which(f"{executable}.exe")
    return resolved or executable


def _run_manual_target(target: dict[str, Any]) -> dict[str, Any]:
    required = bool(target.get("required", False))
    status = "fail" if required else "skip"
    return _target_result(target, status, "manual_adapter_not_configured", [])


def _target_result(target: dict[str, Any], status: str, failure: str, evidence: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": str(target.get("id") or target.get("name") or "target"),
        "name": str(target.get("name") or target.get("id") or "target"),
        "type": str(target.get("type") or ""),
        "adapter": str(target.get("adapter") or target.get("type") or ""),
        "status": status,
        "ok": status in {"pass", "skip"},
        "required": bool(target.get("required", True)),
        "failure": failure,
        "evidence": evidence,
    }


def _run_target(target: dict[str, Any], manifest_dir: Path, env: dict[str, str]) -> dict[str, Any]:
    adapter = str(target.get("adapter") or target.get("type") or "").strip().lower()
    if adapter in {"http", "api"}:
        return _run_http_target(target)
    if adapter in {"command", "shell"}:
        return _run_command_target(target, manifest_dir, env)
    if adapter in {"manual", "playwright", "adb", "desktop"}:
        return _run_manual_target(target)
    return _target_result(target, "fail", f"unknown_adapter:{adapter}", [])


def run_universal_e2e(
    manifest_path: str | Path,
    *,
    env: dict[str, str] | None = None,
    lanes: list[str] | None = None,
) -> UniversalE2EResult:
    started_at = _now()
    started = time.monotonic()
    manifest_file = Path(manifest_path).expanduser().resolve()
    manifest = _resolve_value(_load_manifest(manifest_file), dict(os.environ if env is None else env))
    selected_lanes = {lane for lane in lanes or [] if lane and lane != "all"}
    lane_payload = manifest.get("lanes") if isinstance(manifest.get("lanes"), dict) else {}
    results: list[dict[str, Any]] = []

    for lane_id, lane_config in lane_payload.items():
        if selected_lanes and lane_id not in selected_lanes:
            continue
        if not isinstance(lane_config, dict):
            continue
        targets = lane_config.get("targets") if isinstance(lane_config.get("targets"), list) else []
        target_results = [
            _run_target(target, manifest_file.parent, dict(os.environ if env is None else env))
            for target in targets
            if isinstance(target, dict)
        ]
        results.append(
            {
                "id": str(lane_id),
                "name": str(lane_config.get("name") or lane_id),
                "type": str(lane_config.get("type") or lane_id),
                "targets": target_results,
                "ok": all(target.get("ok") for target in target_results),
            }
        )

    ok = all(lane.get("ok") for lane in results)
    return UniversalE2EResult(
        ok=ok,
        verdict="pass" if ok else "fail",
        manifest=str(manifest_file),
        suite_id=str(manifest.get("id") or manifest.get("name") or manifest_file.stem),
        lanes=results,
        started_at=started_at,
        finished_at=_now(),
        duration_ms=int((time.monotonic() - started) * 1000),
    )
