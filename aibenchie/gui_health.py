from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aibenchie.distribution_hygiene import run_distribution_hygiene_check
from aibenchie.generated_output_policy import run_generated_output_policy_check
from aibenchie.release import validate_status_payload


PYTEST_COUNT = re.compile(r"(\d+) tests? collected")


@dataclass(frozen=True)
class RepositoryHealth:
    generated_at: str
    collected_tests: int
    collection_ok: bool
    release_status: str
    release_ok: bool
    generated_output_ok: bool
    distribution_ok: bool
    distribution_files_scanned: int
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def critical_blockers(self) -> int:
        return len(self.blockers)

    @property
    def publish_mode(self) -> str:
        return "Blocked" if self.blockers else "Eligible"

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["critical_blockers"] = self.critical_blockers
        payload["publish_mode"] = self.publish_mode
        return payload


def collect_pytest_health(root: Path, *, timeout_seconds: int = 30) -> tuple[int, bool, str]:
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return 0, False, f"Test collection could not run: {type(exc).__name__}"

    output = f"{completed.stdout}\n{completed.stderr}"
    matches = PYTEST_COUNT.findall(output)
    count = int(matches[-1]) if matches else 0
    if completed.returncode != 0:
        return count, False, f"Test collection failed with exit code {completed.returncode}."
    return count, True, ""


def _release_health(root: Path) -> tuple[str, bool, str]:
    status_path = root / "public_export" / "suite-status.json"
    if not status_path.is_file():
        return "missing", False, "Public suite status is missing."
    try:
        payload = json.loads(status_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "invalid", False, "Public suite status is invalid."

    validation = validate_status_payload(payload, now=datetime.now(timezone.utc))
    effective = str(validation.get("effective_status") or payload.get("status") or "unknown")
    if validation.get("ok"):
        return effective, True, ""
    reasons = ", ".join(str(item) for item in validation.get("failures", [])) or "validation failed"
    return effective, False, f"Public suite status is not current: {reasons}."


def build_repository_health(root: Path) -> RepositoryHealth:
    resolved = root.resolve()
    blockers: list[str] = []
    warnings: list[str] = []

    collected_tests, collection_ok, collection_failure = collect_pytest_health(resolved)
    if collection_failure:
        blockers.append(collection_failure)

    release_status, release_ok, release_failure = _release_health(resolved)
    if release_failure:
        blockers.append(release_failure)

    generated = run_generated_output_policy_check({"AIBENCHIE_GENERATED_ROOT": str(resolved)})
    if not generated.ok:
        reasons = [budget.failure for budget in generated.budgets if not budget.ok]
        if generated.forbidden_files:
            reasons.append("forbidden generated files")
        if generated.dirty_tracked_files:
            reasons.append("dirty generated evidence")
        detail = ", ".join(dict.fromkeys(reason for reason in reasons if reason)) or "policy failed"
        blockers.append(f"Generated-output policy failed: {detail}.")

    distribution = run_distribution_hygiene_check(root=resolved)
    if not distribution.ok:
        blockers.append(f"Distribution hygiene found {len(distribution.findings)} issue(s).")

    if not (resolved / ".git").is_dir():
        warnings.append("Repository metadata is unavailable; working-tree state was not verified.")

    return RepositoryHealth(
        generated_at=datetime.now(timezone.utc).isoformat(),
        collected_tests=collected_tests,
        collection_ok=collection_ok,
        release_status=release_status,
        release_ok=release_ok,
        generated_output_ok=generated.ok,
        distribution_ok=distribution.ok,
        distribution_files_scanned=distribution.scanned_files,
        blockers=blockers,
        warnings=warnings,
    )
