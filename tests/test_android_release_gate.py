from __future__ import annotations

import json

import aibenchie_local
from aibenchie.android_release_gate import ANDROID_RELEASE_VERDICT_SCHEMA, run_android_release_gate
from aibenchie.android_release_device_proof import ANDROID_RELEASE_DEVICE_PROOF_SCHEMA, emit_android_release_device_proof

VALID_FINGERPRINT = "AA:11:22:33:44:55:66:77:88:99:AA:BB:CC:DD:EE:FF:00:11:22:33:44:55:66:77:88:99:AA:BB:CC:DD:EE:FF"


def test_android_release_device_proof_redacts_raw_serial(tmp_path):
    output = tmp_path / "proof.json"

    def fake_adb(args):
        command = " ".join(args)
        if command == "devices -l":
            return "List of devices attached\nRAW-DEVICE-123 device product:r11q model:SM_S711U device:r11q transport_id:1\n"
        if command == "get-serialno":
            return "RAW-DEVICE-123"
        if command == "shell getprop ro.product.manufacturer":
            return "samsung"
        if command == "shell getprop ro.product.model":
            return "SM-S711U"
        if command == "shell getprop ro.build.version.release":
            return "15"
        if command == "shell getprop ro.build.version.sdk":
            return "35"
        if command == "shell dumpsys package com.nullxoid.android":
            return "Package [com.nullxoid.android]\n  versionCode=42 minSdk=26 targetSdk=35\n  versionName=0.2.0-alpha.42\n"
        raise AssertionError(f"unexpected adb command: {command}")

    payload = emit_android_release_device_proof(
        output=output,
        app_id="nullxoid_android",
        package_name="com.nullxoid.android",
        device_alias="s23fe",
        verdict_path="release/aibenchie/nullxoid-android-release-verdict.json",
        adb_reader=fake_adb,
    )
    text = output.read_text(encoding="utf-8")

    assert payload["schema"] == ANDROID_RELEASE_DEVICE_PROOF_SCHEMA
    assert payload["install_state"] == "installed"
    assert payload["app_version"] == "0.2.0-alpha.42"
    assert payload["version_code"] == "42"
    assert "RAW-DEVICE-123" not in text


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
        app_id="nullbridge_android",
        app_version="0.1.0",
        version_code="12",
        signing_fingerprint_sha256=VALID_FINGERPRINT,
        expected_signing_fingerprint=VALID_FINGERPRINT,
        expected_signing_fingerprint_source="test",
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
        base_url="https://api.elabs.test/nullbridge",
        app_id="nullbridge_android",
        app_version="0.1.0",
        version_code="12",
        signing_fingerprint_sha256=VALID_FINGERPRINT,
        expected_signing_fingerprint=VALID_FINGERPRINT,
        expected_signing_fingerprint_source="test",
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
        base_url="https://api.elabs.test/nullbridge",
        app_id="nullbridge_android",
        app_version="0.1.0",
        version_code="12",
        signing_fingerprint_sha256=VALID_FINGERPRINT,
        expected_signing_fingerprint=VALID_FINGERPRINT,
        expected_signing_fingerprint_source="test",
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
        base_url="https://api.elabs.test/nullbridge",
        app_id="nullbridge_android",
        app_version="0.1.0",
        version_code="12",
        signing_fingerprint_sha256=VALID_FINGERPRINT,
        expected_signing_fingerprint=VALID_FINGERPRINT,
        expected_signing_fingerprint_source="test",
        adb_serial="RAW-DEVICE-123",
        require_device=False,
        adb_reader=lambda args: "List of devices attached\n" if args == ["devices"] else "",
    )

    assert result["ok"] is False
    assert result["verdict"] == "manual-review"
    assert "RAW-DEVICE-123" not in json.dumps(result)


def test_android_release_gate_blocks_publish_without_device_proof(tmp_path):
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
        base_url="https://api.elabs.test/nullbridge",
        app_id="nullbridge_android",
        app_version="0.1.0",
        version_code="12",
        signing_fingerprint_sha256=VALID_FINGERPRINT,
        expected_signing_fingerprint=VALID_FINGERPRINT,
        expected_signing_fingerprint_source="test",
        publish_action="latest-debug",
    )
    checks = {check["name"]: check for check in result["checks"]}

    assert result["ok"] is False
    assert result["verdict"] == "fail"
    assert checks["primary_device_proof"]["failure"] == "primary_device_proof_missing"
    assert checks["secondary_device_proof"]["failure"] == "secondary_device_proof_missing"


def test_android_release_gate_blocks_missing_expected_signing_fingerprint(tmp_path):
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
        base_url="https://api.elabs.test/nullbridge",
        app_id="nullbridge_android",
        app_version="0.1.0",
        version_code="12",
        signing_fingerprint_sha256=VALID_FINGERPRINT,
    )
    checks = {check["name"]: check for check in result["checks"]}

    assert result["ok"] is False
    assert result["verdict"] == "fail"
    assert checks["expected_signing_fingerprint"]["failure"] == "expected_signing_fingerprint_missing_or_invalid"


def test_android_release_gate_accepts_nullbridge_publish_with_device_proofs(tmp_path):
    repo = tmp_path / "NullBridge"
    notes = repo / "frontend" / "app" / "UPDATE_NOTES.md"
    apk = repo / "release" / "NullBridge-debug.apk"
    primary = repo / ".suite" / "local" / "aibenchie" / "device-proof-s23fe.json"
    secondary = repo / ".suite" / "local" / "aibenchie" / "device-proof-a17.json"
    write_update_notes(notes)
    apk.parent.mkdir(parents=True, exist_ok=True)
    apk.write_bytes(b"apk")
    primary.parent.mkdir(parents=True, exist_ok=True)
    primary.write_text(json.dumps({"model": "S23 FE", "serial_alias": "s23fe", "package_name": "com.nullxoid.nullbridge"}), encoding="utf-8")
    secondary.write_text(json.dumps({"model": "A17", "serial_alias": "a17", "package_name": "com.nullxoid.nullbridge"}), encoding="utf-8")

    result = run_android_release_gate(
        repo=repo,
        apk=apk,
        update_notes=notes,
        package_name="com.nullxoid.nullbridge",
        base_url="https://api.elabs.test/nullbridge",
        app_id="nullbridge_android",
        app_version="0.1.0",
        version_code="12",
        signing_fingerprint_sha256=VALID_FINGERPRINT,
        expected_signing_fingerprint=VALID_FINGERPRINT,
        expected_signing_fingerprint_source="test",
        primary_device_proof=primary,
        secondary_device_proof=secondary,
        publish_action="latest-debug",
    )

    assert result["ok"] is True
    assert result["verdict"] == "pass"
    assert result["android"]["app_id"] == "nullbridge_android"


def test_android_release_gate_accepts_nullxoid_android_with_device_proofs(tmp_path):
    repo = tmp_path / "NullXoidAndroid"
    notes = repo / "release" / "UPDATE_NOTES.md"
    apk = repo / "release" / "NullXoidAndroid-debug.apk"
    primary = repo / ".suite" / "local" / "aibenchie" / "device-proof-s23fe.json"
    secondary = repo / ".suite" / "local" / "aibenchie" / "device-proof-a17.json"
    write_update_notes(notes)
    apk.parent.mkdir(parents=True, exist_ok=True)
    apk.write_bytes(b"apk")
    primary.parent.mkdir(parents=True, exist_ok=True)
    primary.write_text(json.dumps({"model": "S23 FE", "serial_alias": "s23fe", "package_name": "com.nullxoid.android"}), encoding="utf-8")
    secondary.write_text(json.dumps({"model": "A17", "serial_alias": "a17", "package_name": "com.nullxoid.android"}), encoding="utf-8")

    result = run_android_release_gate(
        repo=repo,
        apk=apk,
        update_notes=notes,
        package_name="com.nullxoid.android",
        base_url="https://api.elabs.test/nullxoid",
        app_id="nullxoid_android",
        app_version="0.2.0-alpha.1",
        version_code="98",
        signing_fingerprint_sha256=VALID_FINGERPRINT,
        expected_signing_fingerprint=VALID_FINGERPRINT,
        expected_signing_fingerprint_source="test",
        primary_device_proof=primary,
        secondary_device_proof=secondary,
        publish_action="publish",
    )

    assert result["ok"] is True
    assert result["verdict"] == "pass"
    assert result["android"]["app_id"] == "nullxoid_android"


def test_android_release_gate_cli(capsys, monkeypatch, tmp_path):
    output = tmp_path / "verdict.json"

    def fake_gate(**kwargs):
        assert kwargs["repo"] == "C:/repo"
        assert kwargs["apk"] == "app.apk"
        assert kwargs["update_notes"] == "UPDATE_NOTES.md"
        assert kwargs["package_name"] == "com.nullxoid.nullbridge"
        assert kwargs["app_id"] == "nullbridge_android"
        assert kwargs["app_version"] == "0.1.0"
        assert kwargs["version_code"] == "12"
        assert kwargs["signing_fingerprint_sha256"] == VALID_FINGERPRINT
        assert kwargs["expected_signing_fingerprint"] == VALID_FINGERPRINT
        assert kwargs["primary_device_proof"] == "primary.json"
        assert kwargs["secondary_device_proof"] == "secondary.json"
        assert kwargs["publish_action"] == "latest-debug"
        assert kwargs["base_url"] == "http://127.0.0.1:18880/"
        assert kwargs["output"] == str(output)
        assert kwargs["adb_serial"] == "RAW-DEVICE-123"
        assert kwargs["require_device"] is True
        return {
            "schema": ANDROID_RELEASE_VERDICT_SCHEMA,
            "ok": True,
            "verdict": "pass",
            "repo": {"name": "repo", "branch": "main", "commit": "abcdef123456"},
            "android": {"app_id": "nullbridge_android", "package": "com.nullxoid.nullbridge", "app_version": "0.1.0", "version_code": "12", "base_url": "http://127.0.0.1:18880/", "device_checked": True},
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
            "--android-release-app-id",
            "nullbridge_android",
            "--android-release-app-version",
            "0.1.0",
            "--android-release-version-code",
            "12",
            "--android-release-signing-fingerprint",
            VALID_FINGERPRINT,
            "--android-release-expected-fingerprint",
            VALID_FINGERPRINT,
            "--android-release-primary-device-proof",
            "primary.json",
            "--android-release-secondary-device-proof",
            "secondary.json",
            "--android-release-publish-action",
            "latest-debug",
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
