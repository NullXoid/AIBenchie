from __future__ import annotations

import json
from pathlib import Path

from aibenchie import release


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _valid_nullxoid(root: Path) -> None:
    _write(
        root / "scripts" / "echolabs.py",
        "\n".join(release.MS8_REQUIRED_LAUNCHER_MARKERS),
    )
    _write(root / "echolabs.cmd", "@echo off\n")
    _write(root / "echolabs.sh", "#!/usr/bin/env sh\n")
    _write(root / "echolabs", "#!/usr/bin/env sh\n")
    _write(
        root / "frontend" / "src" / "App.jsx",
        "\n".join(release.MS8_REQUIRED_FRONTEND_MARKERS),
    )
    _write(
        root / "frontend" / "src" / "styles.css",
        ".setup-onboarding\n.setup-reminder-card\n.starter-pack-cta\n.setup-checklist\n",
    )
    _write(root / "frontend" / "package.json", '{"scripts":{"dev":"vite --host 127.0.0.1 --port 5174"}}')
    _write(
        root / "frontend" / "vite.config.js",
        'const backendTarget = process.env.NX_BACKEND_URL || "http://127.0.0.1:8090";\nexport default {server:{port: 5174}};\n',
    )
    doc = "EchoLabs Core is .NullXoid + NullBridge\nAIBenchie is validator\n127.0.0.1:8090\n127.0.0.1:5174\n"
    for relative in release.MS8_REQUIRED_DOCS:
        _write(root / relative, doc)


def test_ms8_onboarding_validator_accepts_valid_contract(tmp_path):
    root = tmp_path / ".NullXoid"
    _valid_nullxoid(root)

    result = release.validate_ms8_onboarding(nullxoid_root=root)

    assert result["ok"] is True
    assert result["aibenchie_verdict"] == "pass"


def test_ms8_onboarding_validator_blocks_stale_guest_marker(tmp_path):
    root = tmp_path / ".NullXoid"
    _valid_nullxoid(root)
    app = root / "frontend" / "src" / "App.jsx"
    app.write_text(app.read_text(encoding="utf-8") + "\nSign out / Exit\n", encoding="utf-8")

    result = release.validate_ms8_onboarding(nullxoid_root=root)

    assert result["ok"] is False
    assert "frontend/src/App.jsx:stale_marker:Sign out / Exit" in result["failures"]


def test_release_module_cli_validates_ms8_onboarding(tmp_path, capsys):
    root = tmp_path / ".NullXoid"
    _valid_nullxoid(root)

    code = release.main(["validate-ms8-onboarding", "--nullxoid-root", str(root), "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["ok"] is True
