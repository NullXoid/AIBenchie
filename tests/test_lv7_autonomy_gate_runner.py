from __future__ import annotations

import sys
from pathlib import Path

from aibenchie import lv7_autonomy_gate_runner as runner
from aibenchie.resource_telemetry import MonitoredCommandResult


def test_build_generation_command_targets_lv7_evidence_module(tmp_path):
    command = runner.build_generation_command(python_exe="python", output=tmp_path / "evidence.json")

    assert command[:3] == ["python", "-m", "lv7_autonomy.evidence"]
    assert "--output" in command


def test_run_lv7_autonomy_gate_reports_generation_failure(tmp_path, monkeypatch):
    lv7_root = tmp_path / "Lv-7"
    lv7_root.mkdir()

    def fake_run(*_args, **_kwargs):
        return MonitoredCommandResult(
            command=["python"],
            cwd=str(lv7_root),
            returncode=1,
            stdout="",
            stderr="boom",
            resource_telemetry=telemetry(),
        )

    monkeypatch.setattr(runner, "run_monitored_command", fake_run)

    result = runner.run_lv7_autonomy_gate(
        lv7_root=lv7_root,
        output=tmp_path / "evidence.json",
        telemetry_output=tmp_path / "telemetry.json",
    )

    assert result["ok"] is False
    assert result["verdict"] == "fail"
    assert result["stage"] == "evidence_generation"
    assert result["generation"]["returncode"] == 1
    assert result["generation"]["resource_telemetry_output"].endswith("telemetry.json")
    assert result["gate"] is None


def test_run_lv7_autonomy_gate_validates_generated_evidence(tmp_path, monkeypatch):
    lv7_root = tmp_path / "Lv-7"
    lv7_root.mkdir()
    output = tmp_path / "evidence.json"

    def fake_run(command, cwd, sample_interval_seconds):
        assert cwd == lv7_root.resolve()
        assert command[1:3] == ["-m", "lv7_autonomy.evidence"]
        assert sample_interval_seconds == 0.25
        output.write_text("{}", encoding="utf-8")
        return MonitoredCommandResult(
            command=command,
            cwd=str(cwd),
            returncode=0,
            stdout="ok",
            stderr="",
            resource_telemetry=telemetry(),
        )

    def fake_run_gate(path: Path):
        assert path == output.resolve()
        return {
            "schema": "aibenchie.lv7-autonomy-gate.verdict.v1",
            "ok": True,
            "verdict": "pass",
            "summary": {"checks": 1, "pass": 1, "fail": 0, "scenario_count": 1},
            "checks": [],
        }

    monkeypatch.setattr(runner, "run_monitored_command", fake_run)
    monkeypatch.setattr(runner, "run_gate", fake_run_gate)

    telemetry_output = tmp_path / "telemetry.json"
    result = runner.run_lv7_autonomy_gate(
        lv7_root=lv7_root,
        output=output,
        telemetry_output=telemetry_output,
        python_exe=sys.executable,
        telemetry_sample_interval=0.25,
    )

    assert result["ok"] is True
    assert result["verdict"] == "pass"
    assert result["stage"] == "gate"
    assert result["generation"]["output"] == str(output.resolve())
    assert result["generation"]["resource_telemetry_output"] == str(telemetry_output.resolve())
    assert result["generation"]["resource_telemetry_summary"]["cpu"]["system_percent_peak"] == 10.0
    assert result["gate"]["summary"]["checks"] == 1


def telemetry() -> dict:
    return {
        "schema": "aibenchie.resource-telemetry.v1",
        "command": ["python"],
        "cwd": "",
        "started_at": "2026-05-12T12:00:00Z",
        "finished_at": "2026-05-12T12:00:01Z",
        "duration_seconds": 1.0,
        "sample_interval_seconds": 0.25,
        "sample_count": 1,
        "summary": {
            "duration_seconds": 1.0,
            "sample_count": 1,
            "cpu": {"process_percent_peak": 5.0, "system_percent_peak": 10.0, "process_seconds_total": 0.2},
            "memory": {"process_rss_mb_peak": 50.0, "system_used_percent_peak": 60.0},
            "gpu": {"available": False, "utilization_gpu_percent_peak": None, "memory_used_mb_peak": None},
        },
        "samples": [],
    }
