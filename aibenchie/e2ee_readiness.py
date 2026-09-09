from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aibenchie.nullprivacy import run_e2ee_storage_proof
from aibenchie.e2ee_product_evidence import ProductEvidence
from aibenchie.zero_knowledge_devices import run_zero_knowledge_device_lifecycle_proof


DEFAULT_REQUIRED_TARGETS = (
    "saved_chats",
    "private_artifacts",
    "ccc_memory",
    "workspace_notes",
    "private_uploads",
    "offline_cache",
    "sync_blobs",
    "private_aibenchie_reports",
)
REQUIRED_TARGET_CHECKS = (
    "roundtrip",
    "wrong_key_rejected",
    "tamper_rejected",
    "plaintext_absent_at_rest",
    "key_not_persisted_in_repo",
)
REQUIRED_DEVICE_LIFECYCLE_CHECKS = (
    "device_enrollment",
    "recovery_secret_restores_key",
    "wrong_recovery_secret_rejected",
    "revoked_device_rejected_after_rotation",
    "backend_plaintext_key_absent",
    "audit_redacted",
    "guided_setup_ui_contract",
)
IMPLEMENTED_STATUSES = {"implemented", "proven", "complete"}
FORBIDDEN_BOUNDARIES = {"", "tls_only", "server_only", "backend_only", "not_applicable"}
SAFE_PLAINTEXT_STORAGE = {"forbidden", "none", "plaintext_absent", "encrypted_only"}
FORBIDDEN_KEY_MANAGEMENT_TERMS = {
    "repo",
    "committed",
    "localstoragekey",
    "rawlocalstorage",
    "rawbrowserstorage",
    "plaintextkey",
}


@dataclass(frozen=True)
class E2EETargetReadiness:
    target: str
    ok: bool
    status: str
    failures: list[str] = field(default_factory=list)
    detail: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "ok": self.ok,
            "status": self.status,
            "failures": self.failures,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class E2EEReadinessResult:
    ok: bool
    root: str
    policy_path: str
    evidence_path: str
    required_targets: list[str]
    proof: dict[str, Any]
    device_lifecycle: dict[str, Any]
    targets: list[E2EETargetReadiness]
    failures: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "root": self.root,
            "policy_path": self.policy_path,
            "evidence_path": self.evidence_path,
            "required_targets": self.required_targets,
            "proof": self.proof,
            "device_lifecycle": self.device_lifecycle,
            "targets": [target.as_dict() for target in self.targets],
            "failures": self.failures,
        }


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _resolve_path(root: Path, value: str, default: Path) -> Path:
    if not value.strip():
        return default
    path = Path(value).expanduser()
    return path if path.is_absolute() else (root / path).resolve()


def _json_file(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("expected_object")
    return data


def _required_targets(policy: dict[str, Any], env: dict[str, str]) -> list[str]:
    configured = env.get("AIBENCHIE_E2EE_REQUIRED_TARGETS", "").strip()
    if configured:
        return list(dict.fromkeys(target.strip() for target in configured.split(",") if target.strip())) or list(DEFAULT_REQUIRED_TARGETS)
    targets = policy.get("e2ee_storage_targets") or []
    return _strings(targets) or list(DEFAULT_REQUIRED_TARGETS)


def _strings(value: Any) -> list[str]:
    return [item.strip() for item in value if isinstance(item, str) and item.strip()] if isinstance(value, list) else []


def _evidence_by_target(evidence: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw_targets = evidence.get("targets") or evidence.get("storage_targets") or []
    if not isinstance(raw_targets, list):
        return {}
    return {
        str(item.get("target") or item.get("name") or ""): item
        for item in raw_targets
        if isinstance(item, dict) and (item.get("target") or item.get("name"))
    }


def _target_readiness(target: str, policy_targets: set[str], evidence: dict[str, Any] | None) -> E2EETargetReadiness:
    failures: list[str] = []
    detail: dict[str, Any] = {}

    if target not in policy_targets:
        failures.append(f"policy_target_missing:{target}")

    if evidence is None:
        failures.append(f"evidence_target_missing:{target}")
        return E2EETargetReadiness(target=target, ok=False, status="missing", failures=failures)

    status = str(evidence.get("status") or "").strip().lower()
    if status not in IMPLEMENTED_STATUSES:
        failures.append(f"{target}:status_not_implemented")

    boundary = str(evidence.get("encryption_boundary") or "").strip().lower()
    if boundary in FORBIDDEN_BOUNDARIES:
        failures.append(f"{target}:encryption_boundary_invalid")

    key_management = str(evidence.get("key_management") or "").strip().lower()
    normalized_key_management = (
        key_management.replace(" ", "").replace("-", "").replace("_", "").replace("/", "")
    )
    if not key_management or any(term in normalized_key_management for term in FORBIDDEN_KEY_MANAGEMENT_TERMS):
        failures.append(f"{target}:key_management_invalid")

    plaintext_storage = str(evidence.get("plaintext_storage") or "").strip().lower()
    if plaintext_storage not in SAFE_PLAINTEXT_STORAGE:
        failures.append(f"{target}:plaintext_storage_not_forbidden")

    tests = set(_strings(evidence.get("tests")))
    for check in REQUIRED_TARGET_CHECKS:
        if check not in tests:
            failures.append(f"{target}:test_missing:{check}")

    proof_paths = _strings(evidence.get("evidence"))
    if not proof_paths:
        failures.append(f"{target}:evidence_missing")

    detail.update(
        {
            "status": status,
            "encryption_boundary": boundary,
            "key_management": key_management,
            "plaintext_storage": plaintext_storage,
            "tests": sorted(tests),
            "evidence": proof_paths,
        }
    )
    return E2EETargetReadiness(
        target=target,
        ok=not failures,
        status="pass" if not failures else "fail",
        failures=failures,
        detail=detail,
    )


def _device_lifecycle_evidence(evidence: dict[str, Any]) -> dict[str, Any] | None:
    raw = evidence.get("device_lifecycle") or evidence.get("zero_knowledge_device_lifecycle")
    return raw if isinstance(raw, dict) else None


def _device_lifecycle_readiness(evidence: dict[str, Any] | None, proof: dict[str, Any]) -> tuple[bool, dict[str, Any], list[str]]:
    failures: list[str] = []
    detail: dict[str, Any] = {"proof": proof}

    if not proof.get("ok"):
        failures.append("zero_knowledge_device_lifecycle_proof_failed")

    if evidence is None:
        failures.append("device_lifecycle_evidence_missing")
        return False, detail, failures

    status = str(evidence.get("status") or "").strip().lower()
    if status not in IMPLEMENTED_STATUSES:
        failures.append("device_lifecycle:status_not_implemented")

    boundary = str(evidence.get("encryption_boundary") or "").strip().lower()
    if boundary in FORBIDDEN_BOUNDARIES:
        failures.append("device_lifecycle:encryption_boundary_invalid")

    key_management = str(evidence.get("key_management") or "").strip().lower()
    normalized_key_management = (
        key_management.replace(" ", "").replace("-", "").replace("_", "").replace("/", "")
    )
    if not key_management or any(term in normalized_key_management for term in FORBIDDEN_KEY_MANAGEMENT_TERMS):
        failures.append("device_lifecycle:key_management_invalid")

    backend_key_material = str(evidence.get("backend_key_material") or "").strip().lower()
    if backend_key_material not in {"forbidden", "absent", "encrypted_envelopes_only"}:
        failures.append("device_lifecycle:backend_key_material_not_absent")

    tests = set(_strings(evidence.get("tests")))
    for check in REQUIRED_DEVICE_LIFECYCLE_CHECKS:
        if check not in tests:
            failures.append(f"device_lifecycle:test_missing:{check}")

    proof_paths = _strings(evidence.get("evidence"))
    if not proof_paths:
        failures.append("device_lifecycle:evidence_missing")

    detail.update(
        {
            "status": status,
            "encryption_boundary": boundary,
            "key_management": key_management,
            "backend_key_material": backend_key_material,
            "tests": sorted(tests),
            "evidence": proof_paths,
        }
    )
    return not failures, detail, failures


def run_e2ee_readiness_check(
    *,
    root: Path | None = None,
    env: dict[str, str] | None = None,
) -> E2EEReadinessResult:
    source = dict(os.environ if env is None else env)
    resolved_root = (root or _repo_root()).resolve()
    policy_path = _resolve_path(
        resolved_root,
        source.get("AIBENCHIE_E2EE_POLICY", ""),
        resolved_root / ".suite" / "policies" / "privacy-levels.json",
    )
    evidence_path = _resolve_path(
        resolved_root,
        source.get("AIBENCHIE_E2EE_EVIDENCE", ""),
        resolved_root / ".suite" / "evidence" / "e2ee-readiness.json",
    )

    failures: list[str] = []
    policy: dict[str, Any] = {}
    evidence: dict[str, Any] = {}
    if policy_path.exists():
        try:
            policy = _json_file(policy_path)
        except (OSError, ValueError):
            failures.append("privacy_policy_invalid")
    else:
        failures.append("privacy_policy_missing")

    required = _required_targets(policy, source)
    policy_targets = set(_strings(policy.get("e2ee_storage_targets")))

    if evidence_path.exists():
        try:
            evidence = _json_file(evidence_path)
        except (OSError, ValueError):
            failures.append("e2ee_evidence_manifest_invalid")
    else:
        failures.append("e2ee_evidence_manifest_missing")

    proof = run_e2ee_storage_proof().as_dict()
    proof["scope"] = "local_crypto_simulation_not_product_acceptance"
    if not proof.get("ok"):
        failures.append("e2ee_crypto_proof_failed")

    device_proof = run_zero_knowledge_device_lifecycle_proof().as_dict()
    device_proof["scope"] = "local_lifecycle_simulation_not_device_enrollment"
    product_evidence = ProductEvidence(resolved_root, policy, evidence)
    device_lifecycle_ok, device_lifecycle_detail, device_lifecycle_failures = _device_lifecycle_readiness(
        _device_lifecycle_evidence(evidence),
        device_proof,
    )
    device_lifecycle_failures.extend(product_evidence.check("device_lifecycle", _device_lifecycle_evidence(evidence), REQUIRED_DEVICE_LIFECYCLE_CHECKS))
    device_lifecycle_ok = device_lifecycle_ok and not device_lifecycle_failures
    failures.extend(device_lifecycle_failures)

    evidence_targets = _evidence_by_target(evidence)
    target_results = [
        _target_readiness(target, policy_targets, evidence_targets.get(target))
        for target in required
    ]
    for target_result in target_results:
        product_failures = product_evidence.check(target_result.target, evidence_targets.get(target_result.target), REQUIRED_TARGET_CHECKS)
        if product_failures:
            target_result.failures.extend(product_failures)
        failures.extend(target_result.failures)

    target_results = [
        E2EETargetReadiness(target=item.target, ok=not item.failures, status="fail" if item.failures else item.status, failures=item.failures, detail=item.detail)
        for item in target_results
    ]

    ok = (
        bool(proof.get("ok"))
        and device_lifecycle_ok
        and not failures
        and all(target.ok for target in target_results)
    )
    return E2EEReadinessResult(
        ok=ok,
        root=str(resolved_root),
        policy_path=str(policy_path),
        evidence_path=str(evidence_path),
        required_targets=required,
        proof=proof,
        device_lifecycle={
            "ok": device_lifecycle_ok,
            **device_lifecycle_detail,
            "failures": device_lifecycle_failures,
        },
        targets=target_results,
        failures=sorted(set(failures)),
    )
