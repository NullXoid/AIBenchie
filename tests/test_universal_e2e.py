from __future__ import annotations

import json
import urllib.request
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


def test_universal_e2e_web_browser_adapter_skips_without_playwright(monkeypatch, tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "id": "browser-suite",
                "lanes": {
                    "ux": {
                        "targets": [
                            {
                                "id": "web-browser",
                                "adapter": "web_browser",
                                "required": False,
                                "cwd": ".",
                                "serve_dir": "dist",
                                "path": "/",
                            }
                        ]
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(universal_e2e, "_load_playwright", lambda: None)

    result = universal_e2e.run_universal_e2e(manifest, lanes=["ux"]).as_dict()
    target = result["lanes"][0]["targets"][0]

    assert result["ok"] is True
    assert target["status"] == "skip"
    assert target["failure"] == "playwright_not_installed"


def test_universal_e2e_web_browser_adapter_fails_required_without_playwright(monkeypatch, tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "id": "browser-suite",
                "lanes": {
                    "ux": {
                        "targets": [
                            {
                                "id": "web-browser",
                                "adapter": "web_browser",
                                "required": True,
                                "cwd": ".",
                                "serve_dir": "dist",
                                "path": "/",
                            }
                        ]
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(universal_e2e, "_load_playwright", lambda: None)

    result = universal_e2e.run_universal_e2e(manifest, lanes=["ux"]).as_dict()
    target = result["lanes"][0]["targets"][0]

    assert result["ok"] is False
    assert target["status"] == "fail"
    assert target["failure"] == "playwright_not_installed"


def test_universal_e2e_web_browser_adapter_captures_artifacts(monkeypatch, tmp_path):
    site = tmp_path / "dist"
    site.mkdir()
    (site / "index.html").write_text("<main>NullXoid <button>Ops</button></main>", encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    evidence_dir = tmp_path / "evidence"
    manifest.write_text(
        json.dumps(
            {
                "id": "browser-suite",
                "lanes": {
                    "ux": {
                        "targets": [
                            {
                                "id": "web-browser",
                                "adapter": "web_browser",
                                "required": True,
                                "cwd": ".",
                                "serve_dir": "dist",
                                "path": "/",
                                "evidence_dir": str(evidence_dir),
                                "expect": [{"text": "NullXoid"}, {"text": "Ops"}],
                            }
                        ]
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    class FakeLocator:
        def wait_for(self, **_kwargs):
            return None

        @property
        def first(self):
            return self

    class FakePage:
        def goto(self, *_args, **_kwargs):
            return None

        def get_by_text(self, *_args, **_kwargs):
            return FakeLocator()

        def locator(self, *_args, **_kwargs):
            return FakeLocator()

        def screenshot(self, path, **_kwargs):
            Path(path).write_bytes(b"fake screenshot")

        def content(self):
            return "<main>NullXoid <button>Ops</button></main>"

    class FakeTracing:
        def start(self, **_kwargs):
            return None

        def stop(self, path):
            Path(path).write_bytes(b"fake trace")

    class FakeContext:
        tracing = FakeTracing()

        def new_page(self):
            return FakePage()

    class FakeBrowser:
        def new_context(self, **_kwargs):
            return FakeContext()

        def close(self):
            return None

    class FakeChromium:
        def launch(self, **_kwargs):
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()

    class FakeSyncPlaywright:
        def __call__(self):
            return self

        def __enter__(self):
            return FakePlaywright()

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(universal_e2e, "_load_playwright", lambda: FakeSyncPlaywright())

    result = universal_e2e.run_universal_e2e(manifest, lanes=["ux"]).as_dict()
    target = result["lanes"][0]["targets"][0]
    artifact = target["evidence"][-1]

    assert result["ok"] is True
    assert target["status"] == "pass"
    assert artifact["kind"] == "browser_artifact"
    assert Path(artifact["screenshot"]).exists()
    assert Path(artifact["html"]).read_text(encoding="utf-8").startswith("<main>NullXoid")
    assert Path(artifact["trace"]).exists()


def test_universal_e2e_static_server_supports_spa_fallback(tmp_path):
    site = tmp_path / "dist"
    site.mkdir()
    (site / "index.html").write_text("<main>NullXoid shell</main>", encoding="utf-8")
    server, thread, origin = universal_e2e._start_static_server(site)
    try:
        with urllib.request.urlopen(f"{origin}/nullxoid", timeout=5) as response:
            text = response.read().decode("utf-8")
    finally:
        server.shutdown()
        thread.join(timeout=5)

    assert "NullXoid shell" in text


def test_universal_e2e_cli_outputs_json_and_optional_output_file(monkeypatch, capsys, tmp_path):
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

    output_path = tmp_path / "reports" / "universal.json"
    code = aibenchie_local.main(
        [
            "--universal-e2e",
            "--universal-e2e-manifest",
            "configs/echolabs_universal_e2e.json",
            "--universal-e2e-output",
            str(output_path),
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert code == 0
    assert payload["schema"] == "aibenchie.universal-e2e.verdict.v1"
    assert file_payload == payload


def test_echolabs_manifest_has_executable_ux_targets():
    manifest_path = Path("configs/echolabs_universal_e2e.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    targets = {target["id"]: target for target in manifest["lanes"]["ux"]["targets"]}

    assert targets["web-ux"]["adapter"] == "command"
    assert targets["web-ux"]["required"] is True
    assert targets["web-ux"]["command"] == ["npm", "run", "verify:nullxoid"]
    assert targets["web-browser-ux"]["adapter"] == "web_browser"
    assert targets["web-browser-ux"]["required"] is True
    assert targets["web-browser-ux"]["path"] == "/nullxoid"
    assert targets["web-browser-ux"]["build_command"] == ["npm", "run", "build"]
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


def test_echolabs_manifest_has_executable_api_targets():
    manifest_path = Path("configs/echolabs_universal_e2e.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    targets = {target["id"]: target for target in manifest["lanes"]["api"]["targets"]}

    assert targets["hosted-backend"]["adapter"] == "http"
    assert targets["hosted-backend"]["required"] is False
    assert targets["bridgeecho-api"]["adapter"] == "command"
    assert targets["bridgeecho-api"]["required"] is True
    assert targets["bridgeecho-api"]["command"] == [
        "powershell",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        "scripts/nullbridge_release_gate.ps1",
    ]
