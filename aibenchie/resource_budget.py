from __future__ import annotations

import glob
import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


MIB = 1024 * 1024


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

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "profile": self.profile,
            "disk": self.disk.as_dict(),
            "items": [item.as_dict() for item in self.items],
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
    return ResourceBudgetResult(
        ok=disk.ok and all(item.ok for item in items),
        profile=profile,
        disk=disk,
        items=items,
    )
