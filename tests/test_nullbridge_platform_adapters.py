from __future__ import annotations

import json
import subprocess
from pathlib import Path

from aibenchie import nullbridge_platform_adapters


def test_parse_last_json_handles_step_logs():
    payload = nullbridge_platform_adapters._parse_last_json(
        '{"step":"one","ok":true}\n'
        '{\n'
        '  "ok": true,\n'
        '  "m35PlatformAdapters": {"website": "passed"}\n'
        '}\n'
    )

    assert payload["ok"] is True
    assert payload["m35PlatformAdapters"]["website"] == "passed"


def test_platform_adapter_gate_runs_nullbridge_e2e_script(monkeypatch, tmp_path):
    repo = tmp_path / "NullBridge"
    script = repo / "backend" / "scripts" / "nullbridge_m35_platform_adapters_e2e.py"
    script.parent.mkdir(parents=True)
    script.write_text("# test\n", encoding="utf-8")
    captured = {}

    def fake_run(command, *, cwd, capture_output, text, timeout):
        captured["command"] = command
        captured["cwd"] = cwd
        captured["timeout"] = timeout
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(
                {
                    "ok": True,
                    "m35PlatformAdapters": {
                        "website": "passed",
                        "wrapper": "passed",
                        "windows": "passed",
                        "android": "passed",
                        "unsupportedRouteDenial": "passed",
                        "credentialLeakCheck": "passed",
                    },
                    "capability": "suite.demo.echo",
                    "action": "route.approved.echo",
                    "targetRole": "diagnostics",
                }
            ),
            stderr="",
        )

    monkeypatch.setattr(nullbridge_platform_adapters, "find_repo_root", lambda: repo)
    monkeypatch.setattr(nullbridge_platform_adapters.subprocess, "run", fake_run)

    result = nullbridge_platform_adapters.run_from_env()

    assert result["ok"] is True
    assert captured["cwd"] == str(repo)
    assert Path(captured["command"][1]) == script
    assert result["m35PlatformAdapters"]["credentialLeakCheck"] == "passed"
