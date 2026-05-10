from __future__ import annotations

import glob
import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


MIB = 1024 * 1024
EXPECTED_RUNTIME_SCHEMA = "echolabs.resource-manager-runtime.v1"
DEFAULT_RUNTIME_EVIDENCE_PATH = Path("configs/echolabs_resource_manager_runtime.example.json")
FORBIDDEN_KEYS = {"client_secret", "private_key", "password", "service_secret", "service_token", "api_key", "token"}


@dataclass(frozen=True)
class ResourceBudget:
    name: str
    pattern: str
    max_bytes: int
    required: bool = False

    @classmethod
    def from_dict(cls, item: dict[str, Any]) -> "ResourceBudget":
        if not isinstance(item.get("name"), str) or not item["name"]:
            raise ValueError("resource budget entry is missing name")
        if not isinstance(item.get("pattern"), str) or not item["pattern"]:
            raise ValueError(f"resource budget {item.get('name', '<unknown>')} is missing pattern")
        max_mb = item.get("max_mb")
        max_bytes = item.get("max_bytes")
        if max_bytes is None:
            if max_mb is None:
                raise ValueError(f"resource budget {item['name']} is missing max_mb or max_bytes")
            max_bytes = int(float(max_mb) * MIB)
        return cls(
            name=item["name"],
            pattern=item["pattern"],
            max_bytes=int(max_bytes),
            required=bool(item.get("required", False)),
        )


@dataclass
class ResourceBudgetItem:
    name: str
    pattern: str
    paths: list[str]
    bytes_used: int
    max_bytes: int
    ok: bool
    failure: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "pattern": self.pattern,
            "paths": self.paths,
            "bytes_used": self.bytes_used,
            "mb_used": round(self.bytes_used / MIB, 2),
            "max_bytes": self.max_bytes,
            "max_mb": round(self.max_bytes / MIB, 2),
            "ok": self.ok,
            "failure": self.failure,
        }


@dataclass
class DiskBudget:
    root: str
    total_bytes: int
    used_bytes: int
    free_bytes: int
    used_percent: float
    min_free_bytes: int
    max_used_percent: float
    ok: bool
    failure: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "total_gb": round(self.total_bytes / (MIB * 1024), 2),
            "used_gb": round(self.used_bytes / (MIB * 1024), 2),
            "free_gb": round(self.free_bytes / (MIB * 1024), 2),
            "used_percent": round(self.used_percent, 2),
            "min_free_mb": round(self.min_free_bytes / MIB, 2),
            "max_used_percent": self.max_used_percent,
            "ok": self.ok,
            "failure": self.failure,
        }


@dataclass
class ResourceBudgetResult:
    ok: bool
    profile: str
    disk: DiskBudget
    items: list[ResourceBudgetItem] = field(default_factory=list)
    runtime: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "profile": self.profile,
            "disk": self.disk.as_dict(),
            "items": [item.as_dict() for item in self.items],
            "runtime": self.runtime,
        }


def default_ct400_wrapper_budgets() -> list[ResourceBudget]:
    return [
        ResourceBudget("backend_venv", "/home/deploy/NullXoid/NullXoid/.venv", 300 * MIB, required=True),
        ResourceBudget("staging_backend_venv", "/root/repos/echolabs/nullxoid-wrapper/.venv", 0),
        ResourceBudget("wrapper_frontend_node_modules", "/root/repos/echolabs/nullxoid-wrapper/frontend/node_modules", 500 * MIB),
        ResourceBudget("aibenchie_runtime_reports", "/root/repos/echolabs/AIBenchie/reports/runtime", 500 * MIB),
        ResourceBudget("backend_logs", "/home/deploy/NullXoid/logs", 100 * MIB),
        ResourceBudget("deploy_user_cache", "/home/deploy/.cache", 100 * MIB),
        ResourceBudget("deploy_user_pip_cache", "/home/deploy/.cache/pip", 1 * MIB),
        ResourceBudget("root_pip_cache", "/root/.cache/pip", 100 * MIB),
        ResourceBudget("heavy_venv_backups", "/home/deploy/NullXoid/NullXoid/.venv-heavy-backup-*", 0),
        ResourceBudget("disposable_npm_cache", "/dev/shm/nullxoid-npm-cache", 0),
        ResourceBudget("disposable_npm_tmp", "/dev/shm/nullxoid-npm-tmp", 0),
        ResourceBudget("tmp_nullxoid_artifacts", "/tmp/nullxoid-*", 0),
        ResourceBudget("tmp_pip_artifacts", "/tmp/pip-*", 0),
    ]


def path_size_bytes(path: Path) -> int:
    if not path.exists() and not path.is_symlink():
        return 0
    if path.is_file() or path.is_symlink():
        try:
            return path.lstat().st_size
        except OSError:
            return 0

    total = 0
    for root, dirs, files in os.walk(path, followlinks=False):
        dirs[:] = [name for name in dirs if not Path(root, name).is_symlink()]
        for filename in files:
            candidate = Path(root, filename)
            try:
                total += candidate.lstat().st_size
            except OSError:
                continue
    return total


def expand_pattern(pattern: str) -> list[Path]:
    matches = [Path(match) for match in glob.glob(pattern)]
    if matches:
        return sorted(matches)
    path = Path(pattern)
    return [path] if path.exists() else []


def load_budgets_from_env(env: dict[str, str] | None = None) -> tuple[str, list[ResourceBudget]]:
    source = os.environ if env is None else env
    profile = source.get("AIBENCHIE_RESOURCE_PROFILE", "ct400-wrapper")
    raw_json = source.get("AIBENCHIE_RESOURCE_BUDGETS_JSON", "").strip()
    if raw_json:
        parsed = json.loads(raw_json)
        if not isinstance(parsed, list):
            raise ValueError("AIBENCHIE_RESOURCE_BUDGETS_JSON must be a JSON list")
        return profile, [ResourceBudget.from_dict(item) for item in parsed]
    if profile == "ct400-wrapper":
        return profile, default_ct400_wrapper_budgets()
    raise ValueError(f"unknown resource profile: {profile}")


def check_budget_item(budget: ResourceBudget) -> ResourceBudgetItem:
    paths = expand_pattern(budget.pattern)
    if not paths:
        ok = not budget.required
        return ResourceBudgetItem(
            name=budget.name,
            pattern=budget.pattern,
            paths=[],
            bytes_used=0,
            max_bytes=budget.max_bytes,
            ok=ok,
            failure="" if ok else "required_path_missing",
        )

    bytes_used = sum(path_size_bytes(path) for path in paths)
    ok = bytes_used <= budget.max_bytes
    return ResourceBudgetItem(
        name=budget.name,
        pattern=budget.pattern,
        paths=[str(path) for path in paths],
        bytes_used=bytes_used,
        max_bytes=budget.max_bytes,
        ok=ok,
        failure="" if ok else "budget_exceeded",
    )


def check_disk_budget(
    *,
    root: str,
    min_free_bytes: int,
    max_used_percent: float,
) -> DiskBudget:
    usage = shutil.disk_usage(root)
    used_bytes = usage.total - usage.free
    used_percent = (used_bytes / usage.total) * 100 if usage.total else 100.0
    failure = ""
    if usage.free < min_free_bytes:
        failure = "disk_free_below_budget"
    elif used_percent > max_used_percent:
        failure = "disk_used_percent_above_budget"
    return DiskBudget(
        root=root,
        total_bytes=usage.total,
        used_bytes=used_bytes,
        free_bytes=usage.free,
        used_percent=used_percent,
        min_free_bytes=min_free_bytes,
        max_used_percent=max_used_percent,
        ok=not failure,
        failure=failure,
    )


def _check(name: str, ok: bool, failure: str = "", **detail: Any) -> dict[str, Any]:
    return {"name": name, "ok": ok, "failure": "" if ok else failure, "detail": detail}


def _forbidden_secret_paths(payload: Any, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            lowered = str(key).lower()
            if lowered in FORBIDDEN_KEYS or lowered.endswith("_secret") or lowered.endswith("_token"):
                found.append(f"{path}.{key}")
            found.extend(_forbidden_secret_paths(value, f"{path}.{key}"))
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            found.extend(_forbidden_secret_paths(item, f"{path}[{index}]"))
    return found


def _resolve_runtime_evidence_path(path: str | Path | None) -> Path:
    root = Path(__file__).resolve().parents[1]
    resolved = Path(path or root / DEFAULT_RUNTIME_EVIDENCE_PATH)
    if not resolved.is_absolute():
        resolved = (root / resolved).resolve()
    return resolved


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def validate_runtime_evidence(path: str | Path | None, *, require_runtime: bool = False) -> dict[str, Any]:
    evidence_path = _resolve_runtime_evidence_path(path)
    checks: list[dict[str, Any]] = []
    if require_runtime and not path:
        checks.append(_check("runtime.evidence_file", False, "missing_runtime_evidence_path", path=str(evidence_path)))
        return {"ok": False, "required": require_runtime, "path": str(evidence_path), "checks": checks}
    if not path:
        return {"ok": True, "required": require_runtime, "path": str(evidence_path), "checks": []}
    if not evidence_path.exists():
        checks.append(_check("runtime.evidence_file", False, "missing_config_file", path=str(evidence_path)))
        return {"ok": False, "required": require_runtime, "path": str(evidence_path), "checks": checks}

    try:
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    except Exception as exc:
        checks.append(_check("runtime.evidence_file", False, f"invalid_json:{type(exc).__name__}", path=str(evidence_path)))
        return {"ok": False, "required": require_runtime, "path": str(evidence_path), "checks": checks}
    if not isinstance(payload, dict):
        checks.append(_check("runtime.evidence_file", False, "config_must_be_object", path=str(evidence_path)))
        return {"ok": False, "required": require_runtime, "path": str(evidence_path), "checks": checks}

    checks.append(_check("runtime.evidence_file", True, path=str(evidence_path)))
    checks.append(_check("runtime.schema", payload.get("schema") == EXPECTED_RUNTIME_SCHEMA, "schema_mismatch", expected=EXPECTED_RUNTIME_SCHEMA, actual=payload.get("schema")))
    template = payload.get("template") is True
    checks.append(_check("runtime.template", not (require_runtime and template), "template_runtime_evidence_not_allowed", value=template))
    forbidden = _forbidden_secret_paths(payload)
    checks.append(_check("runtime.secret_keys_absent", not forbidden, "forbidden_secret_keys_present", paths=forbidden))

    profiles = payload.get("profiles") if isinstance(payload.get("profiles"), dict) else {}
    leases = payload.get("leases")
    if not isinstance(leases, list) or not leases:
        checks.append(_check("runtime.leases", False, "missing_leases"))
    else:
        checks.append(_check("runtime.leases", True, count=len(leases)))
        for index, lease in enumerate(leases):
            if not isinstance(lease, dict):
                checks.append(_check(f"runtime.leases[{index}]", False, "lease_must_be_object"))
                continue
            profile_name = str(lease.get("profile") or "")
            profile = profiles.get(profile_name) if isinstance(profiles.get(profile_name), dict) else {}
            max_profile_seconds = _int_or_none(profile.get("max_lease_seconds")) or 0
            max_profile_memory = _int_or_none(profile.get("max_memory_mb")) or 0
            retention_seconds = _int_or_none(profile.get("retention_seconds")) or 0
            duration = _int_or_none(lease.get("max_duration_seconds"))
            memory = _int_or_none(lease.get("max_memory_mb"))
            cleanup_after = _int_or_none(lease.get("cleanup_after_seconds"))
            checks.append(_check(f"runtime.leases[{index}].approved", lease.get("approved") is True, "lease_must_be_approved"))
            checks.append(_check(f"runtime.leases[{index}].duration", duration is not None and duration > 0 and (not max_profile_seconds or duration <= max_profile_seconds), "lease_duration_unbounded", duration=duration, max=max_profile_seconds))
            checks.append(_check(f"runtime.leases[{index}].memory", memory is not None and memory > 0 and (not max_profile_memory or memory <= max_profile_memory), "lease_memory_unbounded", memory=memory, max=max_profile_memory))
            checks.append(_check(f"runtime.leases[{index}].cleanup_after", cleanup_after is not None and cleanup_after > 0 and (not retention_seconds or cleanup_after <= retention_seconds), "lease_cleanup_unbounded", cleanup_after=cleanup_after, retention=retention_seconds))

    cleanup = payload.get("cleanup")
    if not isinstance(cleanup, dict):
        checks.append(_check("runtime.cleanup", False, "missing_cleanup"))
    else:
        checks.append(_check("runtime.cleanup.enabled", cleanup.get("enabled") is True, "cleanup_must_be_enabled"))
        checks.append(_check("runtime.cleanup.last_success_at", bool(str(cleanup.get("last_success_at") or "").strip()), "cleanup_success_missing"))
        deleted_expired = _int_or_none(cleanup.get("deleted_expired_leases"))
        checks.append(_check("runtime.cleanup.deleted_expired_leases", deleted_expired is not None and deleted_expired >= 0, "cleanup_deleted_count_invalid"))

    pressure = payload.get("pressure")
    if not isinstance(pressure, dict):
        checks.append(_check("runtime.pressure", False, "missing_pressure_snapshot"))
    else:
        level = str(pressure.get("level") or "").lower()
        checks.append(_check("runtime.pressure.level", level in {"low", "normal", "ok", "ready"}, "pressure_not_safe", level=level))
        active_leases = _int_or_none(pressure.get("active_leases"))
        pressure_profile = profiles.get(str(pressure.get("profile") or "")) if isinstance(profiles.get(str(pressure.get("profile") or "")), dict) else {}
        max_parallel = _int_or_none(pressure_profile.get("max_parallel_jobs")) or 0
        checks.append(_check("runtime.pressure.active_leases", active_leases is not None and active_leases >= 0 and (not max_parallel or active_leases <= max_parallel), "active_leases_above_profile", active=active_leases, max=max_parallel))

    return {
        "ok": all(check["ok"] for check in checks),
        "required": require_runtime,
        "path": str(evidence_path),
        "checks": checks,
    }


def run_resource_budget_check(env: dict[str, str] | None = None) -> ResourceBudgetResult:
    source = os.environ if env is None else env
    profile, budgets = load_budgets_from_env(source)
    disk_root = source.get("AIBENCHIE_RESOURCE_DISK_ROOT", "/")
    min_free_mb = float(source.get("AIBENCHIE_RESOURCE_MIN_FREE_MB", "1024"))
    max_used_percent = float(source.get("AIBENCHIE_RESOURCE_MAX_USED_PERCENT", "85"))
    disk = check_disk_budget(
        root=disk_root,
        min_free_bytes=int(min_free_mb * MIB),
        max_used_percent=max_used_percent,
    )
    items = [check_budget_item(budget) for budget in budgets]
    runtime = validate_runtime_evidence(
        source.get("AIBENCHIE_RESOURCE_MANAGER_EVIDENCE") or None,
        require_runtime=source.get("AIBENCHIE_RESOURCE_MANAGER_REQUIRE_RUNTIME", "").strip().lower() in {"1", "true", "yes"},
    )
    return ResourceBudgetResult(
        ok=disk.ok and all(item.ok for item in items) and bool(runtime.get("ok", True)),
        profile=profile,
        disk=disk,
        items=items,
        runtime=runtime,
    )
