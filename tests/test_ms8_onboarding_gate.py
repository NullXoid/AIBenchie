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
        root / "backend" / "auth_store.py",
        "Bootstrap admin user created. username='admin'. Use the password you set in NX_BOOTSTRAP_ADMIN_PASSWORD.\n",
    )
    _write(
        root / "README.md",
        "\n".join(
            [
                "git clone http://git.echolabs.diy/EchoLabs/.NullXoid.git",
                "Permission denied (publickey)",
                "$env:NX_BOOTSTRAP_ADMIN_PASSWORD=\"<your-own-password>\"",
                ".\\echolabs.cmd start app",
                "Terminal 1",
                "Terminal 2",
            ]
        ),
    )
    _write(
        root / "frontend" / "src" / "App.jsx",
        "\n".join(
            [
                *release.MS8_REQUIRED_FRONTEND_MARKERS,
                *release.MS8_REQUIRED_FRONTEND_PROTECTED_ACTION_MARKERS,
            ]
        ),
    )
    _write(
        root / "frontend" / "src" / "components" / "StoreAssistant.jsx",
        "\n".join(release.MS8_REQUIRED_STORE_ASSISTANT_MARKERS),
    )
    _write(
        root / "frontend" / "src" / "styles.css",
        "\n".join(release.MS8_REQUIRED_STYLE_MARKERS),
    )
    _write(root / "frontend" / "package.json", '{"scripts":{"dev":"vite --host 127.0.0.1 --port 5174"}}')
    _write(
        root / "frontend" / "vite.config.js",
        'const backendTarget = process.env.NX_BACKEND_URL || "http://127.0.0.1:8090";\nexport default {server:{port: 5174}};\n',
    )
    doc = "\n".join(
        [
            *release.MS8_REQUIRED_DOC_MARKERS,
            *(marker for markers in release.MS8_REQUIRED_SPECIFIC_DOC_MARKERS.values() for marker in markers),
        ]
    )
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


def test_ms8_onboarding_validator_blocks_missing_launcher_exit_code(tmp_path):
    root = tmp_path / ".NullXoid"
    _valid_nullxoid(root)
    launcher = root / "scripts" / "echolabs.py"
    launcher.write_text(
        launcher.read_text(encoding="utf-8").replace("EXIT_PORT_CONFLICT = 3", ""),
        encoding="utf-8",
    )

    result = release.validate_ms8_onboarding(nullxoid_root=root)

    assert result["ok"] is False
    assert "scripts/echolabs.py:marker_missing:EXIT_PORT_CONFLICT = 3" in result["failures"]


def test_ms8_onboarding_validator_blocks_launcher_download_behavior(tmp_path):
    root = tmp_path / ".NullXoid"
    _valid_nullxoid(root)
    launcher = root / "scripts" / "echolabs.py"
    launcher.write_text(launcher.read_text(encoding="utf-8") + "\ndownload model\n", encoding="utf-8")

    result = release.validate_ms8_onboarding(nullxoid_root=root)

    assert result["ok"] is False
    assert "scripts/echolabs.py:forbidden_download_behavior" in result["failures"]


def test_ms8_onboarding_validator_blocks_bootstrap_password_logging(tmp_path):
    root = tmp_path / ".NullXoid"
    _valid_nullxoid(root)
    auth_store = root / "backend" / "auth_store.py"
    auth_store.write_text("username='admin' password='%s'. Change it immediately.\n", encoding="utf-8")

    result = release.validate_ms8_onboarding(nullxoid_root=root)

    assert result["ok"] is False
    assert "backend/auth_store.py:bootstrap_password_value_logged" in result["failures"]


def test_ms8_onboarding_validator_blocks_missing_start_app_readme_flow(tmp_path):
    root = tmp_path / ".NullXoid"
    _valid_nullxoid(root)
    readme = root / "README.md"
    readme.write_text("git clone ssh://forgejo@example/repo.git\nstart backend\n", encoding="utf-8")

    result = release.validate_ms8_onboarding(nullxoid_root=root)

    assert result["ok"] is False
    assert "README.md:http_clone_beginner_path_missing" in result["failures"]
    assert "README.md:start_app_quickstart_missing" in result["failures"]


def test_ms8_onboarding_validator_blocks_missing_protected_action_marker(tmp_path):
    root = tmp_path / ".NullXoid"
    _valid_nullxoid(root)
    app = root / "frontend" / "src" / "App.jsx"
    app.write_text(
        app.read_text(encoding="utf-8").replace("setStoreError(SIGN_IN_REQUIRED_MESSAGE)", ""),
        encoding="utf-8",
    )

    result = release.validate_ms8_onboarding(nullxoid_root=root)

    assert result["ok"] is False
    assert (
        "frontend/src/App.jsx:protected_action_marker_missing:setStoreError(SIGN_IN_REQUIRED_MESSAGE)"
        in result["failures"]
    )


def test_ms8_onboarding_validator_blocks_missing_no_release_movement_doc(tmp_path):
    root = tmp_path / ".NullXoid"
    _valid_nullxoid(root)
    local_prerelease = root / "docs" / "LOCAL_PRERELEASE.md"
    local_prerelease.write_text(
        local_prerelease.read_text(encoding="utf-8").replace("deploy website/home", ""),
        encoding="utf-8",
    )

    result = release.validate_ms8_onboarding(nullxoid_root=root)

    assert result["ok"] is False
    assert "docs/LOCAL_PRERELEASE.md:marker_missing:deploy website/home" in result["failures"]


def test_release_module_cli_validates_ms8_onboarding(tmp_path, capsys):
    root = tmp_path / ".NullXoid"
    _valid_nullxoid(root)

    code = release.main(["validate-ms8-onboarding", "--nullxoid-root", str(root), "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["ok"] is True
