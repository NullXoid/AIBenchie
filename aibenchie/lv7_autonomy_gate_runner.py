from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from aibenchie.lv7_autonomy_gate import run_gate
from aibenchie.resource_telemetry import run_monitored_command, write_resource_telemetry


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LV7_ROOT = PROJECT_ROOT.parent / "Lv-7"
DEFAULT_OUTPUT = PROJECT_ROOT / "_validation" / "lv7-autonomy-evidence.json"
DEFAULT_TELEMETRY_OUTPUT = PROJECT_ROOT / "_validation" / "lv7-autonomy-resource-telemetry.json"


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
    telemetry_output: Path = DEFAULT_TELEMETRY_OUTPUT,
    python_exe: str = sys.executable,
    telemetry_sample_interval: float = 0.5,
) -> dict[str, Any]:
    lv7_root = lv7_root.resolve()
    output = output.resolve()
    telemetry_output = telemetry_output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    telemetry_output.parent.mkdir(parents=True, exist_ok=True)
    if not lv7_root.exists():
        raise FileNotFoundError(f"Lv-7 root does not exist: {lv7_root}")

    command = build_generation_command(python_exe=python_exe, output=output)
    completed = run_monitored_command(
        command,
        cwd=lv7_root,
        sample_interval_seconds=telemetry_sample_interval,
    )
    write_resource_telemetry(telemetry_output, completed.resource_telemetry)
    generation = {
        "command": command,
        "cwd": str(lv7_root),
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "output": str(output),
        "resource_telemetry_output": str(telemetry_output),
        "resource_telemetry_summary": completed.resource_telemetry["summary"],
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
    parser.add_argument(
        "--telemetry-output",
        type=Path,
        default=DEFAULT_TELEMETRY_OUTPUT,
        help="Resource telemetry JSON output path.",
    )
    parser.add_argument(
        "--telemetry-sample-interval",
        type=float,
        default=0.5,
        help="Seconds between CPU, memory, and GPU telemetry samples.",
    )
    parser.add_argument("--python", default=sys.executable, help="Python executable used to run Lv-7 evidence generation.")
    parser.add_argument("--json", action="store_true", help="Print full JSON result.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_lv7_autonomy_gate(
        lv7_root=args.lv7_root,
        output=args.output,
        telemetry_output=args.telemetry_output,
        python_exe=args.python,
        telemetry_sample_interval=args.telemetry_sample_interval,
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
        print(f"Telemetry: {result['generation']['resource_telemetry_output']}")
        telemetry = result["generation"]["resource_telemetry_summary"]
        cpu = telemetry.get("cpu", {})
        memory = telemetry.get("memory", {})
        gpu = telemetry.get("gpu", {})
        print(
            f"CPU peak: process={cpu.get('process_percent_peak')}%, "
            f"system={cpu.get('system_percent_peak')}%, "
            f"process_seconds={cpu.get('process_seconds_total')}"
        )
        print(f"Memory peak: process={memory.get('process_rss_mb_peak')} MB, system={memory.get('system_used_percent_peak')}%")
        gpu_status = (
            f"gpu={gpu.get('utilization_gpu_percent_peak')}%, vram={gpu.get('memory_used_mb_peak')} MB"
            if gpu.get("available")
            else "not available"
        )
        print(f"GPU peak: {gpu_status}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
