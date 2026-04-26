from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


MIB = 1024 * 1024

DEFAULT_RUNTIME_MAX_MB = 50
DEFAULT_DATA_MAX_MB = 250
DEFAULT_RUNTIME_FILE_MAX_MB = 5
DEFAULT_DATA_FILE_MAX_MB = 50
DEFAULT_RUNTIME_MAX_FILES = 150
DEFAULT_DATA_MAX_FILES = 300

IGNORED_LOCAL_DIRS = (
    ".suite/local",
    ".suite/addons/local",
    "reports/local",
    "reports/runtime/.local",
    "data/local",
    "data/private",
)

FORBIDDEN_GENERATED_SUFFIXES = (
    ".tmp",
    ".log",
    ".html",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".zip",
    ".tar",
    ".gz",
    ".sqlite",
    ".sqlite3",
    ".db",
)

TRACKED_GENERATED_GUARD_PATHS = (
    "reports/runtime",
    "data/dpo_expansion_v1_3_2/dpo_train_ready.jsonl",
    "data/dpo_smoke_v1_1/dpo_train_ready.jsonl",
)


@dataclass(frozen=True)
class GeneratedOutputBudget:
    name: str
    relative_path: str
    max_bytes: int
    max_file_bytes: int
    max_files: int
    required: bool = False


@dataclass
class GeneratedOutputBudgetResult:
    name: str
    relative_path: str
    bytes_used: int
    max_bytes: int
    max_file_bytes: int
    max_files: int
    file_count: int
    ok: bool
    largest_files: list[dict[str, Any]] = field(default_factory=list)
    failure: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "relative_path": self.relative_path,
            "bytes_used": self.bytes_used,
            "mb_used": round(self.bytes_used / MIB, 2),
            "max_bytes": self.max_bytes,
            "max_mb": round(self.max_bytes / MIB, 2),
            "max_file_bytes": self.max_file_bytes,
            "max_file_mb": round(self.max_file_bytes / MIB, 2),
            "max_files": self.max_files,
            "file_count": self.file_count,
            "largest_files": self.largest_files,
            "ok": self.ok,
            "failure": self.failure,
        }


@dataclass
class GeneratedOutputForbiddenFile:
    path: str
    bytes_used: int
    failure: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "bytes_used": self.bytes_used,
            "mb_used": round(self.bytes_used / MIB, 2),
            "failure": self.failure,
        }


@dataclass
class GeneratedOutputDirtyFile:
    path: str
    status: str
    failure: str = "tracked_generated_output_dirty"

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "status": self.status,
            "failure": self.failure,
        }


@dataclass
class GeneratedOutputPolicyResult:
    ok: bool
    root: str
    budgets: list[GeneratedOutputBudgetResult]
    forbidden_files: list[GeneratedOutputForbiddenFile]
    dirty_tracked_files: list[GeneratedOutputDirtyFile]
    ignored_local_dirs: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "root": self.root,
            "budgets": [budget.as_dict() for budget in self.budgets],
            "forbidden_files": [item.as_dict() for item in self.forbidden_files],
            "dirty_tracked_files": [item.as_dict() for item in self.dirty_tracked_files],
            "ignored_local_dirs": self.ignored_local_dirs,
        }


def _mb_to_bytes(value: str | int | float) -> int:
    return int(float(value) * MIB)


def _repo_root_from_env(env: dict[str, str] | None = None) -> Path:
    source = os.environ if env is None else env
    configured = source.get("AIBENCHIE_GENERATED_ROOT", "").strip()
    if configured:
        return Path(configured).resolve()
    return Path(__file__).resolve().parents[1]


def _default_budgets(env: dict[str, str] | None = None) -> list[GeneratedOutputBudget]:
    source = os.environ if env is None else env
    return [
        GeneratedOutputBudget(
            name="runtime_reports",
            relative_path="reports/runtime",
            max_bytes=_mb_to_bytes(source.get("AIBENCHIE_GENERATED_RUNTIME_MAX_MB", DEFAULT_RUNTIME_MAX_MB)),
            max_file_bytes=_mb_to_bytes(
                source.get("AIBENCHIE_GENERATED_RUNTIME_FILE_MAX_MB", DEFAULT_RUNTIME_FILE_MAX_MB)
            ),
            max_files=int(source.get("AIBENCHIE_GENERATED_RUNTIME_MAX_FILES", DEFAULT_RUNTIME_MAX_FILES)),
        ),
        GeneratedOutputBudget(
            name="public_data_fixtures",
            relative_path="data",
            max_bytes=_mb_to_bytes(source.get("AIBENCHIE_GENERATED_DATA_MAX_MB", DEFAULT_DATA_MAX_MB)),
            max_file_bytes=_mb_to_bytes(source.get("AIBENCHIE_GENERATED_DATA_FILE_MAX_MB", DEFAULT_DATA_FILE_MAX_MB)),
            max_files=int(source.get("AIBENCHIE_GENERATED_DATA_MAX_FILES", DEFAULT_DATA_MAX_FILES)),
        ),
    ]


def _path_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _is_ignored_local_path(relative_path: Path) -> bool:
    normalized = relative_path.as_posix()
    return any(normalized == item or normalized.startswith(f"{item}/") for item in IGNORED_LOCAL_DIRS)


def _iter_public_generated_files(root: Path, relative_path: str) -> list[Path]:
    base = root / relative_path
    if not base.exists():
        return []
    files: list[Path] = []
    for path in base.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if _is_ignored_local_path(relative):
            continue
        files.append(path)
    return sorted(files)


def check_generated_output_budget(root: Path, budget: GeneratedOutputBudget) -> GeneratedOutputBudgetResult:
    base = root / budget.relative_path
    if not base.exists():
        ok = not budget.required
        return GeneratedOutputBudgetResult(
            name=budget.name,
            relative_path=budget.relative_path,
            bytes_used=0,
            max_bytes=budget.max_bytes,
            max_file_bytes=budget.max_file_bytes,
            max_files=budget.max_files,
            file_count=0,
            ok=ok,
            failure="" if ok else "required_path_missing",
        )

    files = _iter_public_generated_files(root, budget.relative_path)
    sized_files = [(path, _path_size(path)) for path in files]
    bytes_used = sum(size for _, size in sized_files)
    largest = sorted(sized_files, key=lambda item: item[1], reverse=True)[:5]
    largest_files = [
        {
            "path": path.relative_to(root).as_posix(),
            "bytes_used": size,
            "mb_used": round(size / MIB, 2),
        }
        for path, size in largest
    ]

    oversized = [path for path, size in sized_files if size > budget.max_file_bytes]
    failure = ""
    if bytes_used > budget.max_bytes:
        failure = "budget_exceeded"
    elif oversized:
        failure = "file_budget_exceeded"
    elif len(files) > budget.max_files:
        failure = "file_count_exceeded"

    return GeneratedOutputBudgetResult(
        name=budget.name,
        relative_path=budget.relative_path,
        bytes_used=bytes_used,
        max_bytes=budget.max_bytes,
        max_file_bytes=budget.max_file_bytes,
        max_files=budget.max_files,
        file_count=len(files),
        largest_files=largest_files,
        ok=not failure,
        failure=failure,
    )


def find_forbidden_generated_files(root: Path) -> list[GeneratedOutputForbiddenFile]:
    forbidden: list[GeneratedOutputForbiddenFile] = []
    for relative_root in ("reports", "data"):
        base = root / relative_root
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(root)
            if _is_ignored_local_path(relative):
                continue
            lower_name = path.name.lower()
            if lower_name.endswith(FORBIDDEN_GENERATED_SUFFIXES):
                forbidden.append(
                    GeneratedOutputForbiddenFile(
                        path=relative.as_posix(),
                        bytes_used=_path_size(path),
                        failure="forbidden_generated_file_type",
                    )
                )
    return sorted(forbidden, key=lambda item: item.path)


def _parse_git_status_path(line: str) -> str:
    path = line[3:] if len(line) > 3 else ""
    if " -> " in path:
        path = path.split(" -> ", 1)[1]
    return path.strip().strip('"')


def find_dirty_tracked_generated_files(root: Path) -> list[GeneratedOutputDirtyFile]:
    if not (root / ".git").exists():
        return []
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain", "--", *TRACKED_GENERATED_GUARD_PATHS],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if completed.returncode != 0:
        return []

    dirty: list[GeneratedOutputDirtyFile] = []
    for line in completed.stdout.splitlines():
        if len(line) < 4:
            continue
        status = line[:2].strip() or line[:2]
        path = _parse_git_status_path(line)
        if not path:
            continue
        relative = Path(path)
        if _is_ignored_local_path(relative):
            continue
        dirty.append(GeneratedOutputDirtyFile(path=relative.as_posix(), status=status))
    return sorted(dirty, key=lambda item: item.path)


def run_generated_output_policy_check(env: dict[str, str] | None = None) -> GeneratedOutputPolicyResult:
    root = _repo_root_from_env(env)
    budgets = [check_generated_output_budget(root, budget) for budget in _default_budgets(env)]
    forbidden_files = find_forbidden_generated_files(root)
    dirty_tracked_files = find_dirty_tracked_generated_files(root)
    return GeneratedOutputPolicyResult(
        ok=all(budget.ok for budget in budgets) and not forbidden_files and not dirty_tracked_files,
        root=str(root),
        budgets=budgets,
        forbidden_files=forbidden_files,
        dirty_tracked_files=dirty_tracked_files,
        ignored_local_dirs=list(IGNORED_LOCAL_DIRS),
    )
