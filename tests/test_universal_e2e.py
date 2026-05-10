from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from types import SimpleNamespace

import aibenchie_local
from aibenchie import universal_e2e


class ContractHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - stdlib hook
        if self.path == "/health":
            self._json({"ok": True, "status": "ok"})
            return
        if self.path == "/api/aibenchie/greeting":
            self._json(
                {
                    "ok": True,
                    "contract": "aibenchie.frontend-backend.v1",
                    "message": "hello from test backend",
                }
            )
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, *_args):
        return

    def _json(self, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def write_manifest(path: Path, base_url: str) -> None:
    path.write_text(
        json.dumps(
            {
                "schema": "aibenchie.universal-e2e.manifest.v1",
                "id": "fixture-suite",
                "lanes": {
                    "api": {
                        "targets": [
                            {
                                "id": "backend",
                                "adapter": "http",
                                "base_url": base_url,
                                "checks": [
                                    {"path": "/health", "expect_status": 200},
                                    {
                                        "path": "/api/aibenchie/greeting",
                                        "expect_status": 200,
                                        "expect_json": {
                                            "ok": True,
                                            "contract": "aibenchie.frontend-backend.v1",
                                        },
                                    },
                                ],
                            }
                        ]
                    },
                    "ux": {
                        "targets": [
                            {
                                "id": "manual-web",
                                "adapter": "manual",
                                "required": False,
                            }
                        ]
                    },
                },
            }
        ),
        encoding="utf-8",
    )


def test_universal_e2e_api_lane_passes(tmp_path):
    server = ThreadingHTTPServer(("127.0.0.1", 0), ContractHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        manifest = tmp_path / "manifest.json"
        write_manifest(manifest, f"http://127.0.0.1:{server.server_port}")

        result = universal_e2e.run_universal_e2e(manifest, lanes=["api"]).as_dict()

        assert result["ok"] is True
        assert result["verdict"] == "pass"
        assert result["suite_id"] == "fixture-suite"
        assert result["summary"]["targets"] == 1
        assert result["lanes"][0]["targets"][0]["evidence"][1]["path"] == "/api/aibenchie/greeting"
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_universal_e2e_missing_backend_fails_fast(tmp_path):
    manifest = tmp_path / "manifest.json"
    write_manifest(manifest, "")

    result = universal_e2e.run_universal_e2e(manifest, lanes=["api"]).as_dict()

    assert result["ok"] is False
    assert result["summary"]["fail"] == 1
    assert result["lanes"][0]["targets"][0]["failure"] == "missing_base_url"


def test_universal_e2e_command_adapter(monkeypatch, tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "id": "command-suite",
                "lanes": {
                    "ux": {
                        "targets": [
                            {
                                "id": "web-command",
                                "adapter": "command",
                                "command": ["npm", "run", "e2e"],
                                "cwd": ".",
                            }
                        ]
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    def fake_run(command, **kwargs):
        assert command == ["npm", "run", "e2e"]
        assert kwargs["cwd"] == tmp_path
        return SimpleNamespace(returncode=0, stdout="ok\n", stderr="")

    monkeypatch.setattr(universal_e2e, "_resolve_command_executable", lambda executable: executable)
    monkeypatch.setattr(universal_e2e.subprocess, "run", fake_run)

    result = universal_e2e.run_universal_e2e(manifest).as_dict()

    assert result["ok"] is True
    assert result["lanes"][0]["targets"][0]["adapter"] == "command"


def test_universal_e2e_command_adapter_reports_missing_command(monkeypatch, tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "id": "command-suite",
                "lanes": {
                    "ux": {
                        "targets": [
                            {
                                "id": "missing-command",
                                "adapter": "command",
                                "command": ["not-a-real-command"],
                                "cwd": ".",
                            }
                        ]
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    def fake_run(_command, **_kwargs):
        raise FileNotFoundError("missing executable")

    monkeypatch.setattr(universal_e2e, "_resolve_command_executable", lambda executable: executable)
    monkeypatch.setattr(universal_e2e.subprocess, "run", fake_run)

    result = universal_e2e.run_universal_e2e(manifest).as_dict()

    assert result["ok"] is False
    assert result["lanes"][0]["targets"][0]["failure"] == "command_not_found"


def test_universal_e2e_cli_outputs_json(monkeypatch, capsys):
    class FakeResult:
        def as_dict(self):
            return {
                "schema": "aibenchie.universal-e2e.verdict.v1",
                "ok": True,
                "verdict": "pass",
                "suite_id": "fixture",
                "lanes": [],
            }

    monkeypatch.setattr(aibenchie_local, "run_universal_e2e", lambda *_args, **_kwargs: FakeResult())

    code = aibenchie_local.main(
        [
            "--universal-e2e",
            "--universal-e2e-manifest",
            "configs/echolabs_universal_e2e.json",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["schema"] == "aibenchie.universal-e2e.verdict.v1"


def test_echolabs_manifest_has_executable_ux_targets():
    manifest_path = Path("configs/echolabs_universal_e2e.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    targets = {target["id"]: target for target in manifest["lanes"]["ux"]["targets"]}

    assert targets["web-ux"]["adapter"] == "command"
    assert targets["web-ux"]["required"] is True
    assert targets["web-ux"]["command"] == ["npm", "run", "verify:nullxoid"]
    assert targets["android-ux"]["adapter"] == "command"
    assert targets["android-ux"]["required"] is True
    assert targets["android-ux"]["command"] == [
        "powershell",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        "scripts/android_release_gate.ps1",
    ]
    assert targets["desktop-ux"]["adapter"] == "command"
    assert targets["desktop-ux"]["required"] is True
    assert targets["desktop-ux"]["command"] == [
        "powershell",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        "scripts/desktop_release_gate.ps1",
    ]
