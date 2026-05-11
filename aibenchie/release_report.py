from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from aibenchie.deploy_addon import verify_deploy_plan
from aibenchie.docker_support import validate_docker_support_proof
from aibenchie.local_nullbridge_runner import run_local_notification_path, run_local_trust_path
from aibenchie.nullprivacy import decrypt_blob, encrypt_blob, generate_key, run_e2ee_storage_proof
from aibenchie.real_device_ux import validate_real_device_ux_proof
from training.release_fabric import (
    POLICIES_ROOT,
    load_json,
    sha256_file,
    validate_aibenchie_gates,
    validate_nullbridge_capabilities,
    validate_nullbridge_registry,
    validate_privacy_levels,
    validate_resource_policy,
)


REPORT_VERSION = 1
PUBLIC_TRACKS = {
    "nullbridge_enforcement",
    "privacy",
    "e2ee_storage",
    "resource_management",
    "ephemeral_secret_handling",
    "release_manifest_validation",
}
SECRET_MARKERS = [
    "authorization",
    "bearer ",
    "service_token",
    "nullbridge_service_token",
    "cookie",
    "jwt",
    "eyj",
    "private_key",
    "prompt",
]
SHA256_RE = re.compile(r"^[a-fA-F0-9]{64}$")
ARTIFACT_ATTESTATION_REQUIRED_FIELDS = [
    "digest.value",
    "sbom.path",
    "sbom.sha256",
    "signature.reference",
    "signature.algorithm",
    "signature.key_id",
    "manifest.path",
    "manifest.sha256",
]


def git_commit(root: Path) -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    except Exception:
        return "unknown"


def git_branch(root: Path) -> str:
    try:
        return subprocess.check_output(["git", "branch", "--show-current"], cwd=root, text=True).strip() or "unknown"
    except Exception:
        return "unknown"


def git_remote_label(root: Path) -> str:
    try:
        remote = subprocess.check_output(["git", "remote", "get-url", "origin"], cwd=root, text=True).strip()
    except Exception:
        return "unknown"
    return "configured" if remote else "unknown"


def safe_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).lower()


def assert_public_safe(payload: dict[str, Any]) -> None:
    text = safe_json(payload)
    leaked = [marker for marker in SECRET_MARKERS if marker in text]
    if leaked:
        raise ValueError(f"summary contains secret-like markers: {', '.join(leaked)}")


def policy_track_results() -> dict[str, str]:
    checks = {
        "privacy": validate_privacy_levels(load_json(POLICIES_ROOT / "privacy-levels.json")),
        "resource_management": validate_resource_policy(load_json(POLICIES_ROOT / "resource-policy.json")),
        "nullbridge_enforcement": validate_nullbridge_registry(load_json(POLICIES_ROOT / "nullbridge-registry.json"))
        + validate_nullbridge_capabilities(load_json(POLICIES_ROOT / "nullbridge-capabilities.json")),
        "release_manifest_validation": validate_aibenchie_gates(load_json(POLICIES_ROOT / "aibenchie-gates.json")),
    }
    return {track: ("pass" if not errors else "blocks_release") for track, errors in checks.items()}


def _release_id(summary: dict[str, Any]) -> str:
    generated_at = str(summary.get("generated_at") or datetime.now(timezone.utc).isoformat())
    stamp = generated_at.replace("-", "").replace(":", "").split(".")[0]
    stamp = stamp.replace("+0000", "Z").replace("+00", "Z")
    short_commit = str(summary.get("source_commit") or "unknown")[:12]
    return f"aibenchie-{stamp}-{short_commit}"


def _status_for(ok: Any) -> str:
    if ok == "skipped":
        return "not_run"
    return "pass" if ok else "critical_block"


def _deploy_addon_public_summary(env: dict[str, str] | None = None) -> dict[str, Any]:
    source = env or os.environ
    configured = (source.get("AIBENCHIE_DEPLOY_PLAN") or source.get("AIBENCHIE_DEPLOY_ADDON_PLAN") or "").strip()
    if not configured:
        return {
            "ok": "skipped",
            "status": "not_run",
            "dry_run": True,
            "provider": "",
            "checks_total": 0,
            "failed_checks": 0,
            "asset_count": 0,
        }
    verification = verify_deploy_plan(Path(configured)).as_dict()
    checks = verification.get("checks") if isinstance(verification.get("checks"), list) else []
    failed = [check for check in checks if isinstance(check, dict) and check.get("ok") is False]
    deploy_plan = verification.get("deploy_plan") if isinstance(verification.get("deploy_plan"), dict) else {}
    provider = deploy_plan.get("provider") if isinstance(deploy_plan.get("provider"), dict) else {}
    release = deploy_plan.get("release") if isinstance(deploy_plan.get("release"), dict) else {}
    assets = deploy_plan.get("assets") if isinstance(deploy_plan.get("assets"), list) else []
    ok = bool(verification.get("ok"))
    return {
        "ok": ok,
        "status": "pass" if ok else "fail",
        "dry_run": deploy_plan.get("dry_run") is not False,
        "provider": str(provider.get("type") or ""),
        "release_tag": str(release.get("tag") or ""),
        "checks_total": len(checks),
        "failed_checks": len(failed),
        "asset_count": len(assets),
    }


def _real_device_ux_public_summary(env: dict[str, str] | None = None) -> dict[str, Any]:
    source = env or os.environ
    configured = (source.get("AIBENCHIE_REAL_DEVICE_UX_PROOF") or source.get("AIBENCHIE_ANDROID_REAL_DEVICE_UX_PROOF") or "").strip()
    if not configured:
        return {
            "ok": "skipped",
            "status": "not_run",
            "platform": "",
            "proof_id": "",
            "workflow_count": 0,
            "checks_total": 0,
            "failed_checks": 0,
        }
    verification = validate_real_device_ux_proof(configured).as_dict()
    checks = verification.get("checks") if isinstance(verification.get("checks"), list) else []
    failed = [check for check in checks if isinstance(check, dict) and check.get("ok") is False]
    workflows = verification.get("workflows") if isinstance(verification.get("workflows"), list) else []
    app = verification.get("app") if isinstance(verification.get("app"), dict) else {}
    environment = verification.get("environment") if isinstance(verification.get("environment"), dict) else {}
    runtime = verification.get("runtime") if isinstance(verification.get("runtime"), dict) else {}
    ok = bool(verification.get("ok"))
    return {
        "ok": ok,
        "status": "pass" if ok else "fail",
        "platform": str(verification.get("platform") or ""),
        "proof_id": str(verification.get("proof_id") or ""),
        "app_package": str(app.get("package") or ""),
        "app_version": str(app.get("version") or ""),
        "app_build_type": str(app.get("build_type") or ""),
        "base_url": str(environment.get("base_url") or ""),
        "network": str(environment.get("network") or ""),
        "runtime_provider": str(runtime.get("provider") or ""),
        "runtime_model": str(runtime.get("model") or ""),
        "runtime_endpoint_label": str(runtime.get("endpoint_label") or ""),
        "workflow_count": len(workflows),
        "checks_total": len(checks),
        "failed_checks": len(failed),
    }


def _docker_support_public_summary(env: dict[str, str] | None = None) -> dict[str, Any]:
    source = env or os.environ
    configured = (source.get("AIBENCHIE_DOCKER_SUPPORT_PROOF") or source.get("AIBENCHIE_DOCKER_PROOF") or "").strip()
    if not configured:
        return {
            "ok": "skipped",
            "status": "not_run",
            "proof_status": "coming_soon",
            "checks_total": 0,
            "failed_checks": 0,
        }
    verification = validate_docker_support_proof(configured).as_dict()
    checks = verification.get("checks") if isinstance(verification.get("checks"), list) else []
    failed = [check for check in checks if isinstance(check, dict) and check.get("ok") is False]
    ok = bool(verification.get("ok"))
    return {
        "ok": ok,
        "status": "pass" if ok else "fail",
        "proof_status": str(verification.get("status") or ""),
        "checks_total": len(checks),
        "failed_checks": len(failed),
    }


def _default_gates(summary: dict[str, Any]) -> list[dict[str, str]]:
    tracks = summary.get("tracks") or {}
    trust_smoke = summary.get("trust_smoke") or {}
    notification_smoke = summary.get("notification_smoke") or {}
    privacy_proof = summary.get("privacy_proof") or {}
    deploy_addon = summary.get("deploy_addon") or {}
    real_device_ux = summary.get("real_device_ux") or {}
    docker_support = summary.get("docker_support") or {}
    return [
        {
            "name": "NullBridge trust fabric",
            "result": _status_for(trust_smoke.get("ok", "skipped")),
            "evidence": "trust_smoke",
        },
        {
            "name": "NullBridge notification trust",
            "result": _status_for(notification_smoke.get("ok", "skipped")),
            "evidence": "notification_smoke",
        },
        {
            "name": "Privacy/E2EE",
            "result": "pass" if privacy_proof.get("ok") else "critical_block",
            "evidence": "privacy_proof",
        },
        {
            "name": "Resource budget",
            "result": str(tracks.get("resource_management", "not_run")),
            "evidence": "policy:resource_management",
        },
        {
            "name": "Generated output policy",
            "result": str(tracks.get("ephemeral_secret_handling", "not_run")),
            "evidence": "policy:ephemeral_secret_handling",
        },
        {
            "name": "Release manifest validation",
            "result": str(tracks.get("release_manifest_validation", "not_run")),
            "evidence": "policy:release_manifest_validation",
        },
        {
            "name": "Deploy add-on plan",
            "result": _status_for(deploy_addon.get("ok", "skipped")),
            "evidence": "deploy_addon",
        },
        {
            "name": "Real-device UX proof",
            "result": _status_for(real_device_ux.get("ok", "skipped")),
            "evidence": "real_device_ux",
        },
        {
            "name": "Docker supported-mode proof",
            "result": _status_for(docker_support.get("ok", "skipped")),
            "evidence": "docker_support",
        },
    ]


def _list_items(items: Iterable[str] | None) -> list[str]:
    return [str(item) for item in (items or []) if str(item).strip()]


def _reference_path(value: dict[str, Any]) -> str:
    return str(value.get("path") or value.get("name") or value.get("uri") or "").strip()


def _reference_digest(value: dict[str, Any]) -> str:
    raw = str(value.get("sha256") or value.get("digest") or value.get("value") or "").strip()
    if raw.startswith("sha256:"):
        return raw.split(":", 1)[1]
    return raw


def _normalize_digest(value: Any, fallback_sha256: str = "") -> dict[str, str]:
    if isinstance(value, dict):
        algorithm = str(value.get("algorithm") or value.get("algo") or "sha256").strip()
        digest_value = str(value.get("value") or value.get("sha256") or value.get("digest") or fallback_sha256).strip()
    else:
        raw = str(value or fallback_sha256).strip()
        if raw.startswith("sha256:"):
            algorithm, digest_value = raw.split(":", 1)
        else:
            algorithm, digest_value = ("sha256" if raw else "", raw)
    return {"algorithm": algorithm, "value": digest_value}


def _normalize_evidence_reference(value: Any) -> dict[str, str]:
    if isinstance(value, dict):
        return {
            "path": _reference_path(value),
            "sha256": _reference_digest(value),
            "uri": str(value.get("uri") or "").strip(),
        }
    raw = str(value or "").strip()
    if SHA256_RE.match(raw):
        return {"path": "", "sha256": raw, "uri": ""}
    return {"path": raw, "sha256": "", "uri": raw if raw.startswith(("http://", "https://")) else ""}


def _normalize_signature(value: Any) -> dict[str, str]:
    if isinstance(value, dict):
        return {
            "path": _reference_path(value),
            "sha256": _reference_digest(value),
            "algorithm": str(value.get("algorithm") or value.get("scheme") or "").strip(),
            "key_id": str(value.get("key_id") or value.get("signed_by") or value.get("signer") or "").strip(),
            "value": str(value.get("value") or value.get("signature") or "").strip(),
        }
    raw = str(value or "").strip()
    return {
        "path": raw if raw and not raw.startswith(("ssh-", "sig_", "-----")) else "",
        "sha256": "",
        "algorithm": "",
        "key_id": "",
        "value": "" if raw and not raw.startswith(("ssh-", "sig_", "-----")) else raw,
    }


def _signature_has_reference(signature: dict[str, str]) -> bool:
    return bool(signature.get("path") or signature.get("value"))


def _attestation_missing_fields(artifact: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    digest = artifact.get("digest") or {}
    sbom = artifact.get("sbom") or {}
    signature = artifact.get("signature") or {}
    manifest = artifact.get("manifest") or {}
    if not digest.get("value"):
        missing.append("digest.value")
    if digest.get("algorithm") == "sha256" and digest.get("value") and not SHA256_RE.match(str(digest.get("value"))):
        missing.append("digest.value_sha256_hex")
    if not sbom.get("path"):
        missing.append("sbom.path")
    if not sbom.get("sha256"):
        missing.append("sbom.sha256")
    elif not SHA256_RE.match(str(sbom.get("sha256"))):
        missing.append("sbom.sha256_hex")
    if not _signature_has_reference(signature):
        missing.append("signature.reference")
    if not signature.get("algorithm"):
        missing.append("signature.algorithm")
    if not signature.get("key_id"):
        missing.append("signature.key_id")
    if not manifest.get("path"):
        missing.append("manifest.path")
    if not manifest.get("sha256"):
        missing.append("manifest.sha256")
    elif not SHA256_RE.match(str(manifest.get("sha256"))):
        missing.append("manifest.sha256_hex")
    return missing


def normalize_artifact_attestations(artifacts: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for artifact in artifacts or []:
        item = {
            "name": str(artifact.get("name") or artifact.get("path") or artifact.get("uri") or "unnamed_artifact"),
            "path": str(artifact.get("path") or "").strip(),
            "kind": str(artifact.get("kind") or artifact.get("type") or "release_artifact").strip(),
            "digest": _normalize_digest(artifact.get("digest"), str(artifact.get("sha256") or "")),
            "sbom": _normalize_evidence_reference(artifact.get("sbom")),
            "signature": _normalize_signature(artifact.get("signature")),
            "manifest": _normalize_evidence_reference(artifact.get("manifest")),
            "provenance": str(artifact.get("provenance") or "").strip(),
        }
        missing = _attestation_missing_fields(item)
        item["attestation_status"] = "fully_attestable" if not missing else "incomplete"
        item["missing_attestation_fields"] = missing
        normalized.append(item)
    return normalized


def build_release_package_attestation(artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    missing_by_artifact = {
        artifact.get("name", f"artifact_{index}"): artifact.get("missing_attestation_fields", [])
        for index, artifact in enumerate(artifacts)
        if artifact.get("missing_attestation_fields")
    }
    if not artifacts:
        status = "not_recorded"
    elif missing_by_artifact:
        status = "incomplete"
    else:
        status = "fully_attestable"
    return {
        "status": status,
        "artifact_count": len(artifacts),
        "required_fields": ARTIFACT_ATTESTATION_REQUIRED_FIELDS,
        "missing_by_artifact": missing_by_artifact,
    }


def _format_digest(digest: dict[str, str] | Any) -> str:
    if not isinstance(digest, dict):
        return str(digest or "")
    if not digest.get("value"):
        return ""
    return f"{digest.get('algorithm') or 'digest'}:{digest.get('value')}"


def _format_reference(reference: dict[str, str] | Any) -> str:
    if not isinstance(reference, dict):
        return str(reference or "")
    label = reference.get("path") or reference.get("uri") or ""
    digest = reference.get("sha256") or ""
    if label and digest:
        return f"{label} ({digest})"
    return label or digest


def _format_signature(signature: dict[str, str] | Any) -> str:
    if not isinstance(signature, dict):
        return str(signature or "")
    reference = signature.get("path") or signature.get("value") or ""
    bits = [reference]
    if signature.get("algorithm"):
        bits.append(f"algorithm={signature['algorithm']}")
    if signature.get("key_id"):
        bits.append(f"key_id={signature['key_id']}")
    if signature.get("sha256"):
        bits.append(f"sha256={signature['sha256']}")
    return "; ".join(bit for bit in bits if bit)


def default_report_artifacts(summary_path: Path, encrypted_path: Path) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for path, kind in [(summary_path, "aibenchie_summary"), (encrypted_path, "encrypted_full_report")]:
        if not path.exists():
            continue
        artifacts.append(
            {
                "name": path.name,
                "path": path.name,
                "kind": kind,
                "sha256": sha256_file(path),
            }
        )
    return artifacts


def load_artifact_attestation_manifest(path: Path) -> list[dict[str, Any]]:
    payload = load_json(path)
    if isinstance(payload, list):
        artifacts = payload
    elif isinstance(payload, dict):
        artifacts = payload.get("artifacts", [])
    else:
        artifacts = []
    if not isinstance(artifacts, list):
        raise ValueError(f"artifact attestation manifest must contain a list: {path}")
    invalid = [index for index, artifact in enumerate(artifacts) if not isinstance(artifact, dict)]
    if invalid:
        raise ValueError(f"artifact attestation entries must be objects: {path} indexes={invalid}")
    return artifacts


def build_release_details(
    root: Path,
    summary: dict[str, Any],
    *,
    release_id: str | None = None,
    release_type: str = "internal",
    scope: str = "",
    retroactive: bool = False,
    confidence: str = "high",
    operator: str = "",
    reviewer: str = "",
    summary_path: str = "",
    encrypted_full_report_path: str = "",
    signed_verdict_path: str = "",
    artifacts: list[dict[str, Any]] | None = None,
    deploy_notes: list[str] | None = None,
    known_risks: list[str] | None = None,
    evidence: list[str] | None = None,
    unknowns: list[str] | None = None,
) -> dict[str, Any]:
    normalized_artifacts = normalize_artifact_attestations(artifacts)
    details = {
        "schema_version": 1,
        "release_id": release_id or _release_id(summary),
        "release_date_utc": summary.get("generated_at", datetime.now(timezone.utc).isoformat()),
        "release_type": release_type,
        "retroactive": bool(retroactive),
        "confidence": confidence,
        "source": {
            "repo": root.name,
            "branch": git_branch(root),
            "commit": summary.get("source_commit", "unknown"),
            "remote": git_remote_label(root),
        },
        "scope": scope or "AIBenchie suite verdict and release evidence package.",
        "aibenchie_verdict": {
            "suite_verdict": summary.get("verdict", "unknown"),
            "summary_path": summary_path,
            "full_report_path": encrypted_full_report_path,
            "signed_verdict_path": signed_verdict_path,
            "required_signature_policy": "pending_until_channel_signing_configured",
            "command": "python aibenchie_local.py --release-report",
        },
        "real_device_ux": summary.get("real_device_ux", {}),
        "gates": _default_gates(summary),
        "release_package_attestation": build_release_package_attestation(normalized_artifacts),
        "artifacts": normalized_artifacts,
        "security_and_privacy": {
            "public_summary_safe": True,
            "full_report_encrypted": True,
            "service_credentials_exposed": False,
            "nullbridge_credentials_exposed": False,
            "redaction": "public release details are checked for secret-like markers",
            "auth_boundary": "credentialed proof uses controlled test identities only",
        },
        "deploy_notes": _list_items(deploy_notes),
        "known_risks": _list_items(known_risks),
        "evidence": _list_items(evidence),
        "unknowns": _list_items(unknowns),
        "operator_review": {
            "operator": operator,
            "reviewer": reviewer,
            "approved_for_release": summary.get("verdict") == "ship_candidate" and not known_risks,
        },
    }
    assert_public_safe(details)
    return details


def render_release_details_markdown(details: dict[str, Any]) -> str:
    verdict = details.get("aibenchie_verdict", {})
    real_device_ux = details.get("real_device_ux", {}) if isinstance(details.get("real_device_ux"), dict) else {}
    source = details.get("source", {})
    security = details.get("security_and_privacy", {})
    review = details.get("operator_review", {})
    lines = [
        "# Release Details",
        "",
        f"release_id: {details.get('release_id', '')}",
        f"release_date_utc: {details.get('release_date_utc', '')}",
        f"release_type: {details.get('release_type', '')}",
        f"retroactive: {str(details.get('retroactive', False)).lower()}",
        f"confidence: {details.get('confidence', '')}",
        "",
        "## Source",
        "",
        f"- repo: {source.get('repo', '')}",
        f"- branch: {source.get('branch', '')}",
        f"- commit: {source.get('commit', '')}",
        f"- remote: {source.get('remote', '')}",
        "",
        "## Scope",
        "",
        str(details.get("scope", "")),
        "",
        "## AIBenchie Verdict",
        "",
        f"- suite_verdict: {verdict.get('suite_verdict', '')}",
        f"- summary_path: {verdict.get('summary_path', '')}",
        f"- full_report_path: {verdict.get('full_report_path', '')}",
        f"- signed_verdict_path: {verdict.get('signed_verdict_path', '')}",
        f"- required_signature_policy: {verdict.get('required_signature_policy', '')}",
        f"- command: `{verdict.get('command', '')}`",
        "",
        "## Gates",
        "",
        "| Gate | Result | Evidence |",
        "| --- | --- | --- |",
    ]
    for gate in details.get("gates", []):
        lines.append(f"| {gate.get('name', '')} | {gate.get('result', '')} | {gate.get('evidence', '')} |")
    if real_device_ux:
        lines.extend(
            [
                "",
                "## Real-Device UX Evidence",
                "",
                f"- status: {real_device_ux.get('status', '')}",
                f"- platform: {real_device_ux.get('platform', '')}",
                f"- proof_id: {real_device_ux.get('proof_id', '')}",
                f"- app_package: {real_device_ux.get('app_package', '')}",
                f"- app_version: {real_device_ux.get('app_version', '')}",
                f"- app_build_type: {real_device_ux.get('app_build_type', '')}",
                f"- base_url: {real_device_ux.get('base_url', '')}",
                f"- network: {real_device_ux.get('network', '')}",
                f"- runtime_provider: {real_device_ux.get('runtime_provider', '')}",
                f"- runtime_model: {real_device_ux.get('runtime_model', '')}",
                f"- runtime_endpoint_label: {real_device_ux.get('runtime_endpoint_label', '')}",
                f"- workflow_count: {real_device_ux.get('workflow_count', 0)}",
                f"- checks: {real_device_ux.get('checks_total', 0)} total, {real_device_ux.get('failed_checks', 0)} failed",
            ]
        )
    attestation = details.get("release_package_attestation", {})
    missing_by_artifact = attestation.get("missing_by_artifact", {})
    lines.extend(
        [
            "",
            "## Release Package Attestation",
            "",
            f"- status: {attestation.get('status', '')}",
            f"- artifact_count: {attestation.get('artifact_count', 0)}",
            f"- required_fields: {', '.join(attestation.get('required_fields', []))}",
            "",
            "## Artifacts",
            "",
            "| Artifact | Digest | SBOM | Signature | Manifest | Attestation |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for artifact in details.get("artifacts", []):
        lines.append(
            "| "
            + f"{artifact.get('name', '')} | "
            + f"{_format_digest(artifact.get('digest'))} | "
            + f"{_format_reference(artifact.get('sbom'))} | "
            + f"{_format_signature(artifact.get('signature'))} | "
            + f"{_format_reference(artifact.get('manifest'))} | "
            + f"{artifact.get('attestation_status', '')} |"
        )
    if not details.get("artifacts"):
        lines.append("| not_recorded |  |  |  |  | not_recorded |")
    if missing_by_artifact:
        lines.extend(["", "Missing attestation fields:"])
        for artifact_name, missing_fields in missing_by_artifact.items():
            lines.append(f"- {artifact_name}: {', '.join(missing_fields)}")
    lines.extend(
        [
            "",
            "## Security And Privacy Notes",
            "",
            f"- public_summary_safe: {str(security.get('public_summary_safe', False)).lower()}",
            f"- full_report_encrypted: {str(security.get('full_report_encrypted', False)).lower()}",
            f"- service_credentials_exposed: {str(security.get('service_credentials_exposed', True)).lower()}",
            f"- nullbridge_credentials_exposed: {str(security.get('nullbridge_credentials_exposed', True)).lower()}",
            f"- redaction: {security.get('redaction', '')}",
            f"- auth_boundary: {security.get('auth_boundary', '')}",
            "",
            "## Deploy Notes",
            "",
        ]
    )
    lines.extend([f"- {item}" for item in details.get("deploy_notes", [])] or ["- not_recorded"])
    lines.extend(["", "## Known Risks", ""])
    lines.extend([f"- {item}" for item in details.get("known_risks", [])] or ["- none_recorded"])
    lines.extend(["", "## Evidence", ""])
    lines.extend([f"- {item}" for item in details.get("evidence", [])] or ["- generated AIBenchie summary"])
    lines.extend(["", "## Unknowns", ""])
    lines.extend([f"- {item}" for item in details.get("unknowns", [])] or ["- none_recorded"])
    lines.extend(
        [
            "",
            "## Operator Review",
            "",
            f"- operator: {review.get('operator', '')}",
            f"- reviewer: {review.get('reviewer', '')}",
            f"- approved_for_release: {str(review.get('approved_for_release', False)).lower()}",
            "",
        ]
    )
    return "\n".join(lines)


def build_release_report(
    root: Path,
    *,
    run_trust_smoke: bool = True,
    env: dict[str, str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], bytes]:
    commit = git_commit(root)
    tracks = policy_track_results()
    privacy_proof = run_e2ee_storage_proof().as_dict()
    tracks["e2ee_storage"] = "pass" if privacy_proof["ok"] else "critical_block"
    tracks["ephemeral_secret_handling"] = "pass"

    trust_smoke: dict[str, Any] = {"ok": "skipped"}
    notification_smoke: dict[str, Any] = {"ok": "skipped"}
    if run_trust_smoke:
        trust_result = run_local_trust_path()
        notification_result = run_local_notification_path()
        tracks["nullbridge_enforcement"] = (
            "pass" if trust_result.get("ok") and notification_result.get("ok") else "critical_block"
        )
        trust_smoke = {
            "ok": bool(trust_result.get("ok")),
            "allow_status": trust_result.get("allow", {}).get("status"),
            "deny_status": trust_result.get("deny", {}).get("status"),
            "secrets_persisted": bool(trust_result.get("secrets_persisted")),
        }
        notification_smoke = {
            "ok": bool(notification_result.get("ok")),
            "publish_status": notification_result.get("publish", {}).get("status"),
            "query_status": notification_result.get("query", {}).get("status"),
            "direct_denied_status": notification_result.get("direct_frontend_denied", {}).get("status"),
            "website_denied_status": notification_result.get("website_publish_denied", {}).get("status"),
            "source_identity_status": notification_result.get("source_identity_bound", {}).get("status"),
            "secrets_persisted": bool(notification_result.get("secrets_persisted")),
        }

    deploy_addon = _deploy_addon_public_summary(env)
    real_device_ux = _real_device_ux_public_summary(env)
    docker_support = _docker_support_public_summary(env)
    critical_blocks = sorted(track for track, status in tracks.items() if status == "critical_block")
    blocks_release = sorted(track for track, status in tracks.items() if status == "blocks_release")
    verdict = "ship_candidate" if not critical_blocks and not blocks_release else "critical_block"
    generated_at = datetime.now(timezone.utc).isoformat()

    summary = {
        "version": REPORT_VERSION,
        "source_commit": commit,
        "generated_at": generated_at,
        "verdict": verdict,
        "critical_blocks": critical_blocks,
        "tracks": {track: tracks.get(track, "not_run") for track in sorted(PUBLIC_TRACKS)},
        "trust_smoke": trust_smoke,
        "privacy_proof": {
            "ok": privacy_proof["ok"],
            "wrong_key_rejected": privacy_proof["wrong_key_rejected"],
            "tamper_rejected": privacy_proof["tamper_rejected"],
            "plaintext_visible_in_blob": privacy_proof["plaintext_visible_in_blob"],
        },
        "notification_smoke": notification_smoke,
        "deploy_addon": deploy_addon,
        "real_device_ux": real_device_ux,
        "docker_support": docker_support,
    }
    assert_public_safe(summary)

    full_report = {
        "summary": summary,
        "tracks": tracks,
        "privacy_proof": privacy_proof,
        "trust_smoke_full": trust_result if run_trust_smoke else {"ok": "skipped"},
        "notification_smoke_full": notification_result if run_trust_smoke else {"ok": "skipped"},
        "notes": [
            "Full report encrypted before storage.",
            "No service credentials are included in the generated report.",
        ],
    }
    key = generate_key()
    encrypted_full = encrypt_blob(key, json.dumps(full_report, sort_keys=True).encode("utf-8"), associated_data={"kind": "aibenchie_full_report"})
    return summary, encrypted_full, key


def write_release_report(
    root: Path,
    output_dir: Path | None = None,
    *,
    run_trust_smoke: bool = True,
    release_id: str | None = None,
    release_type: str = "internal",
    scope: str = "",
    retroactive: bool = False,
    confidence: str = "high",
    operator: str = "",
    reviewer: str = "",
    artifacts: list[dict[str, Any]] | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    output = output_dir or (root / "reports" / "aibenchie" / "latest")
    output.mkdir(parents=True, exist_ok=True)
    summary, encrypted_full, key = build_release_report(root, run_trust_smoke=run_trust_smoke, env=env)
    summary_path = output / "summary.json"
    encrypted_path = output / "full-report.json.encrypted"
    key_hint_path = output / "full-report.key.local"
    details_path = output / "release-details.json"
    details_markdown_path = output / "release-details.md"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    encrypted_path.write_text(json.dumps(encrypted_full, indent=2, sort_keys=True), encoding="utf-8")
    details = build_release_details(
        root,
        summary,
        release_id=release_id,
        release_type=release_type,
        scope=scope,
        retroactive=retroactive,
        confidence=confidence,
        operator=operator,
        reviewer=reviewer,
        summary_path=summary_path.name,
        encrypted_full_report_path=encrypted_path.name,
        artifacts=artifacts if artifacts is not None else default_report_artifacts(summary_path, encrypted_path),
        evidence=[summary_path.name, encrypted_path.name],
    )
    details_path.write_text(json.dumps(details, indent=2, sort_keys=True), encoding="utf-8")
    details_markdown_path.write_text(render_release_details_markdown(details), encoding="utf-8")
    key_hint_path.write_text(
        "Generated per-run report key. Keep this local or replace with a hardware/device key flow.\n"
        + key.hex()
        + "\n",
        encoding="utf-8",
    )
    return {
        "ok": summary["verdict"] == "ship_candidate",
        "summary": str(summary_path),
        "encrypted_full_report": str(encrypted_path),
        "release_details": str(details_path),
        "release_details_markdown": str(details_markdown_path),
        "local_key": str(key_hint_path),
        "verdict": summary["verdict"],
    }


def decrypt_full_report(key: bytes, encrypted_report: dict[str, Any]) -> dict[str, Any]:
    return json.loads(decrypt_blob(key, encrypted_report).decode("utf-8"))


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    result = write_release_report(root)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
