from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0"
RELEASE_VERDICT_SCHEMA = "aibenchie.release-spine-verdict.v1"
SUITE_STATUS_SCHEMA = "aibenchie.suite-status.v1"
ANDROID_RELEASE_STATUS_SCHEMA = "aibenchie.android-release-status.v1"
STORE_CAPABILITY_STAGES_SCHEMA = "aibenchie.store-capability-stages.v1"
WORKFLOW_MATRIX_SCHEMA = "aibenchie.workflow-matrix.v1"
WORKFLOW_MATRIX_VERDICT_SCHEMA = "aibenchie.workflow-matrix-verdict.v1"
WORKFLOW_MATRIX_SUMMARY_SCHEMA = "aibenchie.workflow-matrix-summary.v1"
WORKFLOW_SUMMARY_SCHEMA = "aibenchie.workflow-summary.v1"
NULLBRIDGE_PRERELEASE_VERDICT_SCHEMA = "aibenchie.nullbridge-prerelease-verdict.v1"
LV7_OPERATOR_LOOP_VERDICT_SCHEMA = "aibenchie.lv7-operator-loop-verdict.v1"
STORE_CAPABILITIES_SCHEMA = "aibenchie.store-capabilities.v1"
DEFAULT_SUITE_VERSION = "0.9.0-prerelease.1"
DEFAULT_EVIDENCE_ROOT = Path(".suite/local/aibenchie/release/evidence")
DEFAULT_WORKFLOW_MATRIX = Path("configs/echolabs_workflow_matrix.json")
DEFAULT_STORE_CAPABILITIES = Path("configs/echolabs_store_capabilities.json")
EXPECTED_MS3_PRERELEASE_WORKFLOWS = {
    "standard-prompt-image": {
        "store_profile_id": "image-standard",
        "provider_workflow": "image_default",
        "artifact_kind": "image",
    },
    "reference-image-edit": {
        "store_profile_id": "image-reference-edit",
        "provider_workflow": "image_reference_edit",
        "artifact_kind": "image",
    },
    "text-to-video": {
        "store_profile_id": "video-text-alpha",
        "provider_workflow": "video_default",
        "artifact_kind": "video",
    },
    "image-to-video": {
        "store_profile_id": "video-image-alpha",
        "provider_workflow": "ltx_fp8_i2v_test",
        "artifact_kind": "video",
    },
    "video-generated-audio": {
        "store_profile_id": "video-audio-prerelease",
        "provider_workflow": "ltx_fp8_i2v_test",
        "artifact_kind": "video",
        "audio_mode": "auto_generated",
    },
    "video-recorded-voice": {
        "store_profile_id": "video-audio-prerelease",
        "provider_workflow": "ltx_fp8_i2v_test",
        "artifact_kind": "video",
        "audio_mode": "recorded_voice",
    },
    "image-to-3d-export": {
        "store_profile_id": "model-standard",
        "provider_workflow": "3d_default",
        "artifact_kind": "model3d",
    },
}
AUDIO_WORKFLOW_IDS = {"video-generated-audio", "video-recorded-voice"}
VIDEO_WORKFLOW_IDS = {"text-to-video", "image-to-video", *AUDIO_WORKFLOW_IDS}

STATUS_VALUES = {
    "draft",
    "in-progress",
    "blocked",
    "failed",
    "stale",
    "prerelease-shell",
    "prerelease-candidate",
    "passing",
    "published",
    "manual-review",
}
VERDICT_VALUES = {"pass", "fail", "blocked", "stale", "not-run", "manual-review"}
PROMOTABLE_STATUSES = {"prerelease-candidate", "passing", "published"}
MANUAL_OVERRIDE_STATUSES = {"manual-review", "blocked", "stale", "failed"}
PUBLIC_FORBIDDEN_MARKERS = (
    "authorization",
    "bearer ",
    "localhost",
    "127.0.0.1",
    "service_token",
    "nullbridge_service_token",
    "service jwt",
    "service_jwt",
    "cookie",
    "jwt",
    "token",
    "secret",
    "private_key",
    "c:\\users\\",
    "/users/",
    "192.168.",
    "10.0.",
    "172.16.",
    "private artifact path",
    "raw credential",
)
REQUIRED_STATUS_FIELDS = (
    "schema_version",
    "build_id",
    "suite_version",
    "generated_at",
    "expires_at",
    "status",
    "aibenchie_verdict",
    "source_commits",
)
REQUIRED_WORKFLOW_PROOF_FILES = (
    "workflow-proof.json",
    "android-submit.png",
    "job-status.png",
    "gallery-result.png",
    "artifact-open.png",
    "failure-message.png",
    "aibenchie-verdict.json",
    "notes.md",
)
REQUIRED_WORKFLOW_PROOF_FLAGS = (
    "android_submit_proof",
    "job_status_proof",
    "gallery_artifact_proof",
    "artifact_open_proof",
    "artifact_save_proof",
    "failure_message_proof",
)
NULLBRIDGE_REQUIRED_PROOFS = {
    "pairing-proof.json": "pairing",
    "approval-proof.json": "approval",
    "denial-proof.json": "denial",
    "route-safety-proof.json": "route-safety",
    "lease-proof.json": "lease",
    "artifact-response-proof.json": "artifact-response",
    "signed-envelope-proof.json": "signed-envelope",
    "status-offline-proof.json": "status-offline",
    "audit-redaction-proof.json": "audit-redaction",
    "android-failure-messaging-proof.json": "android-failure-messaging",
}
NULLBRIDGE_REQUIRED_PROOF_FIELDS = (
    "schema_version",
    "build_id",
    "component",
    "proof_type",
    "status",
    "generated_at",
    "source_commit",
    "public_safe",
    "raw_evidence_local_only",
    "aibenchie_verdict",
    "blocked_reason",
)
LV7_REQUIRED_PROOFS = {
    "approval-result-history-proof.json": "approval-result-history",
    "repair-preflight-proof.json": "repair-preflight",
    "repair-approval-boundary-proof.json": "repair-approval-boundary",
    "artifact-package-proof.json": "artifact-package",
    "sanitized-status-proof.json": "sanitized-status",
    "policy-resource-memory-proof.json": "policy-resource-memory",
    "android-visible-history-proof.json": "android-visible-history",
    "gcli-proof.json": "gcli",
}
LV7_REQUIRED_PROOF_FIELDS = (
    "schema_version",
    "build_id",
    "component",
    "proof_type",
    "status",
    "generated_at",
    "source_commit",
    "public_safe",
    "raw_evidence_local_only",
    "aibenchie_verdict",
    "blocked_reason",
)
LV7_REQUIRED_HISTORY_STATES = {
    "pending",
    "approved",
    "denied",
    "expired",
    "blocked",
    "completed",
    "failed",
    "artifact_available",
    "artifact_package_ready",
}
LV7_REQUIRED_OPERATION_FIELDS = {
    "operation_id",
    "target",
    "reason",
    "risk",
    "required_approval",
    "expected_result",
    "rollback_or_undo_note",
    "resource_requirements",
    "policy_gate_result",
    "preflight_result",
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_iso(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _default_build_id(now: datetime | None = None) -> str:
    return _iso(now or _now()).replace("-", "").replace(":", "").replace("T", "-").split(".")[0].rstrip("Z")


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_canonical_json(payload), encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"__load_error__": str(exc)}
    return value if isinstance(value, dict) else {"__load_error__": "json_root_not_object"}


def _git_value(root: Path, args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "unknown"


def _git_dirty(root: Path) -> bool | str:
    try:
        output = subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True, stderr=subprocess.DEVNULL)
    except Exception:
        return "unknown"
    return bool(output.strip())


def _repo_info(label: str, root: Path) -> dict[str, Any]:
    if not root.exists():
        return {
            "name": label,
            "path_label": root.name,
            "branch": "missing",
            "commit": "missing",
            "dirty": "unknown",
            "available": False,
        }
    return {
        "name": label,
        "path_label": root.name,
        "branch": _git_value(root, ["branch", "--show-current"]),
        "commit": _git_value(root, ["rev-parse", "HEAD"]),
        "dirty": _git_dirty(root),
        "available": True,
    }


def collect_repo_commit_evidence(root: Path | None = None) -> tuple[dict[str, Any], dict[str, str]]:
    base = (root or repo_root()).resolve()
    parent = base.parent
    candidates = {
        "AIBenchie": base,
        "NullXoidAndroid": parent / "NullXoidAndroid",
        "NullBridge": parent / "NullBridge",
        "echolabs-site": parent / "echolabs-site",
        "echolabs-portal": parent / "echolabs-portal",
        "Lv7": parent / "Lv-7",
    }
    repos = [_repo_info(label, path) for label, path in candidates.items()]
    source_commits = {item["name"]: str(item["commit"]) for item in repos}
    return (
        {
            "schema": "aibenchie.repo-commits.v1",
            "schema_version": SCHEMA_VERSION,
            "generated_at": _iso(_now()),
            "repos": repos,
        },
        source_commits,
    )


def _default_status_for_verdict(verdict: str) -> str:
    if verdict == "pass":
        return "prerelease-candidate"
    if verdict == "fail":
        return "failed"
    if verdict == "blocked":
        return "blocked"
    if verdict == "stale":
        return "stale"
    if verdict == "manual-review":
        return "manual-review"
    return "draft"


def _identity_payload(
    *,
    build_id: str,
    suite_version: str,
    status: str,
    verdict: str,
    source_commits: dict[str, str],
    generated_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> dict[str, Any]:
    generated = generated_at or _now()
    expires = expires_at or generated + timedelta(days=7)
    return {
        "schema_version": SCHEMA_VERSION,
        "build_id": build_id,
        "suite_version": suite_version,
        "generated_at": _iso(generated),
        "expires_at": _iso(expires),
        "status": status,
        "aibenchie_verdict": verdict,
        "source_commits": source_commits,
    }


def validate_status_payload(payload: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    failures: list[str] = []
    for field in REQUIRED_STATUS_FIELDS:
        if field not in payload:
            failures.append(f"missing_required_field:{field}")
    status = str(payload.get("status") or "")
    verdict = str(payload.get("aibenchie_verdict") or "")
    if status and status not in STATUS_VALUES:
        failures.append(f"invalid_status:{status}")
    if verdict and verdict not in VERDICT_VALUES:
        failures.append(f"invalid_verdict:{verdict}")
    if "source_commits" in payload and not isinstance(payload.get("source_commits"), dict):
        failures.append("source_commits_not_object")
    generated = _parse_iso(payload.get("generated_at"))
    expires = _parse_iso(payload.get("expires_at"))
    if "generated_at" in payload and generated is None:
        failures.append("generated_at_invalid")
    if "expires_at" in payload and expires is None:
        failures.append("expires_at_invalid")
    current = now or _now()
    expired = bool(expires and expires <= current)
    effective_status = "stale" if expired and status not in {"failed", "blocked", "manual-review", "stale"} else status
    if expired:
        failures.append("status_stale")
    return {
        "ok": not failures,
        "effective_status": effective_status,
        "failures": failures,
        "expired": expired,
    }


def verify_release_spine(
    *,
    suite: str = "echolabs",
    evidence_root: str | Path = DEFAULT_EVIDENCE_ROOT,
    build_id: str = "",
    suite_version: str = DEFAULT_SUITE_VERSION,
    verdict: str = "not-run",
    status: str = "",
    root: Path | None = None,
) -> dict[str, Any]:
    if verdict not in VERDICT_VALUES:
        raise ValueError(f"invalid AIBenchie verdict: {verdict}")
    actual_status = status or _default_status_for_verdict(verdict)
    if actual_status not in STATUS_VALUES:
        raise ValueError(f"invalid release status: {actual_status}")
    generated = _now()
    actual_build_id = build_id or _default_build_id(generated)
    resolved_root = Path(evidence_root).expanduser()
    build_dir = resolved_root / actual_build_id
    repo_evidence, source_commits = collect_repo_commit_evidence(root)
    identity = _identity_payload(
        build_id=actual_build_id,
        suite_version=suite_version,
        status=actual_status,
        verdict=verdict,
        source_commits=source_commits,
        generated_at=generated,
    )
    validation = validate_status_payload(identity, now=generated)
    payload = {
        "schema": RELEASE_VERDICT_SCHEMA,
        **identity,
        "ok": validation["ok"],
        "suite": suite,
        "release_candidate_ok": verdict == "pass" and validation["ok"],
        "evidence_root": str(resolved_root.as_posix()),
        "build_evidence_dir": str(build_dir.as_posix()),
        "validation": validation,
        "summary": {
            "latest_build_written": True,
            "latest_verdict_written": True,
            "latest_passing_written": False,
            "repo_count": len(repo_evidence["repos"]),
        },
    }

    build_dir.mkdir(parents=True, exist_ok=True)
    _write_json(build_dir / "aibenchie-verdict.json", payload)
    _write_json(build_dir / "repo-commits.json", repo_evidence)
    notes = build_dir / "release-notes.md"
    if not notes.exists():
        notes.write_text(
            f"# EchoLabs Release Notes\n\nBuild: {actual_build_id}\n\nStatus: {actual_status}\n\nVerdict: {verdict}\n",
            encoding="utf-8",
        )
    _write_json(resolved_root / "latest-build.json", payload)
    _write_json(resolved_root / "latest-verdict.json", payload)
    return payload


def _load_build_verdict(evidence_root: str | Path, build_id: str) -> tuple[Path, dict[str, Any]]:
    root = Path(evidence_root).expanduser()
    path = root / build_id / "aibenchie-verdict.json"
    if not path.exists():
        return path, {"__load_error__": "build_verdict_missing"}
    return path, _read_json(path)


def promote_passing_candidate(
    *,
    build_id: str,
    evidence_root: str | Path = DEFAULT_EVIDENCE_ROOT,
) -> dict[str, Any]:
    path, payload = _load_build_verdict(evidence_root, build_id)
    failures: list[str] = []
    if payload.get("__load_error__"):
        failures.append(str(payload["__load_error__"]))
    validation = validate_status_payload(payload) if not failures else {"ok": False, "failures": failures, "effective_status": ""}
    if not validation["ok"]:
        failures.extend([item for item in validation.get("failures", []) if item not in failures])
    if payload.get("aibenchie_verdict") != "pass":
        failures.append(f"build_not_passing:{payload.get('aibenchie_verdict', 'unknown')}")
    if payload.get("status") not in PROMOTABLE_STATUSES:
        failures.append(f"build_status_not_promotable:{payload.get('status', 'unknown')}")

    result = {
        "schema": "aibenchie.release-spine-promotion.v1",
        "schema_version": SCHEMA_VERSION,
        "generated_at": _iso(_now()),
        "ok": not failures,
        "build_id": build_id,
        "source_verdict": str(path.as_posix()),
        "failures": failures,
    }
    if failures:
        return result

    promoted = {
        **payload,
        "status": "passing",
        "promoted_at": result["generated_at"],
        "promotion": result,
    }
    _write_json(Path(evidence_root).expanduser() / "latest-passing.json", promoted)
    result["latest_passing"] = str((Path(evidence_root).expanduser() / "latest-passing.json").as_posix())
    return result


def _load_latest_candidate(evidence_root: str | Path, *, prefer_passing: bool = True) -> dict[str, Any]:
    root = Path(evidence_root).expanduser()
    candidates = ["latest-passing.json", "latest-verdict.json"] if prefer_passing else ["latest-verdict.json", "latest-passing.json"]
    for name in candidates:
        path = root / name
        if path.exists():
            payload = _read_json(path)
            if not payload.get("__load_error__"):
                payload["_source_path"] = str(path.as_posix())
                return payload
    repo_evidence, source_commits = collect_repo_commit_evidence()
    return {
        "schema": RELEASE_VERDICT_SCHEMA,
        **_identity_payload(
            build_id="unverified",
            suite_version=DEFAULT_SUITE_VERSION,
            status="draft",
            verdict="not-run",
            source_commits=source_commits,
        ),
        "ok": False,
        "suite": "echolabs",
        "release_candidate_ok": False,
        "summary": {"repo_count": len(repo_evidence["repos"])},
    }


def _assert_public_safe(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, sort_keys=True).lower()
    normalized = text.replace("\\\\", "\\")
    leaked = [marker for marker in PUBLIC_FORBIDDEN_MARKERS if marker in text or marker in normalized]
    if leaked:
        raise ValueError(f"public output contains forbidden marker(s): {', '.join(leaked)}")


def _public_safety_failures(label: str, payload: Any) -> list[str]:
    text = json.dumps(payload, sort_keys=True).lower() if not isinstance(payload, str) else payload.lower()
    normalized = text.replace("\\\\", "\\")
    leaked = [marker for marker in PUBLIC_FORBIDDEN_MARKERS if marker in text or marker in normalized]
    return [f"{label}:public_safety_marker:{marker}" for marker in leaked]


def _load_workflow_matrix(path: str | Path) -> dict[str, Any]:
    payload = _read_json(Path(path))
    workflows = payload.get("workflows")
    if not isinstance(workflows, list):
        payload["workflows"] = []
    return payload


def _load_store_capabilities(path: str | Path) -> dict[str, Any]:
    payload = _read_json(Path(path))
    capabilities = payload.get("capabilities")
    if not isinstance(capabilities, list):
        payload["capabilities"] = []
    return payload


def _resolve_build_root(evidence_root: str | Path, build_id: str = "") -> Path:
    root = Path(evidence_root).expanduser()
    if build_id:
        return root / build_id
    latest = _load_latest_candidate(root, prefer_passing=False)
    latest_build_id = str(latest.get("build_id") or "")
    return root / latest_build_id if latest_build_id and latest_build_id != "unverified" else root


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "pass", "passed", "ok", "1"}
    return bool(value)


def _proof_verdict_value(payload: dict[str, Any]) -> str:
    value = payload.get("aibenchie_verdict") or payload.get("verdict")
    if value:
        return str(value)
    if payload.get("ok") is True:
        return "pass"
    return ""


def _device_aliases(proof: dict[str, Any]) -> list[str]:
    order = proof.get("device_proof_order")
    if isinstance(order, list):
        return [str(item) for item in order if str(item).strip()]
    devices = proof.get("devices")
    if isinstance(devices, list):
        aliases: list[str] = []
        for item in devices:
            if not isinstance(item, dict):
                continue
            alias = item.get("alias") or item.get("device_alias") or item.get("label") or item.get("model")
            if alias:
                aliases.append(str(alias))
        return aliases
    return []


def _artifact_validation_failures(workflow_id: str, proof: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    validation = proof.get("artifact_validation")
    if not isinstance(validation, dict):
        return [f"{workflow_id}:artifact_validation_missing"]
    if not (_truthy(validation.get("ok")) or str(validation.get("validationStatus") or "").lower() in {"pass", "passed"}):
        failures.append(f"{workflow_id}:artifact_validation_not_pass")
    expected_kind = str(expected.get("artifact_kind") or "")
    actual_kind = str(validation.get("artifact_kind") or proof.get("artifact_kind") or "")
    if expected_kind and actual_kind and actual_kind != expected_kind:
        failures.append(f"{workflow_id}:artifact_kind_mismatch:{actual_kind}")
    if workflow_id in VIDEO_WORKFLOW_IDS:
        if int(validation.get("videoStreamCount") or validation.get("video_stream_count") or 0) < 1:
            failures.append(f"{workflow_id}:video_stream_missing")
    if workflow_id in AUDIO_WORKFLOW_IDS:
        if not _truthy(validation.get("hasAudio") if "hasAudio" in validation else validation.get("has_audio")):
            failures.append(f"{workflow_id}:audio_flag_missing")
        if int(validation.get("audioStreamCount") or validation.get("audio_stream_count") or 0) < 1:
            failures.append(f"{workflow_id}:audio_stream_missing")
        if int(validation.get("audioDurationMs") or validation.get("audio_duration_ms") or 0) <= 0:
            failures.append(f"{workflow_id}:audio_duration_missing")
        if int(validation.get("videoDurationMs") or validation.get("video_duration_ms") or 0) <= 0:
            failures.append(f"{workflow_id}:video_duration_missing")
        if not _truthy(
            validation.get("nonSilentAudio")
            if "nonSilentAudio" in validation
            else validation.get("non_silent_audio")
            if "non_silent_audio" in validation
            else validation.get("audio_not_silent")
        ):
            failures.append(f"{workflow_id}:non_silent_audio_missing")
        if not _truthy(
            validation.get("durationCompatible")
            if "durationCompatible" in validation
            else validation.get("duration_compatible")
        ):
            failures.append(f"{workflow_id}:duration_compatibility_missing")
        if str(validation.get("validationFailureReason") or validation.get("validation_failure_reason") or "").strip():
            failures.append(f"{workflow_id}:validation_failure_reason_present")
    if workflow_id == "video-recorded-voice":
        if _truthy(validation.get("voice_truncated") or validation.get("recordedVoiceTruncated")):
            failures.append(f"{workflow_id}:recorded_voice_truncated")
    if expected_kind == "model3d":
        formats = validation.get("output_formats") or validation.get("outputFormats") or []
        if isinstance(formats, str):
            formats = [formats]
        if not any(str(item).lower() in {"glb", "gltf"} for item in formats):
            failures.append(f"{workflow_id}:model3d_export_format_missing")
    return failures


def _validate_workflow_proof(proof_dir: Path, workflow: dict[str, Any], build_id: str) -> list[str]:
    workflow_id = str(workflow.get("workflow_id") or "")
    failures: list[str] = []
    for filename in REQUIRED_WORKFLOW_PROOF_FILES:
        if not (proof_dir / filename).exists():
            failures.append(f"{workflow_id}:missing_proof_file:{filename}")
    proof_json = proof_dir / "workflow-proof.json"
    if not proof_json.exists():
        return failures
    proof = _read_json(proof_json)
    if proof.get("__load_error__"):
        failures.append(f"{workflow_id}:proof_json_invalid")
        return failures
    if proof.get("workflow_id") != workflow_id:
        failures.append(f"{workflow_id}:proof_workflow_id_mismatch")
    if build_id and proof.get("build_id") != build_id:
        failures.append(f"{workflow_id}:proof_build_id_mismatch")
    failures.extend(_public_safety_failures(f"{workflow_id}:proof", proof))
    notes_path = proof_dir / "notes.md"
    if notes_path.exists():
        failures.extend(_public_safety_failures(f"{workflow_id}:notes", notes_path.read_text(encoding="utf-8", errors="replace")))
    verdict_path = proof_dir / "aibenchie-verdict.json"
    if verdict_path.exists():
        verdict = _read_json(verdict_path)
        if verdict.get("__load_error__"):
            failures.append(f"{workflow_id}:verdict_json_invalid")
        else:
            failures.extend(_public_safety_failures(f"{workflow_id}:verdict", verdict))
            if _proof_verdict_value(verdict) != "pass":
                failures.append(f"{workflow_id}:verdict_file_not_pass")
    for field in REQUIRED_WORKFLOW_PROOF_FLAGS:
        if proof.get(field) is not True:
            failures.append(f"{workflow_id}:proof_field_not_true:{field}")
    if proof.get("aibenchie_verdict") != "pass":
        failures.append(f"{workflow_id}:proof_verdict_not_pass")
    expected = EXPECTED_MS3_PRERELEASE_WORKFLOWS.get(workflow_id, {})
    if expected:
        for field in ("store_profile_id", "provider_workflow", "audio_mode"):
            expected_value = expected.get(field)
            if expected_value and str(proof.get(field) or workflow.get(field) or "") != str(expected_value):
                failures.append(f"{workflow_id}:proof_{field}_mismatch")
        if proof.get("real_provider_proof") is not True:
            failures.append(f"{workflow_id}:real_provider_proof_missing")
        for field in ("provider_backing", "provider_kind", "provider_mode"):
            value = str(proof.get(field) or "").lower()
            if "mock" in value:
                failures.append(f"{workflow_id}:mock_provider_detected:{field}")
        if proof.get("mock_backed") is True:
            failures.append(f"{workflow_id}:mock_backed_proof")
        aliases = _device_aliases(proof)
        if str(proof.get("primary_device") or "") != "S23 FE":
            failures.append(f"{workflow_id}:primary_device_not_s23_fe")
        if str(proof.get("secondary_device") or "") != "A17":
            failures.append(f"{workflow_id}:secondary_device_not_a17")
        if aliases[:2] != ["S23 FE", "A17"]:
            failures.append(f"{workflow_id}:device_order_invalid")
        failures.extend(_artifact_validation_failures(workflow_id, proof, expected))
    expires = _parse_iso(proof.get("expires_at"))
    if expires and expires <= _now():
        failures.append(f"{workflow_id}:proof_stale")
    return failures


def validate_workflow_matrix(
    *,
    matrix: str | Path = DEFAULT_WORKFLOW_MATRIX,
    store_capabilities: str | Path = DEFAULT_STORE_CAPABILITIES,
    evidence_root: str | Path = DEFAULT_EVIDENCE_ROOT,
    build_id: str = "",
    out: str | Path = "",
    write_verdict: bool = True,
) -> dict[str, Any]:
    matrix_payload = _load_workflow_matrix(matrix)
    store_payload = _load_store_capabilities(store_capabilities)
    workflows = [item for item in matrix_payload.get("workflows", []) if isinstance(item, dict)]
    capabilities = [item for item in store_payload.get("capabilities", []) if isinstance(item, dict)]
    capabilities_by_workflow = {str(item.get("workflow_id") or ""): item for item in capabilities}
    build_root = _resolve_build_root(evidence_root, build_id)
    actual_build_id = build_id or build_root.name
    failures: list[str] = []
    frozen_prerelease = [str(item) for item in matrix_payload.get("frozen_prerelease_workflows") or []]

    if matrix_payload.get("__load_error__"):
        failures.append(f"workflow_matrix_load_error:{matrix_payload['__load_error__']}")
    if store_payload.get("__load_error__"):
        failures.append(f"store_capabilities_load_error:{store_payload['__load_error__']}")
    if matrix_payload.get("schema") not in {"", None, WORKFLOW_MATRIX_SCHEMA}:
        failures.append(f"workflow_matrix_schema_invalid:{matrix_payload.get('schema')}")
    if store_payload.get("schema") not in {"", None, STORE_CAPABILITIES_SCHEMA}:
        failures.append(f"store_capabilities_schema_invalid:{store_payload.get('schema')}")

    prerelease_count = 0
    prerelease_workflow_ids: list[str] = []
    for workflow in workflows:
        workflow_id = str(workflow.get("workflow_id") or "")
        release_stage = str(workflow.get("release_stage") or "")
        state = str(workflow.get("state") or "")
        if not workflow_id:
            failures.append("workflow_id_missing")
            continue
        if workflow_id not in capabilities_by_workflow:
            failures.append(f"{workflow_id}:missing_store_capability_mapping")
        else:
            capability = capabilities_by_workflow[workflow_id]
            if str(capability.get("proof_path") or "") != str(workflow.get("proof_path") or ""):
                failures.append(f"{workflow_id}:store_capability_proof_path_mismatch")
        if release_stage == "prerelease":
            prerelease_count += 1
            prerelease_workflow_ids.append(workflow_id)
            if state == "blocked" or workflow.get("blocked_reason"):
                failures.append(f"{workflow_id}:blocked_workflow_marked_prerelease")
            capability = capabilities_by_workflow.get(workflow_id)
            if capability and str(capability.get("release_stage") or "") != "prerelease":
                failures.append(f"{workflow_id}:store_capability_not_prerelease")
            expected = EXPECTED_MS3_PRERELEASE_WORKFLOWS.get(workflow_id)
            if expected:
                for field in ("store_profile_id", "provider_workflow", "artifact_kind", "audio_mode"):
                    expected_value = expected.get(field)
                    if expected_value and str(workflow.get(field) or "") != str(expected_value):
                        failures.append(f"{workflow_id}:matrix_{field}_mismatch")
            proof_dir = build_root / str(workflow.get("proof_path") or f"workflow-proofs/{workflow_id}")
            failures.extend(_validate_workflow_proof(proof_dir, workflow, actual_build_id))
        elif state in {"installable", "enabled"} and release_stage in {"blocked", "later"}:
            failures.append(f"{workflow_id}:blocked_or_later_workflow_installable")
        if release_stage in {"blocked", "later"} and not workflow.get("blocked_reason"):
            failures.append(f"{workflow_id}:blocked_or_later_missing_reason")

    if frozen_prerelease:
        expected_set = set(frozen_prerelease)
        actual_set = set(prerelease_workflow_ids)
        for workflow_id in sorted(expected_set - actual_set):
            failures.append(f"{workflow_id}:frozen_prerelease_missing")
        for workflow_id in sorted(actual_set - expected_set):
            failures.append(f"{workflow_id}:unexpected_prerelease_workflow")
        if expected_set != set(EXPECTED_MS3_PRERELEASE_WORKFLOWS):
            failures.append("frozen_prerelease_contract_drift")

    result = {
        "schema": WORKFLOW_MATRIX_VERDICT_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "generated_at": _iso(_now()),
        "ok": not failures,
        "aibenchie_verdict": "pass" if not failures else "blocked",
        "matrix": str(Path(matrix).as_posix()),
        "store_capabilities": str(Path(store_capabilities).as_posix()),
        "evidence_root": str(Path(evidence_root).as_posix()),
        "build_id": actual_build_id,
        "workflow_count": len(workflows),
        "prerelease_count": prerelease_count,
        "frozen_prerelease_workflows": frozen_prerelease,
        "validated_prerelease_workflows": prerelease_workflow_ids,
        "capability_count": len(capabilities),
        "failures": failures,
    }
    if write_verdict:
        output_path = Path(out).expanduser() if out else build_root / "workflow-matrix-verdict.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        _write_json(output_path, result)
        result["output"] = str(output_path.as_posix())
    return result


def export_website_status(
    *,
    out: str | Path,
    evidence_root: str | Path = DEFAULT_EVIDENCE_ROOT,
) -> dict[str, Any]:
    candidate = _load_latest_candidate(evidence_root, prefer_passing=True)
    validation = validate_status_payload(candidate)
    payload = {
        "schema": SUITE_STATUS_SCHEMA,
        "public_safe": True,
        **_identity_payload(
            build_id=str(candidate.get("build_id") or "unverified"),
            suite_version=str(candidate.get("suite_version") or DEFAULT_SUITE_VERSION),
            status=str(validation.get("effective_status") or candidate.get("status") or "draft"),
            verdict=str(candidate.get("aibenchie_verdict") or "not-run"),
            source_commits={key: str(value) for key, value in (candidate.get("source_commits") or {}).items()},
        ),
        "latest_source": Path(str(candidate.get("_source_path") or "")).name,
        "latest_passing_build_id": str(candidate.get("build_id") or "") if candidate.get("aibenchie_verdict") == "pass" else "",
        "summary": {
            "release_candidate_ok": bool(candidate.get("release_candidate_ok")),
            "status_effective": validation.get("effective_status"),
            "validation_failures": validation.get("failures", []),
        },
    }
    _assert_public_safe(payload)
    _write_json(Path(out), payload)
    payload["output"] = str(Path(out).as_posix())
    return payload


def export_android_release_status(
    *,
    out: str | Path,
    evidence_root: str | Path = DEFAULT_EVIDENCE_ROOT,
) -> dict[str, Any]:
    candidate = _load_latest_candidate(evidence_root, prefer_passing=True)
    validation = validate_status_payload(candidate)
    payload = {
        "schema": ANDROID_RELEASE_STATUS_SCHEMA,
        **_identity_payload(
            build_id=str(candidate.get("build_id") or "unverified"),
            suite_version=str(candidate.get("suite_version") or DEFAULT_SUITE_VERSION),
            status=str(validation.get("effective_status") or candidate.get("status") or "draft"),
            verdict=str(candidate.get("aibenchie_verdict") or "not-run"),
            source_commits={key: str(value) for key, value in (candidate.get("source_commits") or {}).items()},
        ),
        "app_version": str(candidate.get("suite_version") or DEFAULT_SUITE_VERSION),
        "apk_version_code": None,
        "apk_sha256": "",
        "signing_status": "missing",
        "signing_key_continuity": "not-run",
        "verdict_path": str(candidate.get("_source_path") or ""),
        "update_notes_path": "",
        "primary_device": "",
        "secondary_device": "",
        "android_proof_path": "",
        "proof_missing": True,
        "summary": {
            "does_not_fake_missing_proof": True,
            "release_candidate_ok": bool(candidate.get("release_candidate_ok")),
        },
    }
    _write_json(Path(out), payload)
    payload["output"] = str(Path(out).as_posix())
    return payload


def export_store_capabilities(
    *,
    out: str | Path,
    store_capabilities: str | Path = DEFAULT_STORE_CAPABILITIES,
    evidence_root: str | Path = DEFAULT_EVIDENCE_ROOT,
) -> dict[str, Any]:
    candidate = _load_latest_candidate(evidence_root, prefer_passing=True)
    candidate_passed = candidate.get("aibenchie_verdict") == "pass" and validate_status_payload(candidate)["ok"]
    source = _load_store_capabilities(store_capabilities)
    exported: list[dict[str, Any]] = []
    for item in source.get("capabilities", []):
        if not isinstance(item, dict):
            continue
        capability = dict(item)
        if capability.get("release_stage") == "prerelease" and not candidate_passed:
            capability["state"] = "blocked"
            capability["effective_release_stage"] = "blocked"
            capability["blocked_reason"] = capability.get("blocked_reason") or "missing_passing_release_candidate"
        else:
            capability["effective_release_stage"] = capability.get("release_stage")
        exported.append(capability)
    payload = {
        "schema": STORE_CAPABILITY_STAGES_SCHEMA,
        **_identity_payload(
            build_id=str(candidate.get("build_id") or "unverified"),
            suite_version=str(candidate.get("suite_version") or DEFAULT_SUITE_VERSION),
            status=str(candidate.get("status") or "draft"),
            verdict=str(candidate.get("aibenchie_verdict") or "not-run"),
            source_commits={key: str(value) for key, value in (candidate.get("source_commits") or {}).items()},
        ),
        "capabilities": exported,
    }
    _write_json(Path(out), payload)
    payload["output"] = str(Path(out).as_posix())
    return payload


def _assert_public_safe_value(label: str, payload: Any) -> None:
    failures = _public_safety_failures(label, payload)
    if failures:
        raise ValueError(f"public output contains forbidden marker(s): {', '.join(failures)}")


def _artifact_validation_status(validation: dict[str, Any]) -> str:
    status = str(validation.get("validationStatus") or validation.get("validation_status") or "").strip().lower()
    if status in {"pass", "passed"} or validation.get("ok") is True:
        return "pass"
    if status:
        return status
    return "unknown"


def _bool_field(payload: dict[str, Any], *names: str) -> bool:
    for name in names:
        if name in payload:
            return _truthy(payload.get(name))
    return False


def _int_field(payload: dict[str, Any], *names: str) -> int | None:
    for name in names:
        value = payload.get(name)
        if value in ("", None):
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    return None


def _audio_summary(workflow_id: str, validation: dict[str, Any]) -> dict[str, Any] | None:
    if workflow_id not in AUDIO_WORKFLOW_IDS:
        return None
    audio_stream_count = _int_field(validation, "audioStreamCount", "audio_stream_count") or 0
    return {
        "audio_stream_present": audio_stream_count >= 1,
        "non_silent_audio": _bool_field(validation, "nonSilentAudio", "non_silent_audio", "audio_not_silent"),
        "duration_compatible": _bool_field(validation, "durationCompatible", "duration_compatible"),
        "audio_duration_ms": _int_field(validation, "audioDurationMs", "audio_duration_ms"),
        "video_duration_ms": _int_field(validation, "videoDurationMs", "video_duration_ms"),
    }


def _safe_device_aliases(proof: dict[str, Any]) -> list[str]:
    aliases = _device_aliases(proof)
    return [alias for alias in aliases if alias in {"S23 FE", "A17"}]


def _workflow_summary(
    *,
    workflow: dict[str, Any],
    proof: dict[str, Any],
    capability: dict[str, Any] | None,
    build_id: str,
    source_verdict_ref: str,
) -> dict[str, Any]:
    workflow_id = str(workflow.get("workflow_id") or proof.get("workflow_id") or "")
    validation = proof.get("artifact_validation") if isinstance(proof.get("artifact_validation"), dict) else {}
    aliases = _safe_device_aliases(proof)
    audio = _audio_summary(workflow_id, validation)
    summary = {
        "schema": WORKFLOW_SUMMARY_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "build_id": build_id,
        "source_evidence_build_id": build_id,
        "source_aibenchie_verdict_ref": source_verdict_ref,
        "generated_at": _iso(_now()),
        "workflow_id": workflow_id,
        "display_name": str(workflow.get("display_name") or workflow_id),
        "release_stage": str(workflow.get("release_stage") or proof.get("release_stage") or ""),
        "verdict": _proof_verdict_value(proof) or str(proof.get("aibenchie_verdict") or "not-run"),
        "proof_device_aliases": aliases,
        "device_order_pass": aliases[:2] == ["S23 FE", "A17"],
        "provider_backing": "real"
        if proof.get("real_provider_proof") is True and proof.get("mock_backed") is not True
        else "not-public-prerelease-proof",
        "artifact_kind": str(workflow.get("artifact_kind") or proof.get("artifact_kind") or ""),
        "artifact_validation_status": _artifact_validation_status(validation),
        "failure_message_proof_present": proof.get("failure_message_proof") is True,
        "store_mapping_present": capability is not None,
        "store_stage": str((capability or {}).get("release_stage") or workflow.get("release_stage") or ""),
    }
    if audio is not None:
        summary["audio_validation"] = audio
    _assert_public_safe_value(workflow_id, summary)
    return summary


def _blocked_workflow_summary(workflows: list[dict[str, Any]], capabilities_by_workflow: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    blocked: list[dict[str, Any]] = []
    for workflow in workflows:
        workflow_id = str(workflow.get("workflow_id") or "")
        release_stage = str(workflow.get("release_stage") or "")
        if release_stage == "prerelease":
            continue
        capability = capabilities_by_workflow.get(workflow_id) or {}
        item = {
            "workflow_id": workflow_id,
            "display_name": str(workflow.get("display_name") or workflow_id),
            "release_stage": release_stage,
            "state": str(workflow.get("state") or capability.get("state") or ""),
            "store_stage": str(capability.get("release_stage") or release_stage),
            "blocked_reason": str(workflow.get("blocked_reason") or capability.get("blocked_reason") or ""),
        }
        _assert_public_safe_value(f"{workflow_id}:blocked_summary", item)
        blocked.append(item)
    return blocked


def _workflow_summary_markdown(summary: dict[str, Any]) -> str:
    lines = [
        f"# EchoLabs MS3 Workflow Evidence Summary",
        "",
        f"Build: `{summary['build_id']}`",
        f"Verdict: `{summary['verdict']}`",
        f"Generated: `{summary['generated_at']}`",
        "",
        "Raw screenshots, videos, logs, device serials, local paths, private endpoints, and prompts are not exported.",
        "",
        "## Prerelease Workflows",
        "",
        "| Workflow | Verdict | Devices | Provider | Artifact | Validation | Failure proof | Store mapping |",
        "|---|---:|---|---|---|---|---:|---:|",
    ]
    for item in summary["workflows"]:
        audio = item.get("audio_validation") if isinstance(item.get("audio_validation"), dict) else None
        validation = item["artifact_validation_status"]
        if audio:
            validation = (
                f"{validation}; audio={str(audio['audio_stream_present']).lower()}, "
                f"non-silent={str(audio['non_silent_audio']).lower()}, "
                f"duration={str(audio['duration_compatible']).lower()}"
            )
        lines.append(
            "| "
            + " | ".join(
                [
                    item["display_name"],
                    item["verdict"],
                    ", ".join(item["proof_device_aliases"]),
                    item["provider_backing"],
                    item["artifact_kind"],
                    validation,
                    "yes" if item["failure_message_proof_present"] else "no",
                    "yes" if item["store_mapping_present"] else "no",
                ]
            )
            + " |"
        )
    lines.extend(["", "## Blocked Or Later Workflows", ""])
    for item in summary["blocked_later_workflows"]:
        lines.append(f"- `{item['workflow_id']}`: {item['release_stage']} - {item['blocked_reason']}")
    lines.append("")
    return "\n".join(lines)


def export_workflow_summary(
    *,
    build_id: str,
    out: str | Path,
    evidence_root: str | Path = DEFAULT_EVIDENCE_ROOT,
    matrix: str | Path = DEFAULT_WORKFLOW_MATRIX,
    store_capabilities: str | Path = DEFAULT_STORE_CAPABILITIES,
) -> dict[str, Any]:
    validation = validate_workflow_matrix(
        matrix=matrix,
        store_capabilities=store_capabilities,
        evidence_root=evidence_root,
        build_id=build_id,
        write_verdict=False,
    )
    if not validation["ok"]:
        return {
            "schema": WORKFLOW_MATRIX_SUMMARY_SCHEMA,
            "schema_version": SCHEMA_VERSION,
            "ok": False,
            "build_id": build_id,
            "generated_at": _iso(_now()),
            "failures": validation.get("failures", []),
            "outputs": {},
        }

    matrix_payload = _load_workflow_matrix(matrix)
    store_payload = _load_store_capabilities(store_capabilities)
    workflows = [item for item in matrix_payload.get("workflows", []) if isinstance(item, dict)]
    capabilities = [item for item in store_payload.get("capabilities", []) if isinstance(item, dict)]
    capabilities_by_workflow = {str(item.get("workflow_id") or ""): item for item in capabilities}
    prerelease_workflows = [item for item in workflows if str(item.get("release_stage") or "") == "prerelease"]
    build_root = _resolve_build_root(evidence_root, build_id)
    output_root = Path(out)
    workflows_out = output_root / "workflows"
    source_verdict_ref = f"aibenchie-release-evidence/{build_id}/workflow-matrix-verdict.json"

    workflow_summaries: list[dict[str, Any]] = []
    for workflow in prerelease_workflows:
        workflow_id = str(workflow.get("workflow_id") or "")
        proof_path = build_root / str(workflow.get("proof_path") or f"workflow-proofs/{workflow_id}") / "workflow-proof.json"
        proof = _read_json(proof_path)
        workflow_summaries.append(
            _workflow_summary(
                workflow=workflow,
                proof=proof,
                capability=capabilities_by_workflow.get(workflow_id),
                build_id=build_id,
                source_verdict_ref=source_verdict_ref,
            )
        )

    device_order_pass = all(item["device_order_pass"] for item in workflow_summaries)
    summary = {
        "schema": WORKFLOW_MATRIX_SUMMARY_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "public_safe": True,
        "ok": True,
        "build_id": build_id,
        "source_evidence_build_id": build_id,
        "source_aibenchie_verdict_ref": source_verdict_ref,
        "generated_at": _iso(_now()),
        "verdict": "pass",
        "workflow_count": len(workflow_summaries),
        "passed": sum(1 for item in workflow_summaries if item["verdict"] == "pass"),
        "device_order": ["S23 FE", "A17"],
        "device_order_pass": device_order_pass,
        "provider_backing": "real",
        "raw_evidence_exported": False,
        "media_files_exported": False,
        "workflows": workflow_summaries,
        "blocked_later_workflows": _blocked_workflow_summary(workflows, capabilities_by_workflow),
        "outputs": {
            "summary_json": "workflow-matrix-summary.json",
            "summary_markdown": "workflow-matrix-summary.md",
            "index_json": "index.json",
            "workflow_json_dir": "workflows/",
        },
    }
    _assert_public_safe_value("workflow_matrix_summary", summary)
    markdown = _workflow_summary_markdown(summary)
    _assert_public_safe_value("workflow_matrix_summary_markdown", markdown)

    workflows_out.mkdir(parents=True, exist_ok=True)
    for item in workflow_summaries:
        _write_json(workflows_out / f"{item['workflow_id']}.json", item)
    _write_json(output_root / "workflow-matrix-summary.json", summary)
    (output_root / "workflow-matrix-summary.md").write_text(markdown, encoding="utf-8")
    index = {
        "schema": "aibenchie.workflow-evidence-index.v1",
        "schema_version": SCHEMA_VERSION,
        "public_safe": True,
        "build_id": build_id,
        "generated_at": summary["generated_at"],
        "summary": "workflow-matrix-summary.json",
        "summary_markdown": "workflow-matrix-summary.md",
        "workflows": [f"workflows/{item['workflow_id']}.json" for item in workflow_summaries],
    }
    _assert_public_safe_value("workflow_evidence_index", index)
    _write_json(output_root / "index.json", index)

    result = dict(summary)
    result["output"] = str(output_root.as_posix())
    return result


def _nullbridge_proof_root(evidence_root: str | Path, build_id: str) -> Path:
    root = Path(evidence_root).expanduser()
    if root.name == "nullbridge-proof":
        return root
    candidate = root / build_id / "nullbridge-proof"
    if candidate.exists() or build_id:
        return candidate
    return root / "nullbridge-proof"


def _require_payload_fields(label: str, payload: dict[str, Any], fields: tuple[str, ...]) -> list[str]:
    return [f"{label}:{field}:missing" for field in fields if field not in payload]


def _sanitize_failures(failures: list[str]) -> list[str]:
    sanitized: list[str] = []
    for failure in failures:
        if ":public_safety_marker:" in failure:
            sanitized.append(failure.split(":public_safety_marker:", 1)[0] + ":public_safety_marker")
        elif "C:" in failure or "\\" in failure:
            sanitized.append(failure.split(":", 1)[0] + ":path_detail_redacted")
        else:
            sanitized.append(failure)
    return sanitized


def validate_nullbridge_prerelease(
    *,
    evidence_root: str | Path = DEFAULT_EVIDENCE_ROOT,
    build_id: str,
    out: str | Path = "",
    now: datetime | None = None,
) -> dict[str, Any]:
    current = now or _now()
    proof_root = _nullbridge_proof_root(evidence_root, build_id)
    failures: list[str] = []
    proof_results: dict[str, str] = {}

    if not proof_root.exists():
        failures.append("nullbridge-proof:missing")
    else:
        for filename, expected_type in NULLBRIDGE_REQUIRED_PROOFS.items():
            path = proof_root / filename
            if not path.exists():
                failures.append(f"{filename}:missing")
                proof_results[expected_type] = "blocked"
                continue
            payload = _read_json(path)
            if payload.get("__load_error__"):
                failures.append(f"{filename}:malformed")
                proof_results[expected_type] = "blocked"
                continue
            failures.extend(_require_payload_fields(filename, payload, NULLBRIDGE_REQUIRED_PROOF_FIELDS))
            failures.extend(_public_safety_failures(filename, payload))
            if payload.get("build_id") != build_id:
                failures.append(f"{filename}:build_id:mismatch")
            if payload.get("component") != "NullBridge":
                failures.append(f"{filename}:component:mismatch")
            if payload.get("proof_type") != expected_type:
                failures.append(f"{filename}:proof_type:mismatch")
            if payload.get("status") != "pass":
                failures.append(f"{filename}:status:not_pass")
            if payload.get("aibenchie_verdict") != "pass":
                failures.append(f"{filename}:aibenchie_verdict:not_pass")
            if payload.get("public_safe") is not True:
                failures.append(f"{filename}:public_safe:not_true")
            if payload.get("raw_evidence_local_only") is not True:
                failures.append(f"{filename}:raw_evidence_local_only:not_true")
            if _parse_iso(payload.get("generated_at")) is None:
                failures.append(f"{filename}:generated_at:invalid")
            proof_results[expected_type] = "pass" if not any(failure.startswith(f"{filename}:") for failure in failures) else "blocked"

        status_path = proof_root / "nullbridge-status.json"
        if not status_path.exists():
            failures.append("nullbridge-status.json:missing")
        else:
            status = _read_json(status_path)
            failures.extend(_require_payload_fields("nullbridge-status.json", status, ("schema_version", "build_id", "generated_at", "expires_at", "status", "verdict", "freshness")))
            failures.extend(_public_safety_failures("nullbridge-status.json", status))
            if status.get("build_id") != build_id:
                failures.append("nullbridge-status.json:build_id:mismatch")
            if status.get("status") != "pass":
                failures.append("nullbridge-status.json:status:not_pass")
            if status.get("verdict") != "pass":
                failures.append("nullbridge-status.json:verdict:not_pass")
            if status.get("freshness") != "fresh":
                failures.append("nullbridge-status.json:freshness:not_fresh")
            expires_at = _parse_iso(status.get("expires_at"))
            if expires_at is None:
                failures.append("nullbridge-status.json:expires_at:invalid")
            elif expires_at <= current:
                failures.append("nullbridge-status.json:expires_at:stale")

        source_verdict_path = proof_root / "nullbridge-prerelease-verdict.json"
        if not source_verdict_path.exists():
            failures.append("nullbridge-prerelease-verdict.json:missing")
        else:
            source_verdict = _read_json(source_verdict_path)
            failures.extend(_require_payload_fields("nullbridge-prerelease-verdict.json", source_verdict, ("schema_version", "build_id", "component", "verdict", "generated_at", "expires_at")))
            failures.extend(_public_safety_failures("nullbridge-prerelease-verdict.json", source_verdict))
            if source_verdict.get("build_id") != build_id:
                failures.append("nullbridge-prerelease-verdict.json:build_id:mismatch")
            if source_verdict.get("component") != "NullBridge":
                failures.append("nullbridge-prerelease-verdict.json:component:mismatch")
            if source_verdict.get("verdict") != "pass":
                failures.append("nullbridge-prerelease-verdict.json:verdict:not_pass")

        notes_path = proof_root / "notes.md"
        if not notes_path.exists():
            failures.append("notes.md:missing")
        else:
            failures.extend(_public_safety_failures("notes.md", notes_path.read_text(encoding="utf-8")))

    sanitized_failures = _sanitize_failures(failures)
    ok = not failures
    result = {
        "schema": NULLBRIDGE_PRERELEASE_VERDICT_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "build_id": build_id,
        "suite": "echolabs",
        "component": "NullBridge",
        "verdict": "pass" if ok else "blocked",
        "aibenchie_verdict": "pass" if ok else "blocked",
        "generated_at": _iso(current),
        "expires_at": _iso(current + timedelta(minutes=10)),
        "proof_root_label": "nullbridge-proof",
        "pairing": proof_results.get("pairing", "blocked"),
        "approval": proof_results.get("approval", "blocked"),
        "denial": proof_results.get("denial", "blocked"),
        "route_safety": proof_results.get("route-safety", "blocked"),
        "leases": proof_results.get("lease", "blocked"),
        "artifact_response": proof_results.get("artifact-response", "blocked"),
        "signed_envelopes": proof_results.get("signed-envelope", "blocked"),
        "status_offline_unavailable": proof_results.get("status-offline", "blocked"),
        "audit_redaction": proof_results.get("audit-redaction", "blocked"),
        "android_failure_messaging": proof_results.get("android-failure-messaging", "blocked"),
        "public_safe_export": "pass" if ok else "blocked",
        "ok": ok,
        "failures": sanitized_failures,
        "blocked_reason": None if ok else "nullbridge_prerelease_evidence_incomplete",
    }
    _assert_public_safe(result)
    output = Path(out).expanduser() if out else proof_root / "nullbridge-prerelease-verdict.json"
    if proof_root.exists() and (ok or out):
        _write_json(output, result)
    return result


def _lv7_proof_root(evidence_root: str | Path, build_id: str) -> Path:
    root = Path(evidence_root).expanduser()
    if root.name == "lv7-proof":
        return root
    candidate = root / build_id / "lv7-proof"
    if candidate.exists() or build_id:
        return candidate
    return root / "lv7-proof"


def _state_failures(label: str, payload: dict[str, Any], required: set[str]) -> list[str]:
    states = payload.get("states")
    if not isinstance(states, list):
        return [f"{label}:states:missing"]
    missing = sorted(required - {str(item) for item in states})
    return [f"{label}:states:missing:{item}" for item in missing]


def _operation_failures(label: str, payload: dict[str, Any]) -> list[str]:
    operations = payload.get("operations")
    if not isinstance(operations, list) or not operations:
        return [f"{label}:operations:missing"]
    failures: list[str] = []
    for index, operation in enumerate(operations):
        if not isinstance(operation, dict):
            failures.append(f"{label}:operations[{index}]:not_object")
            continue
        missing = sorted(LV7_REQUIRED_OPERATION_FIELDS - set(operation))
        failures.extend(f"{label}:operations[{index}]:{field}:missing" for field in missing)
        if operation.get("required_approval") is not True:
            failures.append(f"{label}:operations[{index}]:required_approval:not_true")
        if operation.get("preflight_result") != "pass":
            failures.append(f"{label}:operations[{index}]:preflight_result:not_pass")
    return failures


def _lv7_specific_failures(filename: str, proof_type: str, payload: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if proof_type == "approval-result-history":
        failures.extend(_state_failures(filename, payload, LV7_REQUIRED_HISTORY_STATES))
        if payload.get("android_visible") is not True:
            failures.append(f"{filename}:android_visible:not_true")
    if proof_type == "repair-preflight":
        if payload.get("dry_run_required") is not True:
            failures.append(f"{filename}:dry_run_required:not_true")
        if payload.get("exact_operations_required") is not True:
            failures.append(f"{filename}:exact_operations_required:not_true")
        if payload.get("hidden_mutation_blocked") is not True:
            failures.append(f"{filename}:hidden_mutation_blocked:not_true")
        failures.extend(_operation_failures(filename, payload))
    if proof_type == "repair-approval-boundary":
        if payload.get("execution_without_approval_blocked") is not True:
            failures.append(f"{filename}:execution_without_approval_blocked:not_true")
        if payload.get("hidden_mutation_blocked") is not True:
            failures.append(f"{filename}:hidden_mutation_blocked:not_true")
        fail_closed = payload.get("fail_closed")
        if not isinstance(fail_closed, dict):
            failures.append(f"{filename}:fail_closed:missing")
        else:
            for state in ("denied", "expired", "missing", "revoked"):
                if fail_closed.get(state) is not True:
                    failures.append(f"{filename}:fail_closed:{state}:not_true")
    if proof_type == "artifact-package":
        if payload.get("export_mode") != "local":
            failures.append(f"{filename}:export_mode:not_local")
        if payload.get("public_safe_manifest") is not True:
            failures.append(f"{filename}:public_safe_manifest:not_true")
        if payload.get("checksums_present") is not True:
            failures.append(f"{filename}:checksums_present:not_true")
        nextcloud = payload.get("nextcloud")
        if not isinstance(nextcloud, dict):
            failures.append(f"{filename}:nextcloud:missing")
        elif nextcloud.get("required") is True:
            failures.append(f"{filename}:nextcloud:required_by_default")
    if proof_type == "policy-resource-memory":
        required_true = (
            "uses_existing_resource_manager",
            "does_not_create_second_lease_system",
            "model_intent_policy_gated",
            "model_intent_resource_aware",
            "memory_sanitized_summary_only",
        )
        for field in required_true:
            if payload.get(field) is not True:
                failures.append(f"{filename}:{field}:not_true")
    if proof_type == "android-visible-history":
        failures.extend(_state_failures(filename, payload, LV7_REQUIRED_HISTORY_STATES))
        if payload.get("messages_public_safe") is not True:
            failures.append(f"{filename}:messages_public_safe:not_true")
    if proof_type == "gcli":
        if payload.get("compact_readable") is not True:
            failures.append(f"{filename}:compact_readable:not_true")
        if payload.get("normal_output_public_safe") is not True:
            failures.append(f"{filename}:normal_output_public_safe:not_true")
    if proof_type == "sanitized-status":
        if payload.get("private_markers_rejected") is not True:
            failures.append(f"{filename}:private_markers_rejected:not_true")
        if payload.get("stale_not_healthy") is not True:
            failures.append(f"{filename}:stale_not_healthy:not_true")
    return failures


def _validate_lv7_manifest(proof_root: Path, build_id: str) -> list[str]:
    failures: list[str] = []
    manifest_path = proof_root / "local-package-manifest.json"
    checksum_path = proof_root / "local-package-checksums.json"
    if not manifest_path.exists():
        failures.append("local-package-manifest.json:missing")
        return failures
    manifest = _read_json(manifest_path)
    failures.extend(_require_payload_fields("local-package-manifest.json", manifest, ("schema_version", "package_id", "build_id", "created_at", "export_mode", "artifact_count", "artifacts", "checksums", "public_safe", "retention", "nextcloud")))
    failures.extend(_public_safety_failures("local-package-manifest.json", manifest))
    if manifest.get("build_id") != build_id:
        failures.append("local-package-manifest.json:build_id:mismatch")
    if manifest.get("export_mode") != "local":
        failures.append("local-package-manifest.json:export_mode:not_local")
    if manifest.get("public_safe") is not True:
        failures.append("local-package-manifest.json:public_safe:not_true")
    checksums = manifest.get("checksums")
    if not isinstance(checksums, dict) or not checksums:
        failures.append("local-package-manifest.json:checksums:missing")
    nextcloud = manifest.get("nextcloud")
    if isinstance(nextcloud, dict) and nextcloud.get("required") is True:
        failures.append("local-package-manifest.json:nextcloud:required_by_default")
    if not checksum_path.exists():
        failures.append("local-package-checksums.json:missing")
        return failures
    checksum_payload = _read_json(checksum_path)
    failures.extend(_require_payload_fields("local-package-checksums.json", checksum_payload, ("schema_version", "package_id", "build_id", "created_at", "checksums", "public_safe")))
    failures.extend(_public_safety_failures("local-package-checksums.json", checksum_payload))
    if checksum_payload.get("build_id") != build_id:
        failures.append("local-package-checksums.json:build_id:mismatch")
    if checksum_payload.get("public_safe") is not True:
        failures.append("local-package-checksums.json:public_safe:not_true")
    if not isinstance(checksum_payload.get("checksums"), dict) or not checksum_payload.get("checksums"):
        failures.append("local-package-checksums.json:checksums:missing")
    return failures


def validate_lv7_operator_loop(
    *,
    evidence_root: str | Path = DEFAULT_EVIDENCE_ROOT,
    build_id: str,
    out: str | Path = "",
    now: datetime | None = None,
) -> dict[str, Any]:
    current = now or _now()
    proof_root = _lv7_proof_root(evidence_root, build_id)
    failures: list[str] = []
    proof_results: dict[str, str] = {}

    if not proof_root.exists():
        failures.append("lv7-proof:missing")
    else:
        for filename, expected_type in LV7_REQUIRED_PROOFS.items():
            path = proof_root / filename
            if not path.exists():
                failures.append(f"{filename}:missing")
                proof_results[expected_type] = "blocked"
                continue
            payload = _read_json(path)
            if payload.get("__load_error__"):
                failures.append(f"{filename}:malformed")
                proof_results[expected_type] = "blocked"
                continue
            failures.extend(_require_payload_fields(filename, payload, LV7_REQUIRED_PROOF_FIELDS))
            failures.extend(_public_safety_failures(filename, payload))
            if payload.get("build_id") != build_id:
                failures.append(f"{filename}:build_id:mismatch")
            if payload.get("component") != "Lv-7":
                failures.append(f"{filename}:component:mismatch")
            if payload.get("proof_type") != expected_type:
                failures.append(f"{filename}:proof_type:mismatch")
            if payload.get("status") != "pass":
                failures.append(f"{filename}:status:not_pass")
            if payload.get("aibenchie_verdict") != "pass":
                failures.append(f"{filename}:aibenchie_verdict:not_pass")
            if payload.get("public_safe") is not True:
                failures.append(f"{filename}:public_safe:not_true")
            if payload.get("raw_evidence_local_only") is not True:
                failures.append(f"{filename}:raw_evidence_local_only:not_true")
            if _parse_iso(payload.get("generated_at")) is None:
                failures.append(f"{filename}:generated_at:invalid")
            failures.extend(_lv7_specific_failures(filename, expected_type, payload))
            proof_results[expected_type] = "pass" if not any(failure.startswith(f"{filename}:") for failure in failures) else "blocked"

        status_path = proof_root / "lv7-operator-status.json"
        if not status_path.exists():
            failures.append("lv7-operator-status.json:missing")
        else:
            status = _read_json(status_path)
            failures.extend(_require_payload_fields("lv7-operator-status.json", status, ("schema_version", "build_id", "generated_at", "expires_at", "status", "freshness", "component")))
            failures.extend(_public_safety_failures("lv7-operator-status.json", status))
            if status.get("build_id") != build_id:
                failures.append("lv7-operator-status.json:build_id:mismatch")
            if status.get("component") != "Lv-7":
                failures.append("lv7-operator-status.json:component:mismatch")
            if status.get("status") != "pass":
                failures.append("lv7-operator-status.json:status:not_pass")
            if status.get("freshness") != "fresh":
                failures.append("lv7-operator-status.json:freshness:not_fresh")
            expires_at = _parse_iso(status.get("expires_at"))
            if expires_at is None:
                failures.append("lv7-operator-status.json:expires_at:invalid")
            elif expires_at <= current:
                failures.append("lv7-operator-status.json:expires_at:stale")
            repair = status.get("repair_preflight") if isinstance(status.get("repair_preflight"), dict) else {}
            if repair.get("hidden_mutation_blocked") is not True:
                failures.append("lv7-operator-status.json:hidden_mutation_blocked:not_true")

        verdict_path = proof_root / "lv7-operator-loop-verdict.json"
        if not verdict_path.exists():
            failures.append("lv7-operator-loop-verdict.json:missing")
        else:
            verdict = _read_json(verdict_path)
            failures.extend(_require_payload_fields("lv7-operator-loop-verdict.json", verdict, ("schema_version", "build_id", "component", "verdict", "generated_at", "expires_at")))
            failures.extend(_public_safety_failures("lv7-operator-loop-verdict.json", verdict))
            if verdict.get("build_id") != build_id:
                failures.append("lv7-operator-loop-verdict.json:build_id:mismatch")
            if verdict.get("component") != "Lv-7":
                failures.append("lv7-operator-loop-verdict.json:component:mismatch")
            if verdict.get("verdict") != "pass":
                failures.append("lv7-operator-loop-verdict.json:verdict:not_pass")

        notes_path = proof_root / "notes.md"
        if not notes_path.exists():
            failures.append("notes.md:missing")
        else:
            failures.extend(_public_safety_failures("notes.md", notes_path.read_text(encoding="utf-8")))
        failures.extend(_validate_lv7_manifest(proof_root, build_id))

    sanitized_failures = _sanitize_failures(failures)
    ok = not failures
    result = {
        "schema": LV7_OPERATOR_LOOP_VERDICT_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "build_id": build_id,
        "suite": "echolabs",
        "component": "Lv-7",
        "verdict": "pass" if ok else "blocked",
        "aibenchie_verdict": "pass" if ok else "blocked",
        "generated_at": _iso(current),
        "expires_at": _iso(current + timedelta(minutes=10)),
        "proof_root_label": "lv7-proof",
        "approval_result_history": proof_results.get("approval-result-history", "blocked"),
        "repair_preflight": proof_results.get("repair-preflight", "blocked"),
        "approval_boundary": proof_results.get("repair-approval-boundary", "blocked"),
        "artifact_package_export": proof_results.get("artifact-package", "blocked"),
        "sanitized_status": proof_results.get("sanitized-status", "blocked"),
        "policy_resource_memory": proof_results.get("policy-resource-memory", "blocked"),
        "android_visible_history": proof_results.get("android-visible-history", "blocked"),
        "gcli": proof_results.get("gcli", "blocked"),
        "public_safe_export": "pass" if ok else "blocked",
        "ok": ok,
        "failures": sanitized_failures,
        "blocked_reason": None if ok else "lv7_operator_loop_evidence_incomplete",
    }
    _assert_public_safe(result)
    output = Path(out).expanduser() if out else proof_root / "lv7-operator-loop-verdict.json"
    if proof_root.exists() and (ok or out):
        _write_json(output, result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage AIBenchie release truth spine evidence.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument("--evidence-root", default=str(DEFAULT_EVIDENCE_ROOT))
        subparser.add_argument("--json", action="store_true")

    verify = subparsers.add_parser("verify", help="Write latest build and verdict evidence.")
    add_common(verify)
    verify.add_argument("--suite", default="echolabs")
    verify.add_argument("--build-id", default="")
    verify.add_argument("--suite-version", default=DEFAULT_SUITE_VERSION)
    verify.add_argument("--verdict", default="not-run", choices=sorted(VERDICT_VALUES))
    verify.add_argument("--status", default="", choices=["", *sorted(STATUS_VALUES)])

    promote = subparsers.add_parser("promote-passing", help="Promote a passing build to latest-passing.json.")
    add_common(promote)
    promote.add_argument("--build-id", required=True)

    workflows = subparsers.add_parser("validate-workflows", help="Validate workflow proof folders and Store mappings.")
    add_common(workflows)
    workflows.add_argument("--matrix", default=str(DEFAULT_WORKFLOW_MATRIX))
    workflows.add_argument("--store-capabilities", default=str(DEFAULT_STORE_CAPABILITIES))
    workflows.add_argument("--build-id", default="")
    workflows.add_argument("--out", default="")

    website = subparsers.add_parser("export-website-status", help="Export public-safe suite status JSON.")
    add_common(website)
    website.add_argument("--out", required=True)

    android = subparsers.add_parser("export-android-release", help="Export Android release status shell.")
    add_common(android)
    android.add_argument("--out", required=True)

    store = subparsers.add_parser("export-store-capabilities", help="Export Store capability stage status.")
    add_common(store)
    store.add_argument("--store-capabilities", default=str(DEFAULT_STORE_CAPABILITIES))
    store.add_argument("--out", required=True)

    workflow_summary = subparsers.add_parser(
        "export-workflow-summary",
        help="Export public-safe MS3 workflow evidence summaries.",
    )
    add_common(workflow_summary)
    workflow_summary.add_argument("--build-id", required=True)
    workflow_summary.add_argument("--matrix", default=str(DEFAULT_WORKFLOW_MATRIX))
    workflow_summary.add_argument("--store-capabilities", default=str(DEFAULT_STORE_CAPABILITIES))
    workflow_summary.add_argument("--out", required=True)

    nullbridge = subparsers.add_parser(
        "validate-nullbridge",
        help="Validate NullBridge MS4 prerelease evidence.",
    )
    add_common(nullbridge)
    nullbridge.add_argument("--build-id", required=True)
    nullbridge.add_argument("--out", default="")

    lv7 = subparsers.add_parser(
        "validate-lv7",
        help="Validate Lv-7 MS5 operator-loop evidence.",
    )
    add_common(lv7)
    lv7.add_argument("--build-id", required=True)
    lv7.add_argument("--out", default="")

    return parser


def _print_result(result: dict[str, Any], *, json_output: bool, title: str) -> None:
    if json_output:
        print(json.dumps(result, indent=2, sort_keys=True))
        return
    print(title)
    print(f"Build: {result.get('build_id', '(none)')}")
    if "aibenchie_verdict" in result:
        print(f"Verdict: {str(result['aibenchie_verdict']).upper()}")
    if "status" in result:
        print(f"Status: {str(result['status']).upper()}")
    if result.get("failures"):
        print("Failures:")
        for failure in result["failures"]:
            print(f"- {failure}")
    print("Result: PASS" if result.get("ok", True) else "Result: FAIL")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "verify":
        result = verify_release_spine(
            suite=args.suite,
            evidence_root=args.evidence_root,
            build_id=args.build_id,
            suite_version=args.suite_version,
            verdict=args.verdict,
            status=args.status,
        )
        _print_result(result, json_output=args.json, title="AIBenchie Release Spine Verify")
        return 0 if result["ok"] else 1
    if args.command == "promote-passing":
        result = promote_passing_candidate(build_id=args.build_id, evidence_root=args.evidence_root)
        _print_result(result, json_output=args.json, title="AIBenchie Release Spine Promote Passing")
        return 0 if result["ok"] else 1
    if args.command == "validate-workflows":
        result = validate_workflow_matrix(
            matrix=args.matrix,
            store_capabilities=args.store_capabilities,
            evidence_root=args.evidence_root,
            build_id=args.build_id,
            out=args.out,
        )
        _print_result(result, json_output=args.json, title="AIBenchie Workflow Matrix Validation")
        return 0 if result["ok"] else 1
    if args.command == "export-website-status":
        result = export_website_status(out=args.out, evidence_root=args.evidence_root)
        _print_result(result, json_output=args.json, title="AIBenchie Website Status Export")
        return 0
    if args.command == "export-android-release":
        result = export_android_release_status(out=args.out, evidence_root=args.evidence_root)
        _print_result(result, json_output=args.json, title="AIBenchie Android Release Export")
        return 0
    if args.command == "export-store-capabilities":
        result = export_store_capabilities(
            out=args.out,
            store_capabilities=args.store_capabilities,
            evidence_root=args.evidence_root,
        )
        _print_result(result, json_output=args.json, title="AIBenchie Store Capabilities Export")
        return 0
    if args.command == "export-workflow-summary":
        result = export_workflow_summary(
            build_id=args.build_id,
            out=args.out,
            evidence_root=args.evidence_root,
            matrix=args.matrix,
            store_capabilities=args.store_capabilities,
        )
        _print_result(result, json_output=args.json, title="AIBenchie Workflow Summary Export")
        return 0 if result.get("ok") else 1
    if args.command == "validate-nullbridge":
        result = validate_nullbridge_prerelease(
            build_id=args.build_id,
            evidence_root=args.evidence_root,
            out=args.out,
        )
        _print_result(result, json_output=args.json, title="AIBenchie NullBridge Prerelease Validation")
        return 0 if result.get("ok") else 1
    if args.command == "validate-lv7":
        result = validate_lv7_operator_loop(
            build_id=args.build_id,
            evidence_root=args.evidence_root,
            out=args.out,
        )
        _print_result(result, json_output=args.json, title="AIBenchie Lv-7 Operator Loop Validation")
        return 0 if result.get("ok") else 1
    return 1


if __name__ == "__main__":
    sys.exit(main())
