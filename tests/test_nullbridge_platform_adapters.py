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


def test_platform_adapter_gate_runs_nullbridge_e2e_script_with_isolated_defaults(monkeypatch, tmp_path):
    repo = tmp_path / "NullBridge"
    script = repo / "backend" / "scripts" / "nullbridge_m35_platform_adapters_e2e.py"
    script.parent.mkdir(parents=True)
    script.write_text("# test\n", encoding="utf-8")
    captured = {}
    ports = iter([19080, 19081])

    for key in (
        "NULLBRIDGE_M35_BACKEND_PORT",
        "NULLBRIDGE_M35_MANAGER_PORT",
        "NULLBRIDGE_M35_BACKEND_URL",
        "NULLBRIDGE_M35_AUTH_DB",
    ):
        monkeypatch.delenv(key, raising=False)

    def fake_run(command, *, cwd, capture_output, text, timeout, env):
        captured["command"] = command
        captured["cwd"] = cwd
        captured["timeout"] = timeout
        captured["env"] = env
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
    monkeypatch.setattr(nullbridge_platform_adapters, "_free_loopback_port", lambda: next(ports))
    monkeypatch.setattr(nullbridge_platform_adapters.subprocess, "run", fake_run)

    result = nullbridge_platform_adapters.run_from_env()

    assert result["ok"] is True
    assert captured["cwd"] == str(repo)
    assert Path(captured["command"][1]) == script
    assert captured["env"]["NULLBRIDGE_M35_BACKEND_PORT"] == "19080"
    assert captured["env"]["NULLBRIDGE_M35_MANAGER_PORT"] == "19081"
    assert captured["env"]["NULLBRIDGE_M35_BACKEND_URL"] == (
        f"http://127.0.0.1:{captured['env']['NULLBRIDGE_M35_BACKEND_PORT']}"
    )
    assert "aibenchie-m35-" in captured["env"]["NULLBRIDGE_M35_AUTH_DB"]
    assert result["isolation"]["ports"] == "isolated-loopback"
    assert result["isolation"]["authDb"] == "isolated-temp"
    assert result["m35PlatformAdapters"]["credentialLeakCheck"] == "passed"


def test_platform_adapter_gate_respects_explicit_m35_ports(monkeypatch, tmp_path):
    repo = tmp_path / "NullBridge"
    script = repo / "backend" / "scripts" / "nullbridge_m35_platform_adapters_e2e.py"
    script.parent.mkdir(parents=True)
    script.write_text("# test\n", encoding="utf-8")
    captured = {}

    monkeypatch.setenv("NULLBRIDGE_M35_BACKEND_PORT", "19980")
    monkeypatch.setenv("NULLBRIDGE_M35_MANAGER_PORT", "19981")
    monkeypatch.setenv("NULLBRIDGE_M35_BACKEND_URL", "http://127.0.0.1:19980")

    def fake_run(command, *, cwd, capture_output, text, timeout, env):
        captured["env"] = env
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(
                {
                    "ok": True,
                    "m35PlatformAdapters": {
                        "unsupportedRouteDenial": "passed",
                        "credentialLeakCheck": "passed",
                    },
                }
            ),
            stderr="",
        )

    monkeypatch.setattr(nullbridge_platform_adapters, "find_repo_root", lambda: repo)
    monkeypatch.setattr(nullbridge_platform_adapters.subprocess, "run", fake_run)

    result = nullbridge_platform_adapters.run_from_env()

    assert captured["env"]["NULLBRIDGE_M35_BACKEND_PORT"] == "19980"
    assert captured["env"]["NULLBRIDGE_M35_MANAGER_PORT"] == "19981"
    assert captured["env"]["NULLBRIDGE_M35_BACKEND_URL"] == "http://127.0.0.1:19980"
    assert result["isolation"]["ports"] == "caller-configured"
