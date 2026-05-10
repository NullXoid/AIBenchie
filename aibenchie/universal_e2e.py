from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from dataclasses import dataclass
from pathlib import Path
from threading import Thread
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


def _load_playwright():
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except Exception:
        return None
    return sync_playwright


def _artifact_dir(target: dict[str, Any], manifest_dir: Path) -> Path:
    configured = str(target.get("evidence_dir") or "").strip()
    if configured:
        path = Path(configured)
        if not path.is_absolute():
            path = manifest_dir / path
    else:
        path = manifest_dir / ".." / "_validation" / "universal-e2e" / str(target.get("id") or "web-browser")
    path = path.resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


class _QuietStaticHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):  # noqa: D401 - stdlib hook
        return

    def send_head(self):  # noqa: D401 - stdlib hook
        requested_path = Path(self.translate_path(urllib.parse.urlsplit(self.path).path))
        index_path = Path(self.directory) / "index.html"
        if not requested_path.exists() and index_path.exists():
            self.path = "/index.html"
        return super().send_head()


def _start_static_server(directory: Path) -> tuple[ThreadingHTTPServer, Thread, str]:
    handler = partial(_QuietStaticHandler, directory=str(directory))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{server.server_port}"


def _target_cwd(target: dict[str, Any], manifest_dir: Path) -> Path:
    cwd = Path(str(target.get("cwd") or "."))
    if not cwd.is_absolute():
        cwd = (manifest_dir / cwd).resolve()
    return cwd


def _run_optional_build(target: dict[str, Any], manifest_dir: Path, env: dict[str, str]) -> tuple[bool, str, dict[str, Any] | None]:
    command = target.get("build_command")
    if not command:
        return True, "", None
    if not isinstance(command, list) or not command:
        return False, "missing_build_command", {"kind": "command", "error": "missing_build_command"}
    build_target = {
        **target,
        "command": command,
        "cwd": target.get("cwd") or ".",
        "timeout_seconds": target.get("build_timeout_seconds") or target.get("timeout_seconds") or 240,
    }
    result = _run_command_target(build_target, manifest_dir, env)
    evidence = result["evidence"][0] if result.get("evidence") else {"kind": "command"}
    evidence["phase"] = "build"
    return result["status"] == "pass", result.get("failure") or "", evidence


def _check_page_expectations(page: Any, expectations: list[dict[str, Any]]) -> tuple[bool, str, list[dict[str, Any]]]:
    evidence: list[dict[str, Any]] = []
    for index, expectation in enumerate(expectations):
        if not isinstance(expectation, dict):
            continue
        text = str(expectation.get("text") or "").strip()
        selector = str(expectation.get("selector") or "").strip()
        timeout_ms = int(expectation.get("timeout_ms") or 5000)
        try:
            if text:
                page.get_by_text(text, exact=bool(expectation.get("exact", False))).first.wait_for(timeout=timeout_ms)
                evidence.append({"kind": "browser_expect", "index": index, "text": text, "ok": True})
            elif selector:
                page.locator(selector).first.wait_for(timeout=timeout_ms)
                evidence.append({"kind": "browser_expect", "index": index, "selector": selector, "ok": True})
        except Exception as exc:
            failure = f"expectation_failed:{text or selector or index}"
            evidence.append(
                {
                    "kind": "browser_expect",
                    "index": index,
                    "text": text,
                    "selector": selector,
                    "ok": False,
                    "failure": failure,
                    "error": str(exc)[-500:],
                }
            )
            return False, failure, evidence
    return True, "", evidence


def _run_web_browser_target(target: dict[str, Any], manifest_dir: Path, env: dict[str, str]) -> dict[str, Any]:
    required = bool(target.get("required", True))
    sync_playwright = _load_playwright()
    if sync_playwright is None:
        return _target_result(
            target,
            "fail" if required else "skip",
            "playwright_not_installed",
            [{"kind": "browser_dependency", "package": "playwright", "ok": False}],
        )

    cwd = _target_cwd(target, manifest_dir)
    evidence_dir = _artifact_dir(target, manifest_dir)
    evidence: list[dict[str, Any]] = []

    build_ok, build_failure, build_evidence = _run_optional_build(target, manifest_dir, env)
    if build_evidence:
        evidence.append(build_evidence)
    if not build_ok:
        return _target_result(target, "fail", build_failure or "build_failed", evidence)

    serve_dir = Path(str(target.get("serve_dir") or "dist"))
    if not serve_dir.is_absolute():
        serve_dir = (cwd / serve_dir).resolve()
    if not serve_dir.exists():
        return _target_result(target, "fail" if required else "skip", "serve_dir_missing", evidence)

    server, thread, origin = _start_static_server(serve_dir)
    path = str(target.get("path") or "/").strip() or "/"
    url = _join_url(origin, path)
    screenshot_path = evidence_dir / "screenshot.png"
    html_path = evidence_dir / "page.html"
    trace_path = evidence_dir / "trace.zip"
    expectations = target.get("expect") if isinstance(target.get("expect"), list) else []
    timeout_ms = int(target.get("timeout_seconds") or 30) * 1000

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(viewport=target.get("viewport") or {"width": 1280, "height": 720})
            if bool(target.get("trace", True)):
                context.tracing.start(screenshots=True, snapshots=True)
            page = context.new_page()
            page.goto(url, wait_until=str(target.get("wait_until") or "networkidle"), timeout=timeout_ms)
            ok, failure, expectation_evidence = _check_page_expectations(page, expectations)
            evidence.extend(expectation_evidence)
            page.screenshot(path=str(screenshot_path), full_page=True)
            html_path.write_text(page.content(), encoding="utf-8")
            if bool(target.get("trace", True)):
                context.tracing.stop(path=str(trace_path))
            browser.close()
    except Exception as exc:
        evidence.append({"kind": "browser", "url": url, "ok": False, "error": str(exc)[-1000:]})
        return _target_result(target, "fail", "browser_workflow_failed", evidence)
    finally:
        server.shutdown()
        thread.join(timeout=5)

    evidence.append(
        {
            "kind": "browser_artifact",
            "url": url,
            "screenshot": str(screenshot_path),
            "html": str(html_path),
            "trace": str(trace_path) if trace_path.exists() else "",
            "ok": True,
        }
    )
    return _target_result(target, "pass" if ok else "fail", failure, evidence)


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
    if adapter in {"web_browser", "browser", "playwright"}:
        return _run_web_browser_target(target, manifest_dir, env)
    if adapter in {"manual", "adb", "desktop"}:
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
