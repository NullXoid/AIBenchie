from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aibenchie.nullprivacy import run_e2ee_storage_proof


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
    return json.loads(path.read_text(encoding="utf-8"))


def _required_targets(policy: dict[str, Any], env: dict[str, str]) -> list[str]:
    configured = env.get("AIBENCHIE_E2EE_REQUIRED_TARGETS", "").strip()
    if configured:
        return [target.strip() for target in configured.split(",") if target.strip()]
    targets = policy.get("e2ee_storage_targets") or []
    return [str(target) for target in targets] or list(DEFAULT_REQUIRED_TARGETS)


def _evidence_by_target(evidence: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw_targets = evidence.get("targets") or evidence.get("storage_targets") or []
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

    tests = {str(item).strip() for item in evidence.get("tests") or [] if str(item).strip()}
    for check in REQUIRED_TARGET_CHECKS:
        if check not in tests:
            failures.append(f"{target}:test_missing:{check}")

    proof_paths = [str(item) for item in evidence.get("evidence") or [] if str(item).strip()]
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
        policy = _json_file(policy_path)
    else:
        failures.append("privacy_policy_missing")

    required = _required_targets(policy, source)
    policy_targets = {str(target) for target in policy.get("e2ee_storage_targets", [])}

    if evidence_path.exists():
        evidence = _json_file(evidence_path)
    else:
        failures.append("e2ee_evidence_manifest_missing")

    proof = run_e2ee_storage_proof().as_dict()
    if not proof.get("ok"):
        failures.append("e2ee_crypto_proof_failed")

    evidence_targets = _evidence_by_target(evidence)
    target_results = [
        _target_readiness(target, policy_targets, evidence_targets.get(target))
        for target in required
    ]
    for target_result in target_results:
        failures.extend(target_result.failures)

    ok = bool(proof.get("ok")) and not failures and all(target.ok for target in target_results)
    return E2EEReadinessResult(
        ok=ok,
        root=str(resolved_root),
        policy_path=str(policy_path),
        evidence_path=str(evidence_path),
        required_targets=required,
        proof=proof,
        targets=target_results,
        failures=sorted(set(failures)),
    )
