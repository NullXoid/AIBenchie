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
STORE_CAPABILITIES_SCHEMA = "aibenchie.store-capabilities.v1"
DEFAULT_SUITE_VERSION = "0.9.0-prerelease.1"
DEFAULT_EVIDENCE_ROOT = Path(".suite/local/aibenchie/release/evidence")
DEFAULT_WORKFLOW_MATRIX = Path("configs/echolabs_workflow_matrix.json")
DEFAULT_STORE_CAPABILITIES = Path("configs/echolabs_store_capabilities.json")

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
    "service_token",
    "nullbridge_service_token",
    "cookie",
    "jwt",
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
    leaked = [marker for marker in PUBLIC_FORBIDDEN_MARKERS if marker in text]
    if leaked:
        raise ValueError(f"public output contains forbidden marker(s): {', '.join(leaked)}")


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
    for field in ("android_submit_proof", "job_status_proof", "gallery_artifact_proof", "failure_message_proof"):
        if proof.get(field) is not True:
            failures.append(f"{workflow_id}:proof_field_not_true:{field}")
    if proof.get("aibenchie_verdict") != "pass":
        failures.append(f"{workflow_id}:proof_verdict_not_pass")
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
) -> dict[str, Any]:
    matrix_payload = _load_workflow_matrix(matrix)
    store_payload = _load_store_capabilities(store_capabilities)
    workflows = [item for item in matrix_payload.get("workflows", []) if isinstance(item, dict)]
    capabilities = [item for item in store_payload.get("capabilities", []) if isinstance(item, dict)]
    capabilities_by_workflow = {str(item.get("workflow_id") or ""): item for item in capabilities}
    build_root = _resolve_build_root(evidence_root, build_id)
    actual_build_id = build_id or build_root.name
    failures: list[str] = []

    if matrix_payload.get("__load_error__"):
        failures.append(f"workflow_matrix_load_error:{matrix_payload['__load_error__']}")
    if store_payload.get("__load_error__"):
        failures.append(f"store_capabilities_load_error:{store_payload['__load_error__']}")
    if matrix_payload.get("schema") not in {"", None, WORKFLOW_MATRIX_SCHEMA}:
        failures.append(f"workflow_matrix_schema_invalid:{matrix_payload.get('schema')}")
    if store_payload.get("schema") not in {"", None, STORE_CAPABILITIES_SCHEMA}:
        failures.append(f"store_capabilities_schema_invalid:{store_payload.get('schema')}")

    prerelease_count = 0
    for workflow in workflows:
        workflow_id = str(workflow.get("workflow_id") or "")
        release_stage = str(workflow.get("release_stage") or "")
        state = str(workflow.get("state") or "")
        if not workflow_id:
            failures.append("workflow_id_missing")
            continue
        if workflow_id not in capabilities_by_workflow:
            failures.append(f"{workflow_id}:missing_store_capability_mapping")
        if release_stage == "prerelease":
            prerelease_count += 1
            if state == "blocked" or workflow.get("blocked_reason"):
                failures.append(f"{workflow_id}:blocked_workflow_marked_prerelease")
            proof_dir = build_root / str(workflow.get("proof_path") or f"workflow-proofs/{workflow_id}")
            failures.extend(_validate_workflow_proof(proof_dir, workflow, actual_build_id))
        elif state in {"installable", "enabled"} and release_stage in {"blocked", "later"}:
            failures.append(f"{workflow_id}:blocked_or_later_workflow_installable")

    return {
        "schema": "aibenchie.workflow-matrix-validation.v1",
        "schema_version": SCHEMA_VERSION,
        "generated_at": _iso(_now()),
        "ok": not failures,
        "matrix": str(Path(matrix).as_posix()),
        "store_capabilities": str(Path(store_capabilities).as_posix()),
        "evidence_root": str(Path(evidence_root).as_posix()),
        "build_id": actual_build_id,
        "workflow_count": len(workflows),
        "prerelease_count": prerelease_count,
        "capability_count": len(capabilities),
        "failures": failures,
    }


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
    return 1


if __name__ == "__main__":
    sys.exit(main())
