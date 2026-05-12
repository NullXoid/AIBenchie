from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from aibenchie.lv7_autonomy_gate import run_gate


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LV7_ROOT = PROJECT_ROOT.parent / "Lv-7"
DEFAULT_OUTPUT = PROJECT_ROOT / "_validation" / "lv7-autonomy-evidence.json"


def build_generation_command(*, python_exe: str, output: Path) -> list[str]:
    return [
        python_exe,
        "-m",
        "lv7_autonomy.evidence",
        "--output",
        str(output),
    ]


def run_lv7_autonomy_gate(
    *,
    lv7_root: Path = DEFAULT_LV7_ROOT,
    output: Path = DEFAULT_OUTPUT,
    python_exe: str = sys.executable,
) -> dict[str, Any]:
    lv7_root = lv7_root.resolve()
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if not lv7_root.exists():
        raise FileNotFoundError(f"Lv-7 root does not exist: {lv7_root}")

    command = build_generation_command(python_exe=python_exe, output=output)
    completed = subprocess.run(
        command,
        cwd=lv7_root,
        capture_output=True,
        text=True,
        check=False,
    )
    generation = {
        "command": command,
        "cwd": str(lv7_root),
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "output": str(output),
    }
    if completed.returncode != 0:
        return {
            "schema": "aibenchie.lv7-autonomy-runner.v1",
            "ok": False,
            "verdict": "fail",
            "stage": "evidence_generation",
            "generation": generation,
            "gate": None,
        }

    gate = run_gate(output)
    return {
        "schema": "aibenchie.lv7-autonomy-runner.v1",
        "ok": bool(gate["ok"]),
        "verdict": gate["verdict"],
        "stage": "gate",
        "generation": generation,
        "gate": gate,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate Lv-7 autonomy evidence and validate it with AIBenchie.")
    parser.add_argument("--lv7-root", type=Path, default=DEFAULT_LV7_ROOT, help="Path to the Lv-7 repository.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Evidence JSON output path.")
    parser.add_argument("--python", default=sys.executable, help="Python executable used to run Lv-7 evidence generation.")
    parser.add_argument("--json", action="store_true", help="Print full JSON result.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_lv7_autonomy_gate(
        lv7_root=args.lv7_root,
        output=args.output,
        python_exe=args.python,
    )
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        gate = result.get("gate") or {}
        summary = gate.get("summary") or {}
        if summary:
            print(f"Lv-7 autonomy gate: {result['verdict']} ({summary.get('pass')}/{summary.get('checks')} checks passed)")
        else:
            print(f"Lv-7 autonomy gate: {result['verdict']} at {result['stage']}")
        print(f"Evidence: {result['generation']['output']}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
