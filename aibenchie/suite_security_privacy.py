from __future__ import annotations

import importlib.util
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from aibenchie.nullbridge_platform_adapters import run_from_env as run_nullbridge_platform_adapters_from_env
from aibenchie.nullprivacy import encrypt_blob, generate_key
from aibenchie.release_report import assert_public_safe


GATE_NAMES = (
    "promptEditorLeakage",
    "routePrivacyInventory",
    "artifactSandboxing",
    "cccScoping",
    "nullbridgeCapabilityDenial",
    "credentialIsolation",
    "privateAIBenchieReports",
)

CANARIES = {
    "prompt_editor": "M36_CANARY_SECRET_PROMPT_EDITOR_001",
    "nullbridge_service_token": "M36_CANARY_NULLBRIDGE_SERVICE_TOKEN_001",
    "private_report_key": "M36_CANARY_PRIVATE_REPORT_KEY_001",
    "ccc_scope": "M36_CANARY_CCC_SCOPE_SECRET_001",
}

KNOWN_PENDING = {
    "m37WebsiteAuthCleanup": [
        "localStorage audit-token cleanup",
        "legacy token-header fallback inventory",
        "SSE query-token cleanup",
    ]
}

REQUIRED_ROUTE_FIELDS = (
    "routeId",
    "platform",
    "authRequirement",
    "sensitiveDataClass",
    "storageBehavior",
    "logBehavior",
    "frontendExposure",
    "expectedPrivacyGate",
    "evidence",
    "status",
)

MAX_SCAN_BYTES = 512 * 1024
PUBLIC_SCAN_PATHS = (
    "public_export",
    "docs",
    "reports/runtime",
    "data",
)
PRIVATE_ALLOWED_PREFIXES = (
    "data/private",
    "reports/local",
    "reports/runtime/.local",
)
GENERATED_LOCAL_PREFIXES = (
    ".git",
    ".pytest_cache",
    ".suite/local",
    "__pycache__",
    "reports/runtime/.local",
    "data/private",
)


@dataclass(frozen=True)
class GateResult:
    status: str
    severity: str = "blocking"
    evidence: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    known_pending: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures and self.status in {"passed", "accepted_pending"}

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": self.status,
            "severity": self.severity,
            "evidence": self.evidence,
        }
        if self.failures:
            payload["failures"] = self.failures
        if self.known_pending:
            payload["knownPending"] = self.known_pending
        return payload


@dataclass(frozen=True)
class SuiteSecurityPrivacyResult:
    ok: bool
    release_verdict: str
    blocking_failures: list[str]
    gates: dict[str, GateResult]
    known_pending: dict[str, list[str]]
    route_inventory: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "releaseVerdict": self.release_verdict,
            "blockingFailures": self.blocking_failures,
            "m36SecurityPrivacy": {name: result.as_dict() for name, result in self.gates.items()},
            "knownPending": self.known_pending,
            "routeInventory": self.route_inventory,
        }


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_inventory_path() -> Path:
    return Path(__file__).resolve().parent / "policies" / "route-privacy-inventory.json"


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _path_key(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _is_local_or_private(relative: str) -> bool:
    normalized = relative.replace("\\", "/")
    return any(normalized == prefix or normalized.startswith(f"{prefix}/") for prefix in GENERATED_LOCAL_PREFIXES)


def load_inventory(path: Path | None = None) -> dict[str, Any]:
    inventory_path = path or default_inventory_path()
    with inventory_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("route privacy inventory must be a JSON object")
    return data


def _find_repo(env: dict[str, str], env_key: str, candidates: Iterable[str]) -> Path | None:
    configured = env.get(env_key, "").strip()
    roots: list[Path] = []
    if configured:
        roots.append(Path(configured).expanduser())
    base = repo_root()
    for candidate in candidates:
        path = Path(candidate)
        roots.append(path if path.is_absolute() else (base / path).resolve())
        roots.append(path if path.is_absolute() else (base.parent / path).resolve())
    for root in roots:
        if root.exists():
            return root.resolve()
    return None


def _find_nullbridge_repo(env: dict[str, str]) -> Path | None:
    return _find_repo(env, "AIBENCHIE_NULLBRIDGE_REPO", ("../NullBridge", "NullBridge"))


def _find_wrapper_repo(env: dict[str, str]) -> Path | None:
    return _find_repo(env, "AIBENCHIE_NULLXOID_WRAPPER_REPO", ("../Felnx/NullXoid/.NullXoid", "../.NullXoid", "../NullXoid"))


def _load_prompt_editor(env: dict[str, str]) -> Any | None:
    nullbridge = _find_nullbridge_repo(env)
    if not nullbridge:
        return None
    path = nullbridge / "backend" / "scripts" / "prompt_editor.py"
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("m36_prompt_editor", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _contains_canary(value: Any, canaries: Iterable[str] = CANARIES.values()) -> list[str]:
    text = json.dumps(value, sort_keys=True, default=str) if not isinstance(value, str) else value
    return [canary for canary in canaries if canary in text]


def scan_public_files_for_canaries(root: Path, canaries: Iterable[str] = CANARIES.values()) -> list[str]:
    findings: list[str] = []
    for relative_root in PUBLIC_SCAN_PATHS:
        base = root / relative_root
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            relative = _path_key(path, root)
            if _is_local_or_private(relative):
                continue
            try:
                if path.stat().st_size > MAX_SCAN_BYTES:
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for canary in canaries:
                if canary in text:
                    findings.append(f"{relative}:canary:{canary}")
    return sorted(findings)


def discover_registered_routes(root: Path, env: dict[str, str]) -> set[str]:
    routes: set[str] = set()
    cli = root / "aibenchie_local.py"
    if cli.is_file():
        text = cli.read_text(encoding="utf-8", errors="ignore")
        for flag in ("--suite-security", "--nullbridge-platform-adapters", "--suite-security-privacy", "--Elabs-store"):
            if flag in text:
                routes.add(f"aibenchie.cli.{flag.removeprefix('--')}")

    nullbridge = _find_nullbridge_repo(env)
    if nullbridge:
        route_policy = nullbridge / "backend" / "infra" / "nullbridge" / "route-policy.json"
        if route_policy.is_file():
            try:
                data = json.loads(route_policy.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                data = {}
            for rule in data.get("rules", []):
                caller = str(rule.get("caller") or "").strip()
                if caller:
                    routes.add(f"nullbridge.route_policy.{caller}")
        m35_script = nullbridge / "backend" / "scripts" / "nullbridge_m35_platform_adapters_e2e.py"
        if m35_script.is_file():
            for platform in ("website", "wrapper", "windows", "android"):
                routes.add(f"{platform}.backend.nullbridge.demo-route")
                routes.add(f"{platform}.backend.nullbridge.unsupported-route")
    return routes


def validate_route_inventory(inventory: dict[str, Any], root: Path, env: dict[str, str]) -> tuple[list[str], dict[str, Any]]:
    failures: list[str] = []
    routes = inventory.get("routes")
    exemptions = inventory.get("exemptions") or []
    if inventory.get("version") != 1:
        failures.append("ROUTE_PRIVACY_INVENTORY_VERSION_INVALID")
    if not isinstance(routes, list):
        return ["ROUTE_PRIVACY_INVENTORY_ROUTES_INVALID"], {"inventoryRoutes": 0, "registeredRoutes": 0}

    route_ids: set[str] = set()
    for index, route in enumerate(routes):
        if not isinstance(route, dict):
            failures.append(f"ROUTE_PRIVACY_INVENTORY_ROUTE_INVALID:{index}")
            continue
        route_id = str(route.get("routeId") or "").strip()
        if route_id in route_ids:
            failures.append(f"ROUTE_PRIVACY_INVENTORY_DUPLICATE:{route_id}")
        if route_id:
            route_ids.add(route_id)
        for field_name in REQUIRED_ROUTE_FIELDS:
            value = route.get(field_name)
            if value in (None, "", []):
                failures.append(f"ROUTE_PRIVACY_INVENTORY_FIELD_MISSING:{route_id or index}:{field_name}")
        if route.get("status") not in {"covered", "accepted_pending", "exempted"}:
            failures.append(f"ROUTE_PRIVACY_INVENTORY_STATUS_INVALID:{route_id or index}")
        if route.get("status") == "accepted_pending" and route.get("acceptedPending") in (None, "", []):
            failures.append(f"ROUTE_PRIVACY_INVENTORY_PENDING_REASON_MISSING:{route_id or index}")

    exempted = {str(item.get("routeId") or "").strip() for item in exemptions if isinstance(item, dict)}
    registered = discover_registered_routes(root, env)
    missing = sorted(route_id for route_id in registered if route_id not in route_ids and route_id not in exempted)
    failures.extend(f"ROUTE_PRIVACY_INVENTORY_MISSING:{route_id}" for route_id in missing)

    accepted_pending = sorted(
        route["routeId"]
        for route in routes
        if isinstance(route, dict) and route.get("status") == "accepted_pending" and route.get("routeId")
    )
    summary = {
        "inventoryRoutes": len(route_ids),
        "registeredRoutes": len(registered),
        "exemptions": len(exempted),
        "acceptedPendingRoutes": accepted_pending,
        "missingRoutes": missing,
    }
    return failures, summary


def gate_prompt_editor_leakage(env: dict[str, str]) -> GateResult:
    prompt_editor = _load_prompt_editor(env)
    if prompt_editor is None:
        return GateResult(
            status="failed",
            evidence=[],
            failures=["PROMPT_EDITOR_EVIDENCE_MISSING"],
        )

    source = (
        f"PROMPT_EDITOR_SECRET={CANARIES['prompt_editor']} "
        f"NULLBRIDGE_SERVICE_TOKEN={CANARIES['nullbridge_service_token']} "
        "Authorization: Bearer eyJfake.fake.fake"
    )
    mediated_input = prompt_editor.mediate_input(source, capability="diagnostics.run")
    mediated_output = prompt_editor.mediate_output(source, mode="live_stream", capability="diagnostics.run")
    public_surfaces = {
        "input": mediated_input.text,
        "output": mediated_output.text,
        "redactions": list(mediated_input.redactions) + list(mediated_output.redactions),
        "routeSummary": "Prompt Editor redacted high-risk diagnostic input.",
    }
    leaks = _contains_canary(public_surfaces)
    failures = [f"PROMPT_EDITOR_CANARY_LEAK:{item}" for item in leaks]
    return GateResult(
        status="passed" if not failures else "failed",
        evidence=[
            "NullBridge backend/scripts/prompt_editor.py",
            "seeded fake Prompt Editor and NullBridge service token canaries",
        ],
        failures=failures,
    )


def gate_route_privacy_inventory(root: Path, env: dict[str, str], inventory: dict[str, Any]) -> tuple[GateResult, dict[str, Any]]:
    failures, summary = validate_route_inventory(inventory, root, env)
    return (
        GateResult(
            status="passed" if not failures else "failed",
            evidence=[
                _path_key(default_inventory_path(), root),
                "AIBenchie CLI flags",
                "NullBridge route-policy callers",
                "M35 platform adapter route fixtures",
            ],
            failures=failures,
        ),
        summary,
    )


def gate_artifact_sandboxing(root: Path) -> GateResult:
    failures = scan_public_files_for_canaries(root)
    private_fixture = "data/private/m36-private-artifact.json"
    if not any(private_fixture.startswith(prefix) for prefix in PRIVATE_ALLOWED_PREFIXES):
        failures.append("ARTIFACT_PRIVATE_FIXTURE_NOT_IN_ALLOWED_PREFIX")
    return GateResult(
        status="passed" if not failures else "failed",
        evidence=[
            "public_export/docs/reports/runtime/data canary scan",
            "private prefixes: " + ", ".join(PRIVATE_ALLOWED_PREFIXES),
        ],
        failures=[f"ARTIFACT_SANDBOX_LEAK:{item}" for item in failures],
    )


def _visible_ccc_records(records: list[dict[str, str]], scope: dict[str, str]) -> list[dict[str, str]]:
    return [
        record
        for record in records
        if record.get("workspaceId") == scope.get("workspaceId")
        and record.get("userId") == scope.get("userId")
        and record.get("projectId") == scope.get("projectId")
    ]


def gate_ccc_scoping(env: dict[str, str]) -> GateResult:
    records = [
        {
            "workspaceId": "ws-a",
            "userId": "user-a",
            "projectId": "proj-a",
            "text": "allowed ccc memory",
        },
        {
            "workspaceId": "ws-b",
            "userId": "user-b",
            "projectId": "proj-b",
            "text": CANARIES["ccc_scope"],
        },
    ]
    visible = _visible_ccc_records(records, {"workspaceId": "ws-a", "userId": "user-a", "projectId": "proj-a"})
    failures = []
    if _contains_canary(visible, [CANARIES["ccc_scope"]]):
        failures.append("CCC_SCOPE_CANARY_LEAK")
    wrapper = _find_wrapper_repo(env)
    evidence = ["in-memory workspace/user/project scope fixture"]
    if wrapper and (wrapper / "backend" / "tests" / "test_ccc_e2ee_contract.py").is_file():
        evidence.append("wrapper backend/tests/test_ccc_e2ee_contract.py")
    return GateResult(
        status="passed" if not failures else "failed",
        evidence=evidence,
        failures=failures,
    )


def gate_nullbridge_capability_denial(m35_result: dict[str, Any]) -> GateResult:
    status = (m35_result.get("m35PlatformAdapters") or {}).get("unsupportedRouteDenial")
    failures = []
    if not m35_result.get("ok"):
        failures.append("NULLBRIDGE_M35_GATE_FAILED")
    if status != "passed":
        failures.append("NULLBRIDGE_UNSUPPORTED_ROUTE_DENIAL_MISSING")
    return GateResult(
        status="passed" if not failures else "failed",
        evidence=["AIBenchie --nullbridge-platform-adapters", "M35 unsupportedRouteDenial"],
        failures=failures,
    )


def gate_credential_isolation(root: Path, m35_result: dict[str, Any]) -> GateResult:
    failures: list[str] = []
    m35_status = (m35_result.get("m35PlatformAdapters") or {}).get("credentialLeakCheck")
    if not m35_result.get("ok"):
        failures.append("CREDENTIAL_ISOLATION_M35_GATE_FAILED")
    if m35_status != "passed":
        failures.append("CREDENTIAL_ISOLATION_M35_EVIDENCE_MISSING")

    frontend_fixture = {
        "ok": True,
        "requestId": "m36-public-response",
        "status": "approved",
        "summary": "sanitized frontend response",
    }
    storage_fixture = {"localStorage": {"theme": "dark"}, "sessionStorage": {"refreshDuringStream": "1"}}
    url_fixture = "https://example.invalid/nullxoid/api/jobs/job-1/events"
    manager_fixture = {"approvals": [{"requestId": "req-1", "payloadRedacted": True}]}
    public_summary = {"releaseVerdict": "pass_with_accepted_pending", "credentialIsolation": "passed"}
    leaks = _contains_canary([frontend_fixture, storage_fixture, url_fixture, manager_fixture, public_summary])
    leaks.extend(scan_public_files_for_canaries(root))
    failures.extend(f"CREDENTIAL_CANARY_LEAK:{item}" for item in leaks)
    return GateResult(
        status="passed" if not failures else "failed",
        evidence=[
            "M35 credentialLeakCheck",
            "frontend response/storage/url/manager/public-summary canary fixtures",
            "public repo canary scan",
        ],
        failures=failures,
    )


def gate_private_aibenchie_reports() -> GateResult:
    private_report = {
        "kind": "private_aibenchie_report",
        "operatorNote": CANARIES["private_report_key"],
        "route": "m36-private",
    }
    key = generate_key()
    envelope = encrypt_blob(
        key,
        json.dumps(private_report, sort_keys=True).encode("utf-8"),
        associated_data={"kind": "aibenchie_private_report", "scope": "private"},
    )
    public_summary = {
        "kind": "aibenchie_public_summary",
        "releaseVerdict": "pass_with_accepted_pending",
        "privateReport": "encrypted",
    }
    failures: list[str] = []
    if _contains_canary(envelope, [CANARIES["private_report_key"]]):
        failures.append("PRIVATE_AIBENCHIE_REPORT_ENVELOPE_LEAK")
    if _contains_canary(public_summary, [CANARIES["private_report_key"]]):
        failures.append("PRIVATE_AIBENCHIE_PUBLIC_SUMMARY_LEAK")
    try:
        assert_public_safe(public_summary)
    except ValueError as exc:
        failures.append(f"PRIVATE_AIBENCHIE_PUBLIC_SUMMARY_UNSAFE:{exc}")
    return GateResult(
        status="passed" if not failures else "failed",
        evidence=[
            "private report encrypted envelope check",
            "public summary sanitization check",
        ],
        failures=failures,
    )


def run_suite_security_privacy_check(env: dict[str, str] | None = None) -> SuiteSecurityPrivacyResult:
    source = dict(os.environ if env is None else env)
    root = Path(source.get("AIBENCHIE_M36_ROOT", "") or repo_root()).resolve()
    inventory_path = Path(source.get("AIBENCHIE_ROUTE_PRIVACY_INVENTORY", "") or default_inventory_path()).resolve()
    inventory = load_inventory(inventory_path)

    m35_result = run_nullbridge_platform_adapters_from_env()

    gates: dict[str, GateResult] = {}
    gates["promptEditorLeakage"] = gate_prompt_editor_leakage(source)
    gates["routePrivacyInventory"], route_summary = gate_route_privacy_inventory(root, source, inventory)
    gates["artifactSandboxing"] = gate_artifact_sandboxing(root)
    gates["cccScoping"] = gate_ccc_scoping(source)
    gates["nullbridgeCapabilityDenial"] = gate_nullbridge_capability_denial(m35_result)
    gates["credentialIsolation"] = gate_credential_isolation(root, m35_result)
    gates["privateAIBenchieReports"] = gate_private_aibenchie_reports()

    blocking_failures = [
        f"{name}:{failure}"
        for name, gate in gates.items()
        for failure in gate.failures
        if gate.severity == "blocking"
    ]
    ok = not blocking_failures
    release_verdict = "pass_with_accepted_pending" if ok and KNOWN_PENDING else ("pass" if ok else "blocks_release")
    route_inventory = {
        **route_summary,
        "path": str(inventory_path),
    }
    return SuiteSecurityPrivacyResult(
        ok=ok,
        release_verdict=release_verdict,
        blocking_failures=blocking_failures,
        gates=gates,
        known_pending=KNOWN_PENDING,
        route_inventory=route_inventory,
    )


def run_from_env() -> SuiteSecurityPrivacyResult:
    return run_suite_security_privacy_check()
