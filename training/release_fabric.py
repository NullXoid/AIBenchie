from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SUITE_ROOT = PROJECT_ROOT / ".suite"
POLICIES_ROOT = SUITE_ROOT / "policies"
MANIFESTS_ROOT = SUITE_ROOT / "manifests"
WORKFLOWS_ROOT = PROJECT_ROOT / ".forgejo" / "workflows"

SHA256_RE = re.compile(r"^[a-fA-F0-9]{64}$")
USE_RE = re.compile(r"uses:\s*([^\s#]+)")
NULLBRIDGE_RUNTIME_RE = re.compile(
    r"(^|/)(inbox|outbox|processed|failed|approvals)/",
    re.IGNORECASE,
)
SERVICE_CREDENTIAL_RE = re.compile(
    r"NULLBRIDGE_(?:ANDROID_)?SERVICE_(?:JWT_)?SECRET|NULLBRIDGE_SERVICE_TOKEN|X-NullBridge-Service|Authorization\s*:\s*[\"']?\s*Bearer",
    re.IGNORECASE,
)
DIRECT_NULLBRIDGE_ROUTE_RE = re.compile(
    r"/bridge/requests|/bridge/routes|/bridge/dispatch",
    re.IGNORECASE,
)


REQUIRED_POLICY_FILES = [
    "actions-policy.json",
    "aibenchie-gates.json",
    "breakglass-policy.json",
    "nullbridge-capabilities.json",
    "nullbridge-registry.json",
    "privacy-levels.json",
    "release-policy.json",
    "resource-policy.json",
    "runner-policy.json",
]

REQUIRED_MANIFEST_FILES = [
    "artifact-manifest.schema.json",
    "release-manifest.schema.json",
    "sbom-policy.json",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_policy_tree(root: Path = PROJECT_ROOT) -> list[str]:
    errors: list[str] = []
    policies_root = root / ".suite" / "policies"
    manifests_root = root / ".suite" / "manifests"
    workflows_root = root / ".forgejo" / "workflows"
    for name in REQUIRED_POLICY_FILES:
        path = policies_root / name
        if not path.exists():
            errors.append(f"missing_policy:{name}")
            continue
        try:
            load_json(path)
        except json.JSONDecodeError:
            errors.append(f"invalid_json:{name}")
    for name in REQUIRED_MANIFEST_FILES:
        path = manifests_root / name
        if not path.exists():
            errors.append(f"missing_manifest:{name}")
            continue
        try:
            load_json(path)
        except json.JSONDecodeError:
            errors.append(f"invalid_json:{name}")
    for name in ["ci.yaml", "aibenchie.yaml", "release-candidate.yaml", "publish.yaml"]:
        path = workflows_root / name
        if not path.exists():
            errors.append(f"missing_workflow:{name}")
            continue
        errors.extend(f"{name}:{error}" for error in validate_workflow_file(path))
    return errors


def validate_release_policy(policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if policy.get("source_of_truth") != "forgejo":
        errors.append("source_of_truth:not_forgejo")
    if policy.get("github_posture") != "read_only_ci":
        errors.append("github_posture:not_read_only_ci")
    for key in [
        "forbid_github_production_release",
        "forbid_github_production_secrets",
        "forbid_unsigned_updates",
        "publisher_requires_manifest_verification",
        "publisher_rejects_digest_mismatch",
        "publisher_rejects_unsigned_verdict",
        "publisher_rejects_unsigned_manifest",
        "publisher_rejects_non_forgejo_source",
    ]:
        if policy.get(key) is not True:
            errors.append(f"{key}:not_enforced")
    if "release_hardware_key" not in policy.get("hardware_signing_identities", []):
        errors.append("hardware_signing_identities:missing_release_key")
    return errors


def validate_runner_policy(policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for runner in policy.get("runners", []):
        name = runner.get("name", "unknown")
        if runner.get("arbitrary_code") and (
            runner.get("production_secrets") or runner.get("signing_authority") or runner.get("package_publish")
        ):
            errors.append(f"{name}:arbitrary_code_with_sensitive_power")
        if runner.get("signing_authority") and not runner.get("hardware_key_required"):
            errors.append(f"{name}:signing_without_hardware_key")
        if runner.get("package_publish") and not runner.get("publishes_signed_artifacts_only"):
            errors.append(f"{name}:publishes_without_manifest_guard")
    return errors


def validate_actions_policy(policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if policy.get("source_of_truth") != "forgejo":
        errors.append("source_of_truth:not_forgejo")
    if policy.get("github_posture") != "read_only_ci":
        errors.append("github_posture:not_read_only_ci")
    if policy.get("require_pin_or_mirror_for_release") is not True:
        errors.append("release_actions:not_pin_or_mirror_required")
    if policy.get("internal_action_mirror", {}).get("enabled") is not True:
        errors.append("internal_action_mirror:not_enabled")
    return errors


def validate_aibenchie_gates(policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    tracks = set(policy.get("required_tracks", []))
    for required in {
        "nullbridge_enforcement",
        "privacy",
        "prompt_editor_leakage",
        "forgejo_workflow_policy",
        "runner_isolation",
        "release_manifest_validation",
        "sbom_validation",
        "hardware_signature_verification",
        "breakglass_grant_verification",
    }:
        if required not in tracks:
            errors.append(f"required_track_missing:{required}")
    for verdict in policy.get("accepted_release_verdicts", []):
        if verdict not in policy.get("verdicts", []):
            errors.append(f"accepted_verdict_unknown:{verdict}")
    return errors


def validate_resource_policy(policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if policy.get("deny_unbounded_resources") is not True:
        errors.append("deny_unbounded_resources:not_enforced")
    if policy.get("lease_required_for_heavy_work") is not True:
        errors.append("lease_required_for_heavy_work:not_enforced")
    if policy.get("default_deny_without_profile") is not True:
        errors.append("default_deny_without_profile:not_enforced")

    for name, profile in policy.get("profiles", {}).items():
        limits = profile.get("limits", {})
        for key in ["max_cpu_percent", "max_memory_mb", "max_parallel_jobs", "max_duration_seconds"]:
            value = limits.get(key)
            if not isinstance(value, int) or value <= 0:
                errors.append(f"{name}:{key}:missing_or_invalid")
        if limits.get("max_cpu_percent", 101) > 100:
            errors.append(f"{name}:max_cpu_percent:over_100")
        if limits.get("max_parallel_jobs", 999) > 4:
            errors.append(f"{name}:max_parallel_jobs:too_high")
        if profile.get("platform") in {"android", "ios"}:
            if limits.get("max_memory_mb", 999999) > 2048:
                errors.append(f"{name}:mobile_memory_limit:too_high")
            if limits.get("max_duration_seconds", 999999) > 300:
                errors.append(f"{name}:mobile_duration_limit:too_high")

    for capability, rule in policy.get("capability_classes", {}).items():
        if not rule.get("requires_lease"):
            errors.append(f"{capability}:lease:not_required")
        if not rule.get("allowed_profiles"):
            errors.append(f"{capability}:allowed_profiles:missing")
    return errors


def validate_nullbridge_registry(policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = set(policy.get("required_backend_identities", []))
    for identity in [
        "website_backend",
        "wrapper_backend",
        "windows_backend",
        "android_backend",
        "ios_backend",
        "aibenchie_service",
        "codex_service",
        "ollama_service",
    ]:
        if identity not in required:
            errors.append(f"identity:missing:{identity}")
    for key in [
        "requires_service_auth",
        "deny_unknown_backends",
        "deny_unknown_targets",
        "deny_unknown_capabilities",
        "audit_required",
    ]:
        if policy.get(key) is not True:
            errors.append(f"{key}:not_enforced")
    return errors


def validate_nullbridge_capabilities(policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if policy.get("deny_by_default") is not True:
        errors.append("deny_by_default:not_enforced")
    seen: set[str] = set()
    for rule in policy.get("capabilities", []):
        capability = rule.get("capability")
        if not capability:
            errors.append("capability:missing_name")
            continue
        if capability in seen:
            errors.append(f"capability:duplicate:{capability}")
        seen.add(capability)
        for key in ["allowed_callers", "allowed_platforms", "allowed_targets"]:
            if not rule.get(key):
                errors.append(f"{capability}:{key}:missing")
        if rule.get("requires_user_auth") is not True:
            errors.append(f"{capability}:requires_user_auth:not_enforced")
    for required in ["chat.stream", "artifacts.send_to_codex", "repo.audit"]:
        if required not in seen:
            errors.append(f"capability:missing:{required}")
    return errors


def authorize_nullbridge_route(
    request: dict[str, Any],
    registry: dict[str, Any] | None = None,
    capabilities: dict[str, Any] | None = None,
) -> dict[str, Any]:
    registry = registry or load_json(POLICIES_ROOT / "nullbridge-registry.json")
    capabilities = capabilities or load_json(POLICIES_ROOT / "nullbridge-capabilities.json")
    caller = request.get("caller_backend_id")
    capability = request.get("capability")
    target = request.get("target")
    platform = request.get("platform") or (request.get("acting_user") or {}).get("platform")
    user_id = (request.get("acting_user") or {}).get("user_id")

    required_identities = set(registry.get("required_backend_identities", []))
    if caller not in required_identities:
        return deny_route(request, "unknown_backend")
    if registry.get("requires_service_auth") is True and request.get("service_auth_valid") is not True:
        return deny_route(request, "invalid_service_auth")

    rule = next((item for item in capabilities.get("capabilities", []) if item.get("capability") == capability), None)
    if not rule:
        return deny_route(request, "unknown_capability")
    if caller not in rule.get("allowed_callers", []):
        return deny_route(request, "caller_not_allowed")
    if platform not in rule.get("allowed_platforms", []):
        return deny_route(request, "platform_not_allowed")
    if target not in rule.get("allowed_targets", []):
        return deny_route(request, "target_not_allowed")
    if rule.get("requires_user_auth") is True and not user_id:
        return deny_route(request, "missing_user_context")
    return route_decision(request, "allow", "allowed")


def deny_route(request: dict[str, Any], reason: str) -> dict[str, Any]:
    return route_decision(request, "deny", reason)


def route_decision(request: dict[str, Any], decision: str, reason: str) -> dict[str, Any]:
    acting_user = request.get("acting_user") or {}
    user_id = str(acting_user.get("user_id") or "")
    return {
        "event": "nullbridge.route_decision",
        "trace_id": request.get("trace_id", ""),
        "caller_backend_id": request.get("caller_backend_id", ""),
        "acting_user_id_hash": hashlib.sha256(user_id.encode("utf-8")).hexdigest() if user_id else "",
        "platform": request.get("platform") or acting_user.get("platform", ""),
        "capability": request.get("capability", ""),
        "target": request.get("target", ""),
        "decision": decision,
        "reason": reason,
    }


def validate_nullbridge_audit_log(entry: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in ["event", "trace_id", "caller_backend_id", "platform", "capability", "target", "decision", "reason"]:
        if not entry.get(key):
            errors.append(f"audit:{key}:missing")
    if entry.get("event") != "nullbridge.route_decision":
        errors.append("audit:event:wrong_type")
    text = json.dumps(entry, sort_keys=True).lower()
    for forbidden in ["authorization", "bearer ", "cookie", "service_token", "nullbridge_service_token", "jwt", "eyj"]:
        if forbidden in text:
            errors.append(f"audit:secret_leak:{forbidden.strip()}")
    return errors


def validate_release_manifest(manifest: dict[str, Any], schema_path: Path | None = None) -> list[str]:
    errors: list[str] = []
    schema = load_json(schema_path or MANIFESTS_ROOT / "release-manifest.schema.json")
    validator = Draft202012Validator(schema)
    errors.extend(f"schema:{'.'.join(str(part) for part in error.path) or 'root'}:{error.message}" for error in validator.iter_errors(manifest))
    release_policy = load_json(POLICIES_ROOT / "release-policy.json")
    if manifest.get("signed_by") not in release_policy.get("hardware_signing_identities", []):
        errors.append("signature:not_hardware_identity")
    if manifest.get("aibenchie_verdict") not in release_policy.get("accepted_aibenchie_verdicts", []):
        errors.append("aibenchie_verdict:not_accepted")
    return errors


def validate_aibenchie_summary(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    gates = load_json(POLICIES_ROOT / "aibenchie-gates.json")
    if report.get("verdict") not in gates.get("accepted_release_verdicts", []):
        errors.append("verdict:not_release_accepted")
    if not report.get("signature"):
        errors.append("signature:missing")
    tracks = report.get("tracks", {})
    for track in gates.get("required_tracks", []):
        if track not in tracks:
            errors.append(f"track:missing:{track}")
    if report.get("critical_blocks"):
        errors.append("critical_blocks:present")
    return errors


def validate_breakglass_grant(grant: dict[str, Any], now: datetime | None = None) -> list[str]:
    errors: list[str] = []
    policy = load_json(POLICIES_ROOT / "breakglass-policy.json")
    if grant.get("signed_by_hardware_key") is not True:
        errors.append("hardware_key:required")
    if grant.get("requested_capability") not in policy.get("allowed_capabilities", []):
        errors.append("capability:not_allowed")
    if grant.get("target") not in policy.get("allowed_targets", []):
        errors.append("target:not_allowed")
    if grant.get("environment") not in policy.get("allowed_environments", []):
        errors.append("environment:not_allowed")
    if grant.get("checkpoint_required") is not True:
        errors.append("checkpoint:required")
    if not str(grant.get("encrypted_forgejo_record", "")).endswith(".encrypted"):
        errors.append("encrypted_forgejo_record:not_encrypted")
    profile_name = grant.get("network_profile")
    profile = policy.get("network_profiles", {}).get(profile_name)
    if not profile:
        errors.append("network_profile:not_quarantined")
    else:
        if profile.get("deny_external_network") is not True:
            errors.append("network_profile:deny_external_network_required")
        if profile.get("max_parallel_jobs") != 1:
            errors.append("network_profile:max_parallel_jobs_not_one")
    allowed_until = grant.get("allowed_until")
    if allowed_until:
        expires_at = datetime.fromisoformat(str(allowed_until).replace("Z", "+00:00"))
        if expires_at <= (now or datetime.now(timezone.utc)):
            errors.append("grant:expired")
    else:
        errors.append("allowed_until:missing")
    return errors


def validate_workflow_file(path: Path) -> list[str]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    text = path.read_text(encoding="utf-8")
    return validate_workflow_text(text, workflow=payload, name=path.name)


def validate_workflow_text(text: str, workflow: dict[str, Any] | None = None, name: str = "workflow") -> list[str]:
    errors: list[str] = []
    actions_policy = load_json(POLICIES_ROOT / "actions-policy.json") if POLICIES_ROOT.exists() else {}
    forbidden_refs = set(actions_policy.get("forbidden_action_refs", ["main", "master", "latest", "HEAD"]))
    for match in USE_RE.finditer(text):
        ref = match.group(1)
        if "@" not in ref:
            errors.append(f"action_ref_missing:{ref}")
            continue
        action, version = ref.rsplit("@", 1)
        if version in forbidden_refs:
            errors.append(f"mutable_action_ref:{action}@{version}")
    lowered = text.lower()
    if name == "ci.yaml" and ("publish" in lowered or "package_write" in lowered or "release_hardware_key" in lowered):
        errors.append("ci:publish_or_signing_material_forbidden")
    if "nullbridge_service_token" in lowered or "production_secret" in lowered:
        errors.append("workflow:production_secret_reference")
    workflow = workflow or {}
    jobs = workflow.get("jobs", {}) if isinstance(workflow, dict) else {}
    runner_policy = load_json(POLICIES_ROOT / "runner-policy.json") if POLICIES_ROOT.exists() else {"runners": []}
    known_runners = {runner["name"] for runner in runner_policy.get("runners", [])}
    for job_name, job in jobs.items():
        runner = job.get("runs-on") if isinstance(job, dict) else None
        if runner and runner not in known_runners:
            errors.append(f"job:{job_name}:unknown_runner:{runner}")
    return errors


def validate_publisher_inputs(manifest: dict[str, Any], report: dict[str, Any], artifact_root: Path) -> list[str]:
    errors = validate_release_manifest(manifest)
    errors.extend(validate_aibenchie_summary(report))
    if report.get("source_commit") != manifest.get("source_commit"):
        errors.append("aibenchie_report:source_commit_mismatch")
    for index, artifact in enumerate(manifest.get("artifacts", [])):
        path = artifact_root / artifact.get("name", "")
        if not path.exists():
            errors.append(f"artifact[{index}]:missing")
        elif sha256_file(path) != artifact.get("sha256"):
            errors.append(f"artifact[{index}]:sha256_mismatch")
    sbom = manifest.get("sbom", {})
    sbom_path = artifact_root / sbom.get("name", "")
    if not sbom_path.exists():
        errors.append("sbom:missing")
    elif sha256_file(sbom_path) != sbom.get("sha256"):
        errors.append("sbom:sha256_mismatch")
    return errors


def validate_suite_adapter_compliance(suite_root: Path) -> list[str]:
    """Validate backend-side NullBridge adapter boundaries across a checked-out suite.

    This intentionally accepts a caller-provided root instead of storing private
    repo locations. Missing repos are reported as gaps by repo label.
    """
    errors: list[str] = []
    specs = [
        {
            "label": "wrapper",
            "adapter": Path("Felnx/NullXoid/.NullXoid/backend/nullbridge_adapter.py"),
            "backend_roots": [Path("Felnx/NullXoid/.NullXoid/backend")],
            "frontend_roots": [Path("Felnx/NullXoid/src"), Path("Felnx/NullXoid/.NullXoid/frontend")],
        },
        {
            "label": "windows",
            "adapter": Path("AiAssistant/src/bridge/nullbridge_service_adapter.cpp"),
            "backend_roots": [Path("AiAssistant/src/bridge")],
            "frontend_roots": [Path("AiAssistant/src/ui")],
        },
        {
            "label": "android",
            "adapter": Path("NullXoidAndroid/app/src/main/java/com/nullxoid/android/backend/nullbridge/NullBridgeAdapter.kt"),
            "backend_roots": [Path("NullXoidAndroid/app/src/main/java/com/nullxoid/android/backend")],
            "frontend_roots": [Path("NullXoidAndroid/app/src/main/java/com/nullxoid/android/ui")],
        },
    ]

    for spec in specs:
        adapter = suite_root / spec["adapter"]
        label = str(spec["label"])
        if not adapter.is_file():
            errors.append(f"{label}:adapter:missing")
            continue
        adapter_text = adapter.read_text(encoding="utf-8", errors="ignore")
        if "actingUser" not in adapter_text and "acting_user" not in adapter_text:
            errors.append(f"{label}:acting_user:missing")

        for frontend_root in spec["frontend_roots"]:
            root = suite_root / frontend_root
            if root.exists():
                errors.extend(
                    f"{label}:frontend:{error}"
                    for error in validate_frontend_nullbridge_boundaries(root)
                )

    nullbridge_root = suite_root / "NullBridge"
    if nullbridge_root.exists():
        errors.extend(
            f"nullbridge:{error}"
            for error in validate_nullbridge_runtime_artifacts_untracked(nullbridge_root)
        )
    else:
        errors.append("nullbridge:repo:missing")
    return errors


def validate_frontend_nullbridge_boundaries(frontend_root: Path) -> list[str]:
    errors: list[str] = []
    for path in iter_source_files(frontend_root):
        relative = path.relative_to(frontend_root).as_posix()
        text = path.read_text(encoding="utf-8", errors="ignore")
        if SERVICE_CREDENTIAL_RE.search(text):
            errors.append(f"{relative}:service_credential_reference")
        if DIRECT_NULLBRIDGE_ROUTE_RE.search(text):
            errors.append(f"{relative}:direct_privileged_nullbridge_route")
    return errors


def validate_nullbridge_runtime_artifacts_untracked(nullbridge_repo: Path) -> list[str]:
    errors: list[str] = []
    try:
        tracked = subprocess_check_output(["git", "ls-files"], cwd=nullbridge_repo).splitlines()
    except Exception as exc:  # pragma: no cover - defensive for non-git fixture use
        errors.append(f"git_ls_files:failed:{type(exc).__name__}")
        return errors
    for relative in tracked:
        normalized = relative.replace("\\", "/")
        if "backend/infra/nullbridge/" in normalized and NULLBRIDGE_RUNTIME_RE.search(normalized):
            errors.append(f"runtime_artifact_tracked:{normalized}")
    return errors


def subprocess_check_output(args: list[str], cwd: Path) -> str:
    import subprocess

    return subprocess.check_output(args, cwd=cwd, text=True)


def iter_source_files(root: Path):
    suffixes = {".js", ".jsx", ".ts", ".tsx", ".kt", ".cpp", ".h", ".hpp", ".py", ".json", ".md", ".yaml", ".yml"}
    ignored_parts = {".git", "node_modules", "dist", "build", ".gradle", "__pycache__"}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in ignored_parts for part in path.parts):
            continue
        if path.suffix.lower() in suffixes:
            yield path
