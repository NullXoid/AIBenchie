from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from aibenchie import lv7_autonomy_gate_runner as runner


def test_build_generation_command_targets_lv7_evidence_module(tmp_path):
    command = runner.build_generation_command(python_exe="python", output=tmp_path / "evidence.json")

    assert command[:3] == ["python", "-m", "lv7_autonomy.evidence"]
    assert "--output" in command


def test_run_lv7_autonomy_gate_reports_generation_failure(tmp_path, monkeypatch):
    lv7_root = tmp_path / "Lv-7"
    lv7_root.mkdir()

    def fake_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(args=["python"], returncode=1, stdout="", stderr="boom")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    result = runner.run_lv7_autonomy_gate(lv7_root=lv7_root, output=tmp_path / "evidence.json")

    assert result["ok"] is False
    assert result["verdict"] == "fail"
    assert result["stage"] == "evidence_generation"
    assert result["generation"]["returncode"] == 1
    assert result["gate"] is None


def test_run_lv7_autonomy_gate_validates_generated_evidence(tmp_path, monkeypatch):
    lv7_root = tmp_path / "Lv-7"
    lv7_root.mkdir()
    output = tmp_path / "evidence.json"

    def fake_run(command, cwd, capture_output, text, check):
        assert cwd == lv7_root.resolve()
        assert command[1:3] == ["-m", "lv7_autonomy.evidence"]
        output.write_text("{}", encoding="utf-8")
        return subprocess.CompletedProcess(args=command, returncode=0, stdout="ok", stderr="")

    def fake_run_gate(path: Path):
        assert path == output.resolve()
        return {
            "schema": "aibenchie.lv7-autonomy-gate.verdict.v1",
            "ok": True,
            "verdict": "pass",
            "summary": {"checks": 1, "pass": 1, "fail": 0, "scenario_count": 1},
            "checks": [],
        }

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    monkeypatch.setattr(runner, "run_gate", fake_run_gate)

    result = runner.run_lv7_autonomy_gate(lv7_root=lv7_root, output=output, python_exe=sys.executable)

    assert result["ok"] is True
    assert result["verdict"] == "pass"
    assert result["stage"] == "gate"
    assert result["generation"]["output"] == str(output.resolve())
    assert result["gate"]["summary"]["checks"] == 1
