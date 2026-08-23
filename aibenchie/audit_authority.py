from __future__ import annotations

import argparse
import ast
import hashlib
import hmac
import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


CATALOG_SCHEMA = "aibenchie.audit-catalog.v1"
RESULT_SCHEMA = "aibenchie.audit-result.v1"
EVIDENCE_SCHEMA = "aibenchie.audit-evidence.v1"
MANIFEST_SCHEMA = "aibenchie.audit-manifest.v1"
LATEST_SCHEMA = "aibenchie.audit-latest.v1"
SCHEMA_VERSION = "1.0"
DEFAULT_CATALOG_PATH = Path("configs/audit_catalog.json")
DEFAULT_RESULT_ROOT = Path(".suite/local/aibenchie/audits")
AUDIT_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_.-]{2,95}$")
COMMIT_PATTERN = re.compile(r"\b[0-9a-fA-F]{7,40}\b")
DATE_PATTERNS = (
    re.compile(r"(?im)^\s*(?:audit date|last updated)\s*:\s*(\d{4}-\d{2}-\d{2})"),
    re.compile(r"(?im)^\s*[-*]\s*Audit date\s*:\s*(\d{4}-\d{2}-\d{2})"),
)
SEVERITIES = {"info", "low", "medium", "high", "critical"}
PUBLIC_FINDING_KEYS = {"code", "severity", "message", "subject", "recommended_action"}


class AuditContractError(ValueError):
    """Raised when catalog or result data violates the public contract."""


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_relative_path(root: Path, value: str | Path) -> Path:
    candidate = (root / value).resolve() if not Path(value).is_absolute() else Path(value).resolve()
    resolved_root = root.resolve()
    if candidate != resolved_root and resolved_root not in candidate.parents:
        raise AuditContractError("path_outside_audit_root")
    return candidate


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def load_catalog(path: str | Path | None = None) -> dict[str, Any]:
    resolved = Path(path) if path else repo_root() / DEFAULT_CATALOG_PATH
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuditContractError(f"catalog_unavailable:{exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema") != CATALOG_SCHEMA:
        raise AuditContractError("catalog_schema_invalid")
    audits = payload.get("audits")
    if not isinstance(audits, list) or not audits:
        raise AuditContractError("catalog_audits_missing")
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for raw in audits:
        if not isinstance(raw, dict):
            raise AuditContractError("catalog_audit_invalid")
        audit_id = str(raw.get("id") or "").strip()
        if not AUDIT_ID_PATTERN.fullmatch(audit_id):
            raise AuditContractError(f"catalog_audit_id_invalid:{audit_id}")
        if audit_id in seen:
            raise AuditContractError(f"catalog_audit_id_duplicate:{audit_id}")
        seen.add(audit_id)
        runner = str(raw.get("runner") or "").strip()
        if runner not in {"audit_freshness", "runtime_processes", "repository_health"}:
            raise AuditContractError(f"catalog_runner_invalid:{audit_id}")
        ttl = int(raw.get("default_ttl_seconds") or 0)
        timeout = int(raw.get("timeout_seconds") or 0)
        if ttl < 60 or ttl > 31_536_000:
            raise AuditContractError(f"catalog_ttl_invalid:{audit_id}")
        if timeout < 1 or timeout > 3600:
            raise AuditContractError(f"catalog_timeout_invalid:{audit_id}")
        normalized.append(
            {
                **raw,
                "id": audit_id,
                "version": str(raw.get("version") or "1.0.0"),
                "title": str(raw.get("title") or audit_id),
                "description": str(raw.get("description") or ""),
                "owner": str(raw.get("owner") or "AIBenchie"),
                "component": str(raw.get("component") or ""),
                "scope": str(raw.get("scope") or "repository"),
                "runner": runner,
                "mutates_target": bool(raw.get("mutates_target", False)),
                "release_blocking": bool(raw.get("release_blocking", False)),
                "default_ttl_seconds": ttl,
                "timeout_seconds": timeout,
            }
        )
    return {
        "schema": CATALOG_SCHEMA,
        "schema_version": str(payload.get("schema_version") or SCHEMA_VERSION),
        "catalog_version": str(payload.get("catalog_version") or "1.0.0"),
        "audits": normalized,
    }


def public_catalog(payload: Mapping[str, Any]) -> dict[str, Any]:
    public_keys = {
        "id",
        "version",
        "title",
        "description",
        "owner",
        "component",
        "scope",
        "mutates_target",
        "release_blocking",
        "default_ttl_seconds",
    }
    return {
        "schema": CATALOG_SCHEMA,
        "schema_version": str(payload.get("schema_version") or SCHEMA_VERSION),
        "catalog_version": str(payload.get("catalog_version") or "unknown"),
        "audits": [
            {key: value for key, value in item.items() if key in public_keys}
            for item in payload.get("audits", [])
            if isinstance(item, dict)
        ],
    }


def _git_output(root: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            check=False,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return completed.stdout.strip() if completed.returncode == 0 else ""


def target_identity(root: Path, label: str = "NullXoid") -> dict[str, Any]:
    resolved = root.resolve()
    head = _git_output(resolved, "rev-parse", "HEAD")
    status = _git_output(resolved, "status", "--porcelain")
    return {
        "label": label,
        "source_commit": head if COMMIT_PATTERN.fullmatch(head or "") else "unknown",
        "working_tree_dirty": bool(status),
    }


def _finding(
    code: str,
    severity: str,
    message: str,
    *,
    subject: str = "",
    recommended_action: str = "",
) -> dict[str, str]:
    normalized = severity if severity in SEVERITIES else "medium"
    payload = {"code": code, "severity": normalized, "message": message}
    if subject:
        payload["subject"] = subject.replace("\\", "/")
    if recommended_action:
        payload["recommended_action"] = recommended_action
    return payload


def _audit_document_paths(root: Path) -> list[Path]:
    candidates: set[Path] = set()
    docs = root / "docs"
    if docs.is_dir():
        candidates.update(path for path in docs.glob("*AUDIT*.md") if path.is_file())
        for name in ("BACKEND_FEATURE_MATRIX.md", "WORKFLOW_VALIDATION.md", "REPAIR_TODO.md"):
            path = docs / name
            if path.is_file():
                candidates.add(path)
    for name in ("ADMIN_AUDIT_NOTES.md",):
        path = root / name
        if path.is_file():
            candidates.add(path)
    return sorted(candidates)


def _document_date(text: str) -> datetime | None:
    for pattern in DATE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        try:
            return datetime.strptime(match.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _baseline_commit(text: str) -> str:
    for line in text.splitlines()[:40]:
        lowered = line.lower()
        if not any(marker in lowered for marker in ("baseline", "frozen at commit", "source commit")):
            continue
        match = COMMIT_PATTERN.search(line)
        if match:
            return match.group(0).lower()
    return ""


def _path_is_dirty(root: Path, path: Path) -> bool:
    try:
        relative = path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return False
    return bool(_git_output(root, "status", "--porcelain", "--", relative))


def _repo_audit_contract_findings(root: Path) -> list[dict[str, str]]:
    path = root / "backend" / "repo_audit.py"
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    findings: list[dict[str, str]] = []
    if "Path(__file__).resolve().parents[2]" in text:
        findings.append(
            _finding(
                "repo_audit.root_outside_repository",
                "high",
                "The repository audit resolves its root above the target repository.",
                subject="backend/repo_audit.py",
                recommended_action="Resolve the audit root to the repository containing backend/repo_audit.py.",
            )
        )
    match = re.search(r"DEFAULT_ALLOWLIST\s*=\s*(\[[^\n]+\])", text)
    if match:
        try:
            entries = ast.literal_eval(match.group(1))
        except (SyntaxError, ValueError):
            entries = []
        missing = [str(item) for item in entries if not (root / str(item)).exists()]
        if missing:
            findings.append(
                _finding(
                    "repo_audit.allowlist_missing",
                    "high",
                    f"The default repository audit allowlist contains {len(missing)} missing targets.",
                    subject="backend/repo_audit.py",
                    recommended_action="Use repository-relative targets that exist and reject missing allowlist entries.",
                )
            )
    existence_guard = re.search(r"if\s+[^\n:]*not\s+root\.exists\(\)", text)
    if "keep only existing" in text and not existence_guard:
        findings.append(
            _finding(
                "repo_audit.existence_contract_mismatch",
                "medium",
                "The allowlist normalization comment promises existence filtering but the implementation does not enforce it.",
                subject="backend/repo_audit.py",
                recommended_action="Filter missing allowlist roots before path authorization.",
            )
        )
    return findings


def run_audit_freshness(
    target_root: str | Path,
    *,
    now: datetime | None = None,
    max_current_age_days: int = 7,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    root = Path(target_root).resolve()
    if not root.is_dir():
        raise AuditContractError("target_repository_missing")
    moment = (now or _utc_now()).astimezone(timezone.utc)
    identity = target_identity(root)
    findings: list[dict[str, str]] = []
    documents: list[dict[str, Any]] = []
    for path in _audit_document_paths(root):
        relative = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        header = "\n".join(text.splitlines()[:12]).lower()
        historical = "> **historical" in header or "> **dated" in header
        frozen = historical and "frozen" in header
        claims_current = bool(re.search(r"(?i)\bcurrent\b", text[:5000])) and not historical
        recorded = _document_date(text)
        baseline = _baseline_commit(text)
        dirty = _path_is_dirty(root, path)
        age_days = (moment - recorded).total_seconds() / 86400 if recorded else None
        documents.append(
            {
                "path": relative,
                "historical": historical,
                "claims_current": claims_current,
                "recorded_date": _iso(recorded) if recorded else None,
                "age_days": round(age_days, 2) if age_days is not None else None,
                "baseline_commit": baseline or None,
                "working_tree_modified": dirty,
            }
        )
        if claims_current and recorded and age_days is not None and age_days > max_current_age_days:
            findings.append(
                _finding(
                    "audit_document.current_claim_expired",
                    "high",
                    f"A document claiming current authority is {int(age_days)} days old.",
                    subject=relative,
                    recommended_action="Generate a fresh result or label the document historical.",
                )
            )
        if frozen and dirty:
            findings.append(
                _finding(
                    "audit_document.frozen_baseline_modified",
                    "high",
                    "A frozen historical audit has current working-tree modifications.",
                    subject=relative,
                    recommended_action="Restore the frozen snapshot or move current evidence to a new result.",
                )
            )
        if claims_current and baseline and identity["source_commit"] != "unknown":
            if not identity["source_commit"].lower().startswith(baseline):
                findings.append(
                    _finding(
                        "audit_document.source_commit_mismatch",
                        "medium",
                        "The document's source baseline does not match the current repository commit.",
                        subject=relative,
                        recommended_action="Regenerate against the current commit or mark the result historical.",
                    )
                )
    findings.extend(_repo_audit_contract_findings(root))
    ui_candidates = root / "docs" / "UI_SURFACING_CANDIDATES.md"
    registry = root / "backend" / "workflow_registry.py"
    if ui_candidates.is_file() and registry.is_file():
        text = ui_candidates.read_text(encoding="utf-8", errors="replace")
        if "no dedicated backend readiness contract" in text.lower():
            findings.append(
                _finding(
                    "audit_document.workflow_readiness_claim_stale",
                    "medium",
                    "The UI audit says no workflow readiness contract exists although the workflow registry is present.",
                    subject="docs/UI_SURFACING_CANDIDATES.md",
                    recommended_action="Generate this view from the current workflow registry evidence.",
                )
            )
    if identity["working_tree_dirty"]:
        findings.append(
            _finding(
                "target.working_tree_dirty",
                "low",
                "The target repository has uncommitted changes; this result is local evidence, not release proof.",
                subject=identity["label"],
            )
        )
    return findings, {"target": identity, "documents": documents}


def _default_process_snapshot() -> dict[str, Any]:
    try:
        import psutil  # type: ignore
    except ImportError:
        return {"available": False, "error": "psutil_unavailable", "listeners": {}, "tunnels": []}
    listeners: dict[int, dict[str, Any]] = {}
    try:
        connections = psutil.net_connections(kind="inet")
    except (OSError, psutil.Error):
        connections = []
    for connection in connections:
        if connection.status != psutil.CONN_LISTEN or not connection.laddr:
            continue
        port = int(connection.laddr.port)
        pid = int(connection.pid or 0)
        process_name = "unknown"
        command = ""
        created = None
        if pid:
            try:
                process = psutil.Process(pid)
                process_name = process.name()
                command = " ".join(process.cmdline())
                created = float(process.create_time())
            except (OSError, psutil.Error):
                pass
        listeners[port] = {
            "pid": pid,
            "process_name": process_name,
            "command": command,
            "created_at_epoch": created,
        }
    tunnels: list[str] = []
    try:
        processes = psutil.process_iter(["name", "cmdline"])
    except (OSError, psutil.Error):
        processes = []
    for process in processes:
        try:
            name = str(process.info.get("name") or "").lower()
            command = " ".join(process.info.get("cmdline") or [])
        except (OSError, psutil.Error):
            continue
        if name in {"ssh", "ssh.exe"} and " -R " in f" {command} ":
            tunnels.append(command)
    return {"available": True, "listeners": listeners, "tunnels": tunnels}


def _probe_comfyui(port: int, timeout: float = 2.0) -> dict[str, Any]:
    base = f"http://127.0.0.1:{port}"
    try:
        with urlopen(Request(f"{base}/system_stats", headers={"Accept": "application/json"}), timeout=timeout) as response:
            stats = json.loads(response.read().decode("utf-8"))
        with urlopen(Request(f"{base}/queue", headers={"Accept": "application/json"}), timeout=timeout) as response:
            queue = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {"healthy": False, "running": 0, "pending": 0, "version": "unknown"}
    system = stats.get("system") if isinstance(stats, dict) else {}
    return {
        "healthy": True,
        "running": len(queue.get("queue_running") or []) if isinstance(queue, dict) else 0,
        "pending": len(queue.get("queue_pending") or []) if isinstance(queue, dict) else 0,
        "version": str((system or {}).get("comfyui_version") or "unknown"),
    }


def run_runtime_processes(
    config: Mapping[str, Any],
    *,
    snapshot: Mapping[str, Any] | None = None,
    health_probe: Callable[[int], Mapping[str, Any]] | None = None,
    now: datetime | None = None,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    runtime_items = config.get("runtimes")
    if not isinstance(runtime_items, list):
        raise AuditContractError("runtime_config_missing")
    moment = (now or _utc_now()).astimezone(timezone.utc)
    observed = dict(snapshot or _default_process_snapshot())
    listeners = observed.get("listeners") if isinstance(observed.get("listeners"), dict) else {}
    tunnels = observed.get("tunnels") if isinstance(observed.get("tunnels"), list) else []
    probe = health_probe or _probe_comfyui
    findings: list[dict[str, str]] = []
    runtimes: list[dict[str, Any]] = []
    if not observed.get("available", False):
        findings.append(
            _finding(
                "runtime.collector_unavailable",
                "high",
                "The process inventory collector is unavailable.",
                recommended_action="Install the bounded process collector dependency on the AIBenchie runner.",
            )
        )
    for item in runtime_items:
        if not isinstance(item, dict):
            continue
        runtime_id = str(item.get("id") or "").strip()
        port = int(item.get("port") or 0)
        desired = str(item.get("desired_state") or "running").strip().lower()
        listener = listeners.get(port) or listeners.get(str(port))
        command = str((listener or {}).get("command") or "")
        markers = [str(marker) for marker in item.get("command_markers") or [] if str(marker)]
        marker_match = bool(listener) and all(marker.lower() in command.lower() for marker in markers)
        health = dict(probe(port)) if listener and item.get("health_contract") == "comfyui" else {}
        tunnel_match = any(f":{port}:" in str(command_line) for command_line in tunnels)
        classification = "unknown_owner"
        severity = "medium"
        recommended = "Review the listener ownership and expected runtime configuration."
        if desired == "retired":
            if listener:
                classification = "probable_orphan"
                severity = "high"
                recommended = "Request explicit administrator confirmation before stopping this retired listener."
            else:
                classification = "expected_stopped"
                severity = "info"
                recommended = ""
        elif not listener:
            classification = "unhealthy"
            severity = "high"
            recommended = "Start or repair the expected runtime using its approved launcher."
        elif markers and not marker_match:
            classification = "misconfigured"
            severity = "high"
            recommended = "Verify the process identity before routing work to this port."
        elif health and not health.get("healthy", False):
            classification = "unhealthy"
            severity = "high"
            recommended = "Repair the runtime health contract before use."
        elif bool(item.get("tunnel_required")) and not tunnel_match:
            classification = "misconfigured"
            severity = "high"
            recommended = "Restore the approved loopback tunnel before hosted use."
        elif int(health.get("running") or 0) or int(health.get("pending") or 0):
            classification = "expected_active"
            severity = "info"
            recommended = ""
        else:
            classification = "expected_idle"
            severity = "info"
            recommended = ""
        created_epoch = (listener or {}).get("created_at_epoch")
        age_hours = None
        if isinstance(created_epoch, (int, float)):
            age_hours = round(max(0.0, moment.timestamp() - float(created_epoch)) / 3600, 1)
        pid = int((listener or {}).get("pid") or 0)
        runtime = {
            "id": runtime_id,
            "port": port,
            "desired_state": desired,
            "classification": classification,
            "pid": pid or None,
            "process_name": str((listener or {}).get("process_name") or "unknown") if listener else None,
            "process_age_hours": age_hours,
            "command_fingerprint": _sha256_bytes(command.encode("utf-8")) if command else None,
            "identity_markers_match": marker_match,
            "tunnel_present": tunnel_match,
            "healthy": bool(health.get("healthy")) if health else None,
            "queue_running": int(health.get("running") or 0),
            "queue_pending": int(health.get("pending") or 0),
            "runtime_version": str(health.get("version") or "unknown") if health else None,
        }
        runtimes.append(runtime)
        if severity != "info":
            findings.append(
                _finding(
                    f"runtime.{classification}",
                    severity,
                    f"{runtime_id} on port {port} is classified as {classification.replace('_', ' ')}.",
                    subject=runtime_id,
                    recommended_action=recommended,
                )
            )
    return findings, {"collector_available": bool(observed.get("available")), "runtimes": runtimes}


def _verdict_for(findings: Iterable[Mapping[str, Any]]) -> str:
    severities = {str(item.get("severity") or "") for item in findings}
    if severities & {"critical", "high"}:
        return "blocked"
    if severities & {"medium", "low"}:
        return "warn"
    return "pass"


def _counts(findings: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counter = Counter(str(item.get("severity") or "info") for item in findings)
    return {severity: int(counter.get(severity, 0)) for severity in ("critical", "high", "medium", "low", "info")}


def run_repository_health(
    target_root: str | Path,
    *,
    health_builder: Callable[[Path], Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if health_builder is None:
        from aibenchie.gui_health import build_repository_health

        health_builder = build_repository_health
    health = health_builder(Path(target_root))
    payload = health.as_dict() if hasattr(health, "as_dict") else dict(health)
    findings: list[dict[str, Any]] = []
    for index, message in enumerate(payload.get("blockers") or [], start=1):
        findings.append(
            _finding(
                f"repository.health.blocker.{index}",
                "high",
                str(message),
                subject="AIBenchie",
                recommended_action="Resolve the live blocker and rerun this self-audit before release.",
            )
        )
    for index, message in enumerate(payload.get("warnings") or [], start=1):
        findings.append(
            _finding(
                f"repository.health.warning.{index}",
                "low",
                str(message),
                subject="AIBenchie",
                recommended_action="Review the warning before promotion.",
            )
        )
    evidence = {
        key: payload.get(key)
        for key in (
            "generated_at",
            "collected_tests",
            "collection_ok",
            "release_status",
            "release_ok",
            "generated_output_ok",
            "distribution_ok",
            "distribution_files_scanned",
            "critical_blockers",
            "publish_mode",
        )
    }
    return findings, evidence


def execute_audit(
    audit_id: str,
    *,
    target_root: str | Path,
    catalog_path: str | Path | None = None,
    now: datetime | None = None,
    process_snapshot: Mapping[str, Any] | None = None,
    health_probe: Callable[[int], Mapping[str, Any]] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    catalog = load_catalog(catalog_path)
    definition = next((item for item in catalog["audits"] if item["id"] == audit_id), None)
    if not definition:
        raise AuditContractError("audit_not_found")
    if definition["mutates_target"]:
        raise AuditContractError("mutating_audit_not_supported")
    moment = (now or _utc_now()).astimezone(timezone.utc)
    target = target_identity(Path(target_root), label=definition["component"] or "Unknown")
    if definition["runner"] == "audit_freshness":
        findings, evidence_body = run_audit_freshness(target_root, now=moment)
    elif definition["runner"] == "runtime_processes":
        findings, evidence_body = run_runtime_processes(
            definition.get("config") or {}, snapshot=process_snapshot, health_probe=health_probe, now=moment
        )
    elif definition["runner"] == "repository_health":
        findings, evidence_body = run_repository_health(target_root)
    else:
        raise AuditContractError("audit_runner_not_supported")
    expires = moment + timedelta(seconds=int(definition["default_ttl_seconds"]))
    verdict = _verdict_for(findings)
    result = {
        "schema": RESULT_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "audit_id": audit_id,
        "audit_version": definition["version"],
        "catalog_version": catalog["catalog_version"],
        "title": definition["title"],
        "component": definition["component"],
        "scope": definition["scope"],
        "mutates_target": False,
        "release_blocking": definition["release_blocking"],
        "generated_at": _iso(moment),
        "expires_at": _iso(expires),
        "verdict": verdict,
        "target": target,
        "summary": {"finding_count": len(findings), "counts": _counts(findings)},
        "findings": findings,
    }
    evidence = {
        "schema": EVIDENCE_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "audit_id": audit_id,
        "generated_at": _iso(moment),
        "target": target,
        "evidence": evidence_body,
    }
    return result, evidence


def write_immutable_result(
    result: Mapping[str, Any],
    evidence: Mapping[str, Any],
    *,
    result_root: str | Path | None = None,
    run_id: str | None = None,
    signing_key: str | bytes | None = None,
    signing_key_id: str = "",
) -> dict[str, Any]:
    audit_id = str(result.get("audit_id") or "")
    if not AUDIT_ID_PATTERN.fullmatch(audit_id):
        raise AuditContractError("result_audit_id_invalid")
    generated = _parse_datetime(result.get("generated_at"))
    if generated is None:
        raise AuditContractError("result_generated_at_invalid")
    actual_run_id = run_id or f"{generated.strftime('%Y%m%dT%H%M%SZ')}-{secrets.token_hex(4)}"
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{5,95}", actual_run_id):
        raise AuditContractError("result_run_id_invalid")
    root = Path(result_root) if result_root else repo_root() / DEFAULT_RESULT_ROOT
    audit_root = _safe_relative_path(root.resolve(), audit_id)
    run_root = _safe_relative_path(audit_root, actual_run_id)
    if run_root.exists():
        raise AuditContractError("immutable_result_exists")
    run_root.mkdir(parents=True, exist_ok=False)
    result_payload = {**result, "run_id": actual_run_id}
    evidence_payload = {**evidence, "run_id": actual_run_id}
    result_path = run_root / "result.json"
    evidence_path = run_root / "evidence.json"
    _atomic_write_json(result_path, result_payload)
    _atomic_write_json(evidence_path, evidence_payload)
    manifest_body: dict[str, Any] = {
        "schema": MANIFEST_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "audit_id": audit_id,
        "run_id": actual_run_id,
        "generated_at": result_payload["generated_at"],
        "files": {
            "result.json": _sha256_file(result_path),
            "evidence.json": _sha256_file(evidence_path),
        },
        "integrity": "hash_only",
    }
    if signing_key:
        key_bytes = signing_key.encode("utf-8") if isinstance(signing_key, str) else signing_key
        manifest_body["integrity"] = "hmac_sha256"
        signature = hmac.new(key_bytes, _json_bytes(manifest_body), hashlib.sha256).hexdigest()
        manifest_body["signature"] = {
            "algorithm": "hmac-sha256",
            "key_id": signing_key_id or "runtime-audit-key",
            "value": signature,
        }
    manifest_path = run_root / "manifest.json"
    _atomic_write_json(manifest_path, manifest_body)
    pointer = {
        "schema": LATEST_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "audit_id": audit_id,
        "run_id": actual_run_id,
        "generated_at": result_payload["generated_at"],
        "expires_at": result_payload["expires_at"],
        "verdict": result_payload["verdict"],
        "manifest_sha256": _sha256_file(manifest_path),
    }
    _atomic_write_json(audit_root / "latest.json", pointer)
    return {"run_id": actual_run_id, "result": result_payload, "manifest": manifest_body, "latest": pointer}


def _load_json_object(path: Path, failure: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise AuditContractError(failure) from exc
    if not isinstance(payload, dict):
        raise AuditContractError(failure)
    return payload


def read_latest_result(
    audit_id: str,
    *,
    result_root: str | Path | None = None,
    now: datetime | None = None,
    signing_key: str | bytes | None = None,
    expected_source_commit: str = "",
) -> dict[str, Any]:
    if not AUDIT_ID_PATTERN.fullmatch(audit_id):
        raise AuditContractError("audit_id_invalid")
    root = Path(result_root) if result_root else repo_root() / DEFAULT_RESULT_ROOT
    audit_root = _safe_relative_path(root.resolve(), audit_id)
    pointer_path = audit_root / "latest.json"
    pointer = _load_json_object(pointer_path, "latest_pointer_unavailable")
    if pointer.get("schema") != LATEST_SCHEMA or pointer.get("audit_id") != audit_id:
        raise AuditContractError("latest_pointer_invalid")
    run_id = str(pointer.get("run_id") or "")
    run_root = _safe_relative_path(audit_root, run_id)
    manifest_path = run_root / "manifest.json"
    if not hmac.compare_digest(_sha256_file(manifest_path), str(pointer.get("manifest_sha256") or "")):
        raise AuditContractError("manifest_hash_mismatch")
    manifest = _load_json_object(manifest_path, "manifest_unavailable")
    if manifest.get("schema") != MANIFEST_SCHEMA or manifest.get("run_id") != run_id:
        raise AuditContractError("manifest_invalid")
    for filename in ("result.json", "evidence.json"):
        path = run_root / filename
        expected = str((manifest.get("files") or {}).get(filename) or "")
        if not expected or not hmac.compare_digest(_sha256_file(path), expected):
            raise AuditContractError(f"artifact_hash_mismatch:{filename}")
    signature = manifest.get("signature")
    if signature:
        if not signing_key:
            raise AuditContractError("signature_key_required")
        key_bytes = signing_key.encode("utf-8") if isinstance(signing_key, str) else signing_key
        unsigned = dict(manifest)
        unsigned.pop("signature", None)
        expected = hmac.new(key_bytes, _json_bytes(unsigned), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, str(signature.get("value") or "")):
            raise AuditContractError("manifest_signature_invalid")
    result = _load_json_object(run_root / "result.json", "result_unavailable")
    if result.get("schema") != RESULT_SCHEMA or result.get("audit_id") != audit_id:
        raise AuditContractError("result_invalid")
    moment = (now or _utc_now()).astimezone(timezone.utc)
    expires = _parse_datetime(result.get("expires_at"))
    state = "current"
    reasons: list[str] = []
    if expires is None:
        state = "invalid"
        reasons.append("expires_at_invalid")
    elif expires <= moment:
        state = "stale"
        reasons.append("result_expired")
    source_commit = str((result.get("target") or {}).get("source_commit") or "")
    if expected_source_commit and source_commit != expected_source_commit:
        state = "stale"
        reasons.append("source_commit_mismatch")
    return {
        "state": state,
        "reasons": reasons,
        "result": result,
        "manifest": manifest,
        "latest": pointer,
    }


def public_result_summary(validated: Mapping[str, Any]) -> dict[str, Any]:
    result = validated.get("result") if isinstance(validated.get("result"), dict) else {}
    findings = result.get("findings") if isinstance(result.get("findings"), list) else []
    public_findings = [
        {key: value for key, value in item.items() if key in PUBLIC_FINDING_KEYS}
        for item in findings
        if isinstance(item, dict)
    ]
    target = result.get("target") if isinstance(result.get("target"), dict) else {}
    manifest = validated.get("manifest") if isinstance(validated.get("manifest"), dict) else {}
    return {
        "audit_id": result.get("audit_id"),
        "run_id": result.get("run_id"),
        "title": result.get("title"),
        "component": result.get("component"),
        "state": validated.get("state"),
        "stale_reasons": list(validated.get("reasons") or []),
        "verdict": result.get("verdict"),
        "generated_at": result.get("generated_at"),
        "expires_at": result.get("expires_at"),
        "target": {
            "label": target.get("label"),
            "source_commit": target.get("source_commit"),
            "working_tree_dirty": bool(target.get("working_tree_dirty")),
        },
        "summary": result.get("summary") if isinstance(result.get("summary"), dict) else {},
        "findings": public_findings,
        "integrity": manifest.get("integrity", "unknown"),
        "mutates_target": False,
    }


def run_and_store(
    audit_id: str,
    *,
    target_root: str | Path,
    catalog_path: str | Path | None = None,
    result_root: str | Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    result, evidence = execute_audit(audit_id, target_root=target_root, catalog_path=catalog_path, now=now)
    stored = write_immutable_result(
        result,
        evidence,
        result_root=result_root,
        signing_key=os.getenv("AIBENCHIE_AUDIT_SIGNING_KEY") or None,
        signing_key_id=os.getenv("AIBENCHIE_AUDIT_SIGNING_KEY_ID", ""),
    )
    validated = read_latest_result(
        audit_id,
        result_root=result_root,
        now=now,
        signing_key=os.getenv("AIBENCHIE_AUDIT_SIGNING_KEY") or None,
    )
    return public_result_summary(validated) | {"stored": True, "run_id": stored["run_id"]}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AIBenchie audit authority")
    parser.add_argument("--catalog", default=str(repo_root() / DEFAULT_CATALOG_PATH))
    parser.add_argument("--results", default=str(repo_root() / DEFAULT_RESULT_ROOT))
    parser.add_argument("--target", default=os.getenv("AIBENCHIE_NULLXOID_WRAPPER_REPO", ""))
    parser.add_argument("--list", action="store_true", help="List the public audit catalog.")
    parser.add_argument("--run", default="", help="Run one stable audit id and store its immutable result.")
    parser.add_argument("--latest", default="", help="Read and validate the latest result for one audit id.")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.list:
            payload = {"ok": True, **public_catalog(load_catalog(args.catalog))}
        elif args.run:
            target = args.target or (str(repo_root()) if args.run.startswith("aibenchie.") else "")
            if not target:
                raise AuditContractError("target_repository_required")
            payload = {"ok": True, **run_and_store(args.run, target_root=target, catalog_path=args.catalog, result_root=args.results)}
        elif args.latest:
            validated = read_latest_result(
                args.latest,
                result_root=args.results,
                signing_key=os.getenv("AIBENCHIE_AUDIT_SIGNING_KEY") or None,
            )
            payload = {"ok": True, **public_result_summary(validated)}
        else:
            payload = {"ok": False, "error": "choose_list_run_or_latest"}
    except AuditContractError as exc:
        payload = {"ok": False, "error": str(exc)}
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"AIBenchie audit: {'OK' if payload.get('ok') else 'FAIL'}")
        if payload.get("error"):
            print(payload["error"])
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
