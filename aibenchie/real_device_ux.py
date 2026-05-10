from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


REAL_DEVICE_UX_SCHEMA = "aibenchie.real-device-ux-proof.v1"
DEFAULT_PROOF_PATH = Path("configs/aibenchie_real_device_ux.example.json")
ALLOWED_PLATFORMS = {"android", "ios", "desktop", "web"}
SECRET_KEY_PARTS = ("token", "secret", "password", "credential", "private_key", "apikey", "api_key", "session")
SECRET_VALUE_PREFIXES = ("ghp_", "github_pat_", "gitea_", "forgejo_", "glpat-", "xoxb-", "sk-", "eyj")
REQUIRED_ANDROID_WORKFLOWS = {"signin", "chat"}


@dataclass(frozen=True)
class RealDeviceUXCheck:
    name: str
    ok: bool
    failure: str = ""
    detail: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "ok": self.ok,
            "failure": self.failure,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class RealDeviceUXResult:
    ok: bool
    proof_path: str
    platform: str
    proof_id: str
    workflows: list[str]
    checks: list[RealDeviceUXCheck]

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "proof_path": self.proof_path,
            "platform": self.platform,
            "proof_id": self.proof_id,
            "workflows": self.workflows,
            "checks": [check.as_dict() for check in self.checks],
        }


def _check(name: str, ok: bool, failure: str = "", **detail: Any) -> RealDeviceUXCheck:
    return RealDeviceUXCheck(name=name, ok=ok, failure="" if ok else failure, detail=detail)


def _load_json(path: Path) -> tuple[dict[str, Any], str]:
    if not path.exists():
        return {}, "proof_missing"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {}, f"proof_invalid_json:{exc.lineno}"
    if not isinstance(payload, dict):
        return {}, "proof_not_object"
    return payload, ""


def _scan_secret_like_values(value: Any, path: str = "") -> list[str]:
    failures: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}" if path else key_text
            key_lower = key_text.lower()
            if any(part in key_lower for part in SECRET_KEY_PARTS):
                failures.append(f"{child_path}:secret_key_not_allowed")
                continue
            failures.extend(_scan_secret_like_values(child, child_path))
        return failures
    if isinstance(value, list):
        for index, child in enumerate(value):
            failures.extend(_scan_secret_like_values(child, f"{path}[{index}]"))
        return failures
    if isinstance(value, str):
        stripped = value.strip()
        lower = stripped.lower()
        if any(lower.startswith(prefix) for prefix in SECRET_VALUE_PREFIXES):
            failures.append(f"{path}:secret_value_not_allowed")
    return failures


def _looks_like_hash(value: Any, *, min_len: int = 16) -> bool:
    text = str(value or "").strip()
    return len(text) >= min_len and bool(re.fullmatch(r"[A-Fa-f0-9:_-]+", text))


def _workflow_ids(payload: dict[str, Any]) -> list[str]:
    workflows = payload.get("workflows") if isinstance(payload.get("workflows"), list) else []
    ids = []
    for workflow in workflows:
        if isinstance(workflow, dict):
            workflow_id = str(workflow.get("id") or workflow.get("name") or "").strip()
            if workflow_id:
                ids.append(workflow_id)
    return ids


def validate_real_device_ux_proof(proof_path: str | Path | None = None) -> RealDeviceUXResult:
    selected = Path(proof_path) if proof_path else DEFAULT_PROOF_PATH
    resolved = selected.expanduser().resolve()
    payload, load_failure = _load_json(resolved)
    checks: list[RealDeviceUXCheck] = []

    checks.append(_check("proof_json", not load_failure, load_failure))
    checks.append(_check("schema", payload.get("schema") == REAL_DEVICE_UX_SCHEMA, "schema_mismatch"))

    secret_failures = _scan_secret_like_values(payload)
    checks.append(_check("secret_boundary", not secret_failures, ";".join(secret_failures), scanned=True))

    template = bool(payload.get("template", False))
    checks.append(_check("not_template", not template, "template_proof_not_release_evidence", template=template))

    platform = str(payload.get("platform") or "").strip().lower()
    checks.append(_check("platform", platform in ALLOWED_PLATFORMS, f"unsupported_platform:{platform or 'missing'}", platform=platform))

    proof_id = str(payload.get("proof_id") or "").strip()
    checks.append(_check("proof_id", bool(proof_id), "proof_id_missing"))

    device = payload.get("device") if isinstance(payload.get("device"), dict) else {}
    device_hash = device.get("device_id_hash")
    checks.append(_check("device_id_hash", _looks_like_hash(device_hash), "device_id_hash_missing_or_invalid"))
    raw_device_fields = [key for key in ("device_id", "serial", "imei", "phone_number") if key in device]
    checks.append(_check("raw_device_identifiers_absent", not raw_device_fields, ";".join(raw_device_fields), fields=raw_device_fields))

    app = payload.get("app") if isinstance(payload.get("app"), dict) else {}
    package_name = str(app.get("package") or app.get("bundle_id") or "").strip()
    version = str(app.get("version") or app.get("build") or "").strip()
    checks.append(_check("app_identity", bool(package_name and version), "app_identity_missing", package=package_name, version=version))

    environment = payload.get("environment") if isinstance(payload.get("environment"), dict) else {}
    base_url = str(environment.get("base_url") or "").strip()
    checks.append(_check("environment", base_url.startswith("https://") or base_url.startswith("http://127.0.0.1"), "environment_base_url_invalid", base_url=base_url))

    workflows = payload.get("workflows") if isinstance(payload.get("workflows"), list) else []
    workflow_ids = _workflow_ids(payload)
    workflow_failures: list[str] = []
    for index, workflow in enumerate(workflows):
        if not isinstance(workflow, dict):
            workflow_failures.append(f"workflow_not_object:{index}")
            continue
        workflow_id = str(workflow.get("id") or workflow.get("name") or index).strip()
        if str(workflow.get("status") or "").strip().lower() != "pass":
            workflow_failures.append(f"workflow_not_pass:{workflow_id}")
        evidence = workflow.get("evidence") if isinstance(workflow.get("evidence"), list) else []
        if not evidence:
            workflow_failures.append(f"workflow_evidence_missing:{workflow_id}")
    checks.append(_check("workflows", bool(workflows) and not workflow_failures, ";".join(workflow_failures), count=len(workflows)))

    if platform == "android":
        missing = sorted(REQUIRED_ANDROID_WORKFLOWS.difference(workflow_ids))
        checks.append(_check("android_required_workflows", not missing, ";".join(f"workflow_missing:{item}" for item in missing), required=sorted(REQUIRED_ANDROID_WORKFLOWS)))

    artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), list) else []
    artifact_failures = []
    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, dict):
            artifact_failures.append(f"artifact_not_object:{index}")
            continue
        digest = str(artifact.get("sha256") or "").strip()
        if digest and not (len(digest) == 64 and all(char in "0123456789abcdefABCDEF" for char in digest)):
            artifact_failures.append(f"artifact_sha256_invalid:{index}")
        if "path" in artifact and str(artifact.get("path") or "").startswith(("C:\\", "/Users/", "/home/")):
            artifact_failures.append(f"artifact_path_must_be_public_safe:{index}")
    checks.append(_check("artifact_references", not artifact_failures, ";".join(artifact_failures), count=len(artifacts)))

    return RealDeviceUXResult(
        ok=all(check.ok for check in checks),
        proof_path=str(resolved),
        platform=platform,
        proof_id=proof_id,
        workflows=workflow_ids,
        checks=checks,
    )
