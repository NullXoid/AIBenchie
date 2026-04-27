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


def read_service_audit_entries(temp_backend_root: Path) -> list[dict[str, Any]]:
    audit_path = temp_backend_root / "infra" / "nullbridge" / "state" / "service-audit.jsonl"
    if not audit_path.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line in audit_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            entries.append(item)
    return entries


def audit_summary(entries: list[dict[str, Any]], secrets_map: dict[str, str]) -> dict[str, Any]:
    serialized = json.dumps(entries, sort_keys=True)
    secret_leaks = [backend_id for backend_id, value in secrets_map.items() if value and value in serialized]
    secret_leaks.extend(marker for marker in ("Bearer ", "eyJ") if marker in serialized)
    route_decisions = [
        {
            "event": item.get("event"),
            "caller": item.get("caller_backend_id") or item.get("caller"),
            "capability": item.get("capability"),
            "targetRole": item.get("targetRole"),
            "decision": item.get("decision"),
            "reason": item.get("reason"),
        }
        for item in entries
        if item.get("event") in {"nullbridge.route_decision", "nullbridge.service_claim_denied"}
    ]
    return {
        "entry_count": len(entries),
        "route_decisions": route_decisions,
        "secret_leaks": secret_leaks,
        "ok": bool(entries) and not secret_leaks,
    }


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
        checks: dict[str, bool] = {}
        allow_status, allow_body = live_trust_path.route_check(
            base_url=bridge.base_url,
            caller="android_backend",
            secret=bridge.service_secrets["android_backend"],
            target_role="primary_api",
            capability="chat.stream",
            platform="android",
            request_id="aibenchie-local-allow",
        )
        checks["signed_allow"] = allow_status == 202 and allow_body.get("accepted") is True
        deny_status, deny_body = live_trust_path.route_check(
            base_url=bridge.base_url,
            caller="android_backend",
            secret=bridge.service_secrets["android_backend"],
            target_role="codex_tools",
            capability="codex.run",
            platform="android",
            request_id="aibenchie-local-policy-deny",
        )
        checks["route_policy_deny"] = deny_status == 403 and deny_body.get("errorCode") == "bridge.route_denied"
        default_deny_status, default_deny_body = live_trust_path.route_check(
            base_url=bridge.base_url,
            caller="android_backend",
            secret=bridge.service_secrets["android_backend"],
            target_role="ghost_runtime",
            capability="admin.audit",
            platform="android",
            request_id="aibenchie-local-default-deny",
        )
        checks["deny_by_default_before_target_lookup"] = (
            default_deny_status == 403 and default_deny_body.get("errorCode") == "bridge.route_denied"
        )
        missing_user_status, missing_user_body = live_trust_path.route_check(
            base_url=bridge.base_url,
            caller="android_backend",
            secret=bridge.service_secrets["android_backend"],
            target_role="primary_api",
            capability="chat.stream",
            platform="android",
            include_acting_user=False,
            request_id="aibenchie-local-missing-user-context",
        )
        checks["user_context_required"] = (
            missing_user_status == 403 and missing_user_body.get("errorCode") == "bridge.missing_user_context"
        )
        capability_claim_status, capability_claim_body = live_trust_path.route_check(
            base_url=bridge.base_url,
            caller="android_backend",
            secret=bridge.service_secrets["android_backend"],
            target_role="primary_api",
            capability="chat.stream",
            platform="android",
            jwt_capability="models.list",
            request_id="aibenchie-local-capability-claim-deny",
        )
        checks["jwt_capability_bound"] = (
            capability_claim_status == 403
            and capability_claim_body.get("errorCode") == "service.jwt_capability_mismatch"
        )
        target_claim_status, target_claim_body = live_trust_path.route_check(
            base_url=bridge.base_url,
            caller="android_backend",
            secret=bridge.service_secrets["android_backend"],
            target_role="primary_api",
            capability="chat.stream",
            platform="android",
            jwt_target_role="artifact_store",
            request_id="aibenchie-local-target-claim-deny",
        )
        checks["jwt_target_bound"] = (
            target_claim_status == 403 and target_claim_body.get("errorCode") == "service.jwt_target_mismatch"
        )
        invalid_signature_status, invalid_signature_body = live_trust_path.route_check(
            base_url=bridge.base_url,
            caller="android_backend",
            secret=f"{bridge.service_secrets['android_backend']}-wrong",
            target_role="primary_api",
            capability="chat.stream",
            platform="android",
            request_id="aibenchie-local-invalid-signature",
        )
        checks["invalid_signature_rejected"] = (
            invalid_signature_status == 401
            and invalid_signature_body.get("errorCode") == "service.jwt_invalid_signature"
        )
        audit = audit_summary(read_service_audit_entries(bridge.temp_root), bridge.service_secrets)
        checks["audit_events_recorded"] = audit["ok"]
        ok = all(checks.values())
        return {
            "ok": ok,
            "base_url": bridge.base_url,
            "allow": {"status": allow_status, "body": allow_body},
            "deny": {"status": deny_status, "body": deny_body},
            "default_deny": {"status": default_deny_status, "body": default_deny_body},
            "missing_user_context": {"status": missing_user_status, "body": missing_user_body},
            "capability_claim_deny": {"status": capability_claim_status, "body": capability_claim_body},
            "target_claim_deny": {"status": target_claim_status, "body": target_claim_body},
            "invalid_signature": {"status": invalid_signature_status, "body": invalid_signature_body},
            "checks": checks,
            "audit": audit,
            "secrets_persisted": False,
        }


def main() -> int:
    result = run_local_trust_path()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
