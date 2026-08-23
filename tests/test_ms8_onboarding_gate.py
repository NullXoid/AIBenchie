from __future__ import annotations

import json
from pathlib import Path

from aibenchie import release


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _valid_nullxoid(root: Path) -> None:
    _write(
        root / "scripts" / "Elabs.py",
        "\n".join(release.MS8_REQUIRED_LAUNCHER_MARKERS),
    )
    _write(root / "Elabs.cmd", "@echo off\n")
    _write(root / "Elabs.sh", "#!/usr/bin/env sh\n")
    _write(root / "Elabs", "#!/usr/bin/env sh\n")
    _write(root / ".gitignore", ".suite/local/nullxoid/bootstrap.env\n")
    _write(
        root / "backend" / "auth_store.py",
        "Bootstrap admin user created. username='admin'. Use the password you set in NX_BOOTSTRAP_ADMIN_PASSWORD.\n",
    )
    _write(root / "backend" / "main.py", '"bootstrap"\nskip_model_setup\n"/api/setup/status"\nSETUP_STATUS_MODES\naccount_first_run\nandroid_client\nNullBridge pairing QR\n')
    _write(
        root / "README.md",
        "\n".join(
            [
                "git clone http://git.example.test/Elabs/.NullXoid.git",
                "Permission denied (publickey)",
                ".\\Elabs.cmd setup backend",
                ".\\Elabs.cmd setup app",
                ".\\Elabs.cmd setup core",
                ".\\Elabs.cmd start app",
                "./Elabs setup backend",
                "./Elabs setup app",
                "./Elabs setup core",
                "Browser App",
                "Elabs Core + Android",
                "Advanced Custom",
                "backend is always included",
                "not setup profiles",
                "does not build, install, publish, or sideload APKs",
                "http://127.0.0.1:5174/setup",
                "Backend-only does not require",
                "Android import QR",
                "NullBridge pairing QR",
                "Terminal 1",
                "Terminal 2",
            ]
        ),
    )
    _write(root / "START_HERE.md", ".\\Elabs.cmd setup backend\n.\\Elabs.cmd setup app\n.\\Elabs.cmd setup core\n./Elabs setup backend\n./Elabs setup app\n./Elabs setup core\nBrowser App\nElabs Core + Android\nAdvanced Custom\nbackend is always included\nnot setup profiles\ndoes not build, install, publish, or sideload APKs\nAndroid import QR and NullBridge pairing QR are optional\nhttp://127.0.0.1:5174/setup\n")
    _write(
        root / "docs" / "STORE_METADATA.md",
        "\n".join(release.MS8_REQUIRED_STORE_METADATA_MARKERS),
    )
    for relative, markers in release.MS8_REQUIRED_PLUG_DOC_MARKERS.items():
        _write(root / relative, "\n".join(markers))
    _write(
        root / "Elabs-pack.json",
        json.dumps(
            {
                "schema_version": "1.0",
                "id": "nullxoid",
                "display_name": ".NullXoid",
                "summary": "Local Elabs backend and browser app.",
                "type": "core_app",
                "repo_url": "http://git.example.test/Elabs/.NullXoid",
                "docs": {
                    "start_here": "START_HERE.md",
                    "commands": "docs/COMMANDS.md",
                    "security": "SECURITY.md",
                    "starter_chat_code": "docs/STARTER_CHAT_CODE_PACK.md",
                    "store_metadata": "docs/STORE_METADATA.md",
                },
                "modes": {
                    "backend": {"label": "Backend-only", "required_components": [".NullXoid"]},
                    "app": {"label": "Browser app", "required_components": [".NullXoid", "frontend"]},
                    "core": {"label": "Elabs Core", "required_components": [".NullXoid", "NullBridge"]},
                },
                "store": {"role": "core", "installable": False, "core_required": True, "stage": "prerelease"},
                "public_safe": True,
            },
            indent=2,
        ),
    )
    _write(root / "docs" / "COMMANDS.md", "Command reference\n")
    _write(root / "SECURITY.md", "Security\n")
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
    _write(root / "START_HERE.md", f"{doc}\n.\\Elabs.cmd setup\nhttp://127.0.0.1:5174/setup\n")


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
    launcher = root / "scripts" / "Elabs.py"
    launcher.write_text(
        launcher.read_text(encoding="utf-8").replace("EXIT_PORT_CONFLICT = 3", ""),
        encoding="utf-8",
    )

    result = release.validate_ms8_onboarding(nullxoid_root=root)

    assert result["ok"] is False
    assert "scripts/Elabs.py:marker_missing:EXIT_PORT_CONFLICT = 3" in result["failures"]


def test_ms8_onboarding_validator_blocks_launcher_download_behavior(tmp_path):
    root = tmp_path / ".NullXoid"
    _valid_nullxoid(root)
    launcher = root / "scripts" / "Elabs.py"
    launcher.write_text(launcher.read_text(encoding="utf-8") + "\ndownload model\n", encoding="utf-8")

    result = release.validate_ms8_onboarding(nullxoid_root=root)

    assert result["ok"] is False
    assert "scripts/Elabs.py:forbidden_download_behavior" in result["failures"]


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


def test_ms8_onboarding_validator_blocks_missing_setup_route(tmp_path):
    root = tmp_path / ".NullXoid"
    _valid_nullxoid(root)
    readme = root / "README.md"
    readme.write_text(readme.read_text(encoding="utf-8").replace("http://127.0.0.1:5174/setup", ""), encoding="utf-8")

    result = release.validate_ms8_onboarding(nullxoid_root=root)

    assert result["ok"] is False
    assert "README.md:direct_setup_url_missing" in result["failures"]


def test_ms8_onboarding_validator_blocks_missing_store_metadata(tmp_path):
    root = tmp_path / ".NullXoid"
    _valid_nullxoid(root)
    (root / "docs" / "STORE_METADATA.md").unlink()

    result = release.validate_ms8_onboarding(nullxoid_root=root)

    assert result["ok"] is False
    assert "docs/STORE_METADATA.md:missing" in result["failures"]


def test_ms8_onboarding_validator_blocks_missing_pack_metadata(tmp_path):
    root = tmp_path / ".NullXoid"
    _valid_nullxoid(root)
    (root / "Elabs-pack.json").unlink()

    result = release.validate_ms8_onboarding(nullxoid_root=root)

    assert result["ok"] is False
    assert "Elabs-pack.json:missing" in result["failures"]


def test_ms8_onboarding_validator_blocks_installable_pack_metadata(tmp_path):
    root = tmp_path / ".NullXoid"
    _valid_nullxoid(root)
    metadata_path = root / "Elabs-pack.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["store"]["installable"] = True
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    result = release.validate_ms8_onboarding(nullxoid_root=root)

    assert result["ok"] is False
    assert "Elabs-pack.json:installable_core_app" in result["failures"]


def test_ms8_onboarding_validator_blocks_pack_metadata_private_marker(tmp_path):
    root = tmp_path / ".NullXoid"
    _valid_nullxoid(root)
    metadata_path = root / "Elabs-pack.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["docs"]["unsafe"] = "C:" + "\\Users\\" + "ka" + "som" + "\\secret.txt"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    result = release.validate_ms8_onboarding(nullxoid_root=root)

    assert result["ok"] is False
    assert "Elabs-pack.json:docs_link_public_unsafe:unsafe" in result["failures"]
    assert "Elabs-pack.json:path_detail_redacted" in result["failures"]


def test_ms8_onboarding_validator_blocks_ambiguous_qr_required_path(tmp_path):
    root = tmp_path / ".NullXoid"
    _valid_nullxoid(root)
    readme = root / "README.md"
    readme.write_text(readme.read_text(encoding="utf-8").replace("Android import QR", ""), encoding="utf-8")

    result = release.validate_ms8_onboarding(nullxoid_root=root)

    assert result["ok"] is False
    assert "README.md:mode_marker_missing:Android import QR" in result["failures"]


def test_ms8_onboarding_validator_blocks_missing_setup_status_route(tmp_path):
    root = tmp_path / ".NullXoid"
    _valid_nullxoid(root)
    backend_main = root / "backend" / "main.py"
    backend_main.write_text(backend_main.read_text(encoding="utf-8").replace('"/api/setup/status"', ""), encoding="utf-8")

    result = release.validate_ms8_onboarding(nullxoid_root=root)

    assert result["ok"] is False
    assert 'backend/main.py:setup_status_marker_missing:"/api/setup/status"' in result["failures"]


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
