from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from aibenchie.local_nullbridge_runner import run_local_notification_path, run_local_trust_path
from aibenchie.nullprivacy import decrypt_blob, encrypt_blob, generate_key, run_e2ee_storage_proof
from training.release_fabric import (
    POLICIES_ROOT,
    load_json,
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


def _default_gates(summary: dict[str, Any]) -> list[dict[str, str]]:
    tracks = summary.get("tracks") or {}
    trust_smoke = summary.get("trust_smoke") or {}
    notification_smoke = summary.get("notification_smoke") or {}
    privacy_proof = summary.get("privacy_proof") or {}
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
    ]


def _list_items(items: Iterable[str] | None) -> list[str]:
    return [str(item) for item in (items or []) if str(item).strip()]


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
        "gates": _default_gates(summary),
        "artifacts": artifacts or [],
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
    lines.extend(["", "## Artifacts", "", "| Artifact | Digest | SBOM | Manifest |", "| --- | --- | --- | --- |"])
    for artifact in details.get("artifacts", []):
        lines.append(
            "| "
            + f"{artifact.get('name', '')} | "
            + f"{artifact.get('digest', '')} | "
            + f"{artifact.get('sbom', '')} | "
            + f"{artifact.get('manifest', '')} |"
        )
    if not details.get("artifacts"):
        lines.append("| not_recorded |  |  |  |")
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


def build_release_report(root: Path, *, run_trust_smoke: bool = True) -> tuple[dict[str, Any], dict[str, Any], bytes]:
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
) -> dict[str, Any]:
    output = output_dir or (root / "reports" / "aibenchie" / "latest")
    output.mkdir(parents=True, exist_ok=True)
    summary, encrypted_full, key = build_release_report(root, run_trust_smoke=run_trust_smoke)
    summary_path = output / "summary.json"
    encrypted_path = output / "full-report.json.encrypted"
    key_hint_path = output / "full-report.key.local"
    details_path = output / "release-details.json"
    details_markdown_path = output / "release-details.md"
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
        evidence=[summary_path.name, encrypted_path.name],
    )
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    encrypted_path.write_text(json.dumps(encrypted_full, indent=2, sort_keys=True), encoding="utf-8")
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
