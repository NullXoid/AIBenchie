from __future__ import annotations

import json

import aibenchie_local
from aibenchie.android_release_gate import ANDROID_RELEASE_VERDICT_SCHEMA, run_android_release_gate


def write_update_notes(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """# Android Update Notes

## 0.1.0-dev - 2026-05-15

### Summary

Added a release gate.

### User-Visible Changes

- Release notes are checked.

### Compatibility

- Backend contract is unchanged.

### Regression Checks

- Unit tests passed.

### Device Rollout

- S23 FE smoke checked.

### Known Issues

- None.
""",
        encoding="utf-8",
    )


def test_android_release_gate_passes_with_notes_apk_and_device_preflight(tmp_path):
    repo = tmp_path / "NullBridge"
    notes = repo / "frontend" / "app" / "UPDATE_NOTES.md"
    apk = repo / "frontend" / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"
    write_update_notes(notes)
    apk.parent.mkdir(parents=True, exist_ok=True)
    apk.write_bytes(b"debug apk bytes")

    def fake_adb(args):
        command = " ".join(args)
        if command == "devices":
            return "List of devices attached\nRAW-DEVICE-123\tdevice\n"
        if command == "shell dumpsys package com.nullxoid.nullbridge":
            return "Package [com.nullxoid.nullbridge]\n  versionName=0.1.0\n"
        raise AssertionError(f"unexpected adb command: {command}")

    output = tmp_path / "verdict.json"
    result = run_android_release_gate(
        repo=repo,
        apk=apk,
        update_notes=notes,
        package_name="com.nullxoid.nullbridge",
        base_url="http://127.0.0.1:18880/",
        output=output,
        adb_serial="RAW-DEVICE-123",
        require_device=True,
        adb_reader=fake_adb,
    )
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert result["ok"] is True
    assert result["schema"] == ANDROID_RELEASE_VERDICT_SCHEMA
    assert result["verdict"] == "pass"
    assert result["artifacts"][0]["sha256"] == "2d22e3578cd61424f7a8ace7ee78af4e49794fa56460e327776c6ca8b1e285e7"
    assert result["android"]["installed_version"] == "0.1.0"
    assert payload["ok"] is True
    assert "RAW-DEVICE-123" not in json.dumps(result)
    assert "RAW-DEVICE-123" not in output.read_text(encoding="utf-8")


def test_android_release_gate_fails_missing_required_update_note_sections(tmp_path):
    repo = tmp_path / "NullBridge"
    notes = repo / "frontend" / "app" / "UPDATE_NOTES.md"
    apk = repo / "app-debug.apk"
    notes.parent.mkdir(parents=True, exist_ok=True)
    notes.write_text("## 0.1.0-dev\n\n### Summary\n\nToo short.\n", encoding="utf-8")
    apk.write_bytes(b"apk")

    result = run_android_release_gate(
        repo=repo,
        apk=apk,
        update_notes=notes,
        package_name="com.nullxoid.nullbridge",
        base_url="https://api.echolabs.diy/nullbridge",
    )
    checks = {check["name"]: check for check in result["checks"]}

    assert result["ok"] is False
    assert result["verdict"] == "fail"
    assert checks["update_notes_required_sections"]["failure"].startswith("missing_update_note_sections:")


def test_android_release_gate_skips_device_when_not_requested(tmp_path):
    repo = tmp_path / "NullBridge"
    notes = repo / "frontend" / "app" / "UPDATE_NOTES.md"
    apk = repo / "app-debug.apk"
    write_update_notes(notes)
    apk.write_bytes(b"apk")

    result = run_android_release_gate(
        repo=repo,
        apk=apk,
        update_notes=notes,
        package_name="com.nullxoid.nullbridge",
        base_url="https://api.echolabs.diy/nullbridge",
    )
    checks = {check["name"]: check for check in result["checks"]}

    assert result["ok"] is True
    assert result["verdict"] == "pass"
    assert checks["device_preflight"]["status"] == "skip"
    assert result["android"]["device_checked"] is False


def test_android_release_gate_warns_when_optional_device_preflight_fails(tmp_path):
    repo = tmp_path / "NullBridge"
    notes = repo / "frontend" / "app" / "UPDATE_NOTES.md"
    apk = repo / "app-debug.apk"
    write_update_notes(notes)
    apk.write_bytes(b"apk")

    result = run_android_release_gate(
        repo=repo,
        apk=apk,
        update_notes=notes,
        package_name="com.nullxoid.nullbridge",
        base_url="https://api.echolabs.diy/nullbridge",
        adb_serial="RAW-DEVICE-123",
        require_device=False,
        adb_reader=lambda args: "List of devices attached\n" if args == ["devices"] else "",
    )

    assert result["ok"] is True
    assert result["verdict"] == "warn"
    assert "RAW-DEVICE-123" not in json.dumps(result)


def test_android_release_gate_cli(capsys, monkeypatch, tmp_path):
    output = tmp_path / "verdict.json"

    def fake_gate(**kwargs):
        assert kwargs["repo"] == "C:/repo"
        assert kwargs["apk"] == "app.apk"
        assert kwargs["update_notes"] == "UPDATE_NOTES.md"
        assert kwargs["package_name"] == "com.nullxoid.nullbridge"
        assert kwargs["base_url"] == "http://127.0.0.1:18880/"
        assert kwargs["output"] == str(output)
        assert kwargs["adb_serial"] == "RAW-DEVICE-123"
        assert kwargs["require_device"] is True
        return {
            "schema": ANDROID_RELEASE_VERDICT_SCHEMA,
            "ok": True,
            "verdict": "pass",
            "repo": {"name": "repo", "branch": "main", "commit": "abcdef123456"},
            "android": {"package": "com.nullxoid.nullbridge", "base_url": "http://127.0.0.1:18880/", "device_checked": True},
            "notes": {"latest_entry": "0.1.0-dev"},
            "artifacts": [],
            "checks": [],
        }

    monkeypatch.setattr(aibenchie_local, "run_android_release_gate", fake_gate)

    exit_code = aibenchie_local.main(
        [
            "--android-release-gate",
            "--android-release-repo",
            "C:/repo",
            "--android-release-apk",
            "app.apk",
            "--android-release-update-notes",
            "UPDATE_NOTES.md",
            "--android-release-package",
            "com.nullxoid.nullbridge",
            "--android-release-base-url",
            "http://127.0.0.1:18880/",
            "--android-release-output",
            str(output),
            "--android-release-adb-serial",
            "RAW-DEVICE-123",
            "--android-release-require-device",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["verdict"] == "pass"
