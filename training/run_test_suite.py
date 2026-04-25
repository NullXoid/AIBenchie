from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "test_suites.json"
DEFAULT_HISTORY = PROJECT_ROOT / "reports" / "test_suites" / "test_suite_history.jsonl"
DEFAULT_SUMMARY = PROJECT_ROOT / "reports" / "test_suites" / "test_suite_summary.json"


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def load_config(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("test suite config must be a JSON object")
    suites = payload.get("suites")
    if not isinstance(suites, dict) or not suites:
        raise ValueError("test suite config must define non-empty suites")
    for suite_name, suite in suites.items():
        if not isinstance(suite, dict):
            raise ValueError(f"suite {suite_name} must be a JSON object")
        paths = suite.get("paths")
        if not isinstance(paths, list) or not paths:
            raise ValueError(f"suite {suite_name} must define non-empty paths")
        if not all(isinstance(item, str) and item.strip() for item in paths):
            raise ValueError(f"suite {suite_name} paths must be non-empty strings")
        pytest_args = suite.get("pytest_args", [])
        if not isinstance(pytest_args, list) or not all(isinstance(item, str) for item in pytest_args):
            raise ValueError(f"suite {suite_name} pytest_args must be a list of strings")
    default_suite = payload.get("default_suite")
    if default_suite not in suites:
        raise ValueError("default_suite must name a configured suite")
    return payload


def resolve_suite(config: dict[str, Any], suite_name: str | None) -> tuple[str, dict[str, Any]]:
    suites = config["suites"]
    name = suite_name or config["default_suite"]
    if name not in suites:
        available = ", ".join(sorted(suites))
        raise ValueError(f"unknown suite `{name}`; available suites: {available}")
    return name, suites[name]


def suite_command(suite: dict[str, Any], extra_pytest_args: list[str] | None = None) -> list[str]:
    args = [sys.executable, "-m", "pytest"]
    args.extend(str(PROJECT_ROOT / path) for path in suite["paths"])
    args.extend(suite.get("pytest_args", []))
    if extra_pytest_args:
        args.extend(extra_pytest_args)
    return args


def read_history(path: Path = DEFAULT_HISTORY) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def append_history(record: dict[str, Any], path: Path = DEFAULT_HISTORY) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def write_summary(history: list[dict[str, Any]], path: Path = DEFAULT_SUMMARY) -> dict[str, Any]:
    usage = Counter(str(record.get("suite", "")) for record in history if record.get("suite"))
    passed = Counter(
        str(record.get("suite", ""))
        for record in history
        if record.get("suite") and int(record.get("returncode", 1)) == 0
    )
    failed = Counter(
        str(record.get("suite", ""))
        for record in history
        if record.get("suite") and int(record.get("returncode", 1)) != 0
    )
    recent = history[-10:]
    payload = {
        "schema_version": "1.0",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "total_recorded_runs": len(history),
        "most_used_suites": [
            {
                "suite": suite,
                "runs": count,
                "passes": passed.get(suite, 0),
                "failures": failed.get(suite, 0),
            }
            for suite, count in usage.most_common()
        ],
        "recent_runs": recent,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def list_suites(config: dict[str, Any]) -> None:
    print("Configured test suites:")
    for name, suite in sorted(config["suites"].items()):
        kind = suite.get("kind", "unspecified")
        description = suite.get("description", "")
        print(f"- {name} [{kind}]: {description}")


def run_suite(
    *,
    suite_name: str,
    suite: dict[str, Any],
    extra_pytest_args: list[str],
    record: bool,
) -> int:
    command = suite_command(suite, extra_pytest_args)
    started_at = datetime.now(timezone.utc).isoformat()
    started = time.perf_counter()
    print("Running:", " ".join(command))
    completed = subprocess.run(command, cwd=PROJECT_ROOT)
    elapsed_seconds = round(time.perf_counter() - started, 3)
    finished_at = datetime.now(timezone.utc).isoformat()
    if record:
        history_record = {
            "suite": suite_name,
            "kind": suite.get("kind", "unspecified"),
            "started_at": started_at,
            "finished_at": finished_at,
            "elapsed_seconds": elapsed_seconds,
            "returncode": completed.returncode,
            "command": command,
        }
        append_history(history_record)
        write_summary(read_history())
    return completed.returncode


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run configured LV7 pytest suites and record suite usage.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="Path to test suite config JSON.")
    parser.add_argument("--suite", help="Suite name to run. Defaults to config default_suite.")
    parser.add_argument("--list", action="store_true", help="List configured suites and exit.")
    parser.add_argument("--dry-run", action="store_true", help="Print the pytest command without running it.")
    parser.add_argument("--no-record", action="store_true", help="Do not append reports/test_suites history.")
    parser.add_argument(
        "pytest_args",
        nargs=argparse.REMAINDER,
        help="Extra pytest args. Use -- before pytest args, for example: -- -q -x",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    if args.list:
        list_suites(config)
        return

    suite_name, suite = resolve_suite(config, args.suite)
    extra_pytest_args = list(args.pytest_args)
    if extra_pytest_args and extra_pytest_args[0] == "--":
        extra_pytest_args = extra_pytest_args[1:]
    command = suite_command(suite, extra_pytest_args)
    if args.dry_run:
        print(" ".join(command))
        return
    raise SystemExit(
        run_suite(
            suite_name=suite_name,
            suite=suite,
            extra_pytest_args=extra_pytest_args,
            record=not args.no_record,
        )
    )


if __name__ == "__main__":
    main()
