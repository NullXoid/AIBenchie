from __future__ import annotations

import json

import aibenchie_local
from aibenchie.real_device_ux import (
    check_android_real_device_ux_preflight,
    emit_android_real_device_ux_proof,
    validate_real_device_ux_proof,
)


def write_proof(path, overrides=None):
    payload = {
        "schema": "aibenchie.real-device-ux-proof.v1",
        "template": False,
        "proof_id": "android-physical-smoke-001",
        "platform": "android",
        "device": {
            "manufacturer": "Samsung",
            "model": "SM-A176U",
            "os_version": "Android 16",
            "device_id_hash": "0123456789abcdef0123456789abcdef",
        },
        "app": {
            "package": "com.nullxoid.android",
            "version": "1.0.0",
            "build_type": "release",
        },
        "environment": {
            "base_url": "https://api.elabs.test/nullxoid",
            "network": "cellular",
        },
        "runtime": {
            "provider": "llamacpp",
            "model": "Qwen/Qwen3-4B-GGUF",
            "endpoint_label": "ct729-text-8081",
        },
        "workflows": [
            {
                "id": "signin",
                "name": "Native passkey sign-in",
                "status": "pass",
                "evidence": [{"kind": "manual_observation", "summary": "Signed in with Credential Manager."}],
            },
            {
                "id": "chat",
                "name": "NullXoid chat response",
                "status": "pass",
                "evidence": [{"kind": "manual_observation", "summary": "Chat returned a visible response."}],
            },
        ],
        "artifacts": [{"kind": "screenshot", "name": "chat", "sha256": "a" * 64}],
    }
    if overrides:
        payload.update(overrides)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_real_device_ux_accepts_public_safe_android_proof(tmp_path):
    proof = write_proof(tmp_path / "proof.json")

    result = validate_real_device_ux_proof(proof).as_dict()

    assert result["ok"] is True
    assert result["platform"] == "android"
    assert result["workflows"] == ["signin", "chat"]
    assert result["app"]["version"] == "1.0.0"
    assert result["environment"]["base_url"] == "https://api.elabs.test/nullxoid"
    assert result["runtime"]["model"] == "Qwen/Qwen3-4B-GGUF"


def test_real_device_ux_requires_runtime_model_for_android_chat(tmp_path):
    proof = write_proof(
        tmp_path / "proof.json",
        overrides={"runtime": {"provider": "llamacpp", "model": "", "endpoint_label": "ct729-text-8081"}},
    )

    result = validate_real_device_ux_proof(proof).as_dict()
    checks = {check["name"]: check for check in result["checks"]}

    assert result["ok"] is False
    assert checks["runtime_model_label"]["failure"] == "runtime_model_missing_for_chat"


def test_real_device_ux_rejects_template_default():
    result = validate_real_device_ux_proof("configs/aibenchie_real_device_ux.example.json").as_dict()
    checks = {check["name"]: check for check in result["checks"]}

    assert result["ok"] is False
    assert checks["not_template"]["failure"] == "template_proof_not_release_evidence"


def test_real_device_ux_rejects_raw_device_ids_and_secret_material(tmp_path):
    proof = write_proof(
        tmp_path / "proof.json",
        overrides={
            "device": {
                "manufacturer": "Samsung",
                "model": "SM-A176U",
                "os_version": "Android 16",
                "device_id_hash": "0123456789abcdef0123456789abcdef",
                "serial": "R5GYC1KBN7T",
            },
            "session_token": "eyJnotAllowed",
        },
    )

    result = validate_real_device_ux_proof(proof).as_dict()
    checks = {check["name"]: check for check in result["checks"]}

    assert result["ok"] is False
    assert "serial" in checks["raw_device_identifiers_absent"]["failure"]
    assert "secret_key_not_allowed" in checks["secret_boundary"]["failure"]


def test_real_device_ux_requires_android_signin_and_chat(tmp_path):
    proof = write_proof(tmp_path / "proof.json", overrides={"workflows": [{"id": "signin", "status": "pass", "evidence": [{"kind": "manual"}]}]})

    result = validate_real_device_ux_proof(proof).as_dict()
    checks = {check["name"]: check for check in result["checks"]}

    assert result["ok"] is False
    assert checks["android_required_workflows"]["failure"] == "workflow_missing:chat"


def test_real_device_ux_rejects_unknown_app_version(tmp_path):
    proof = write_proof(tmp_path / "proof.json", overrides={"app": {"package": "com.nullxoid.android", "version": "unknown"}})

    result = validate_real_device_ux_proof(proof).as_dict()
    checks = {check["name"]: check for check in result["checks"]}

    assert result["ok"] is False
    assert checks["app_identity"]["failure"] == "app_identity_missing"


def test_real_device_ux_cli(capsys, tmp_path):
    proof = write_proof(tmp_path / "proof.json")

    exit_code = aibenchie_local.main(["--real-device-ux-proof", str(proof), "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["proof_id"] == "android-physical-smoke-001"


def test_real_device_ux_cli_human_report_labels_runtime_and_environment(capsys, tmp_path):
    proof = write_proof(tmp_path / "proof.json")

    exit_code = aibenchie_local.main(["--real-device-ux-proof", str(proof)])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "App version: 1.0.0" in output
    assert "Base URL: https://api.elabs.test/nullxoid" in output
    assert "Network: cellular" in output
    assert "Runtime provider: llamacpp" in output
    assert "Runtime model: Qwen/Qwen3-4B-GGUF" in output
    assert "Runtime endpoint: ct729-text-8081" in output


def test_emit_android_real_device_ux_proof_hashes_device_identifier(tmp_path):
    def fake_adb(args):
        command = " ".join(args)
        if command == "get-serialno":
            return "RAW-DEVICE-123"
        if command == "shell getprop ro.product.manufacturer":
            return "Google"
        if command == "shell getprop ro.product.model":
            return "Pixel 9"
        if command == "shell getprop ro.build.version.release":
            return "16"
        if command == "shell getprop ro.build.version.sdk":
            return "36"
        if command == "shell dumpsys package com.nullxoid.android":
            return "Package [com.nullxoid.android]\n  versionName=1.2.3\n"
        raise AssertionError(f"unexpected adb command: {command}")

    output = tmp_path / "android-real-device-ux.json"
    result = emit_android_real_device_ux_proof(
        output,
        signin_passed=True,
        chat_passed=True,
        proof_id="android-real-device-test",
        runtime_provider="llamacpp",
        runtime_model="Qwen/Qwen3-4B-GGUF",
        runtime_endpoint_label="ct729-text-8081",
        adb_reader=fake_adb,
    )
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert result["ok"] is True
    assert payload["app"]["version"] == "1.2.3"
    assert payload["runtime"] == {
        "provider": "llamacpp",
        "model": "Qwen/Qwen3-4B-GGUF",
        "endpoint_label": "ct729-text-8081",
    }
    assert payload["device"]["device_id_hash"] != "RAW-DEVICE-123"
    assert "RAW-DEVICE-123" not in output.read_text(encoding="utf-8")
    assert validate_real_device_ux_proof(output).ok is True


def test_emit_android_real_device_ux_proof_can_capture_ignored_screenshot(tmp_path):
    def fake_adb(args):
        command = " ".join(args)
        if command == "get-serialno":
            return "RAW-DEVICE-123"
        if command == "shell getprop ro.product.manufacturer":
            return "Google"
        if command == "shell getprop ro.product.model":
            return "Pixel 9"
        if command == "shell getprop ro.build.version.release":
            return "16"
        if command == "shell getprop ro.build.version.sdk":
            return "36"
        if command == "shell dumpsys package com.nullxoid.android":
            return "Package [com.nullxoid.android]\n  versionName=1.2.3\n"
        raise AssertionError(f"unexpected adb command: {command}")

    output = tmp_path / "proof.json"
    artifact_dir = tmp_path / "artifacts"
    screenshot = b"\x89PNG\r\n\x1a\nfake"
    result = emit_android_real_device_ux_proof(
        output,
        signin_passed=True,
        chat_passed=True,
        proof_id="android-real-device-screen-test",
        runtime_model="Qwen/Qwen3-4B-GGUF",
        capture_screenshot=True,
        artifact_dir=artifact_dir,
        adb_reader=fake_adb,
        adb_binary_reader=lambda args: screenshot if args == ["exec-out", "screencap", "-p"] else b"",
    )
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert result["ok"] is True
    assert payload["artifacts"] == [
        {
            "kind": "screenshot",
            "name": "android-current-screen",
            "sha256": "68ee4598e64cd28eed508c333dfb14c745677f41e2b012e6256c9b138b304270",
            "byte_size": len(screenshot),
            "path": "android-real-device-screen-test-screen.png",
        }
    ]
    assert (artifact_dir / "android-real-device-screen-test-screen.png").read_bytes() == screenshot


def test_emit_android_real_device_ux_proof_requires_installed_package_version(tmp_path):
    def fake_adb(args):
        command = " ".join(args)
        if command == "get-serialno":
            return "RAW-DEVICE-123"
        if command == "shell getprop ro.product.manufacturer":
            return "Google"
        if command == "shell getprop ro.product.model":
            return "Pixel 9"
        if command == "shell getprop ro.build.version.release":
            return "16"
        if command == "shell getprop ro.build.version.sdk":
            return "36"
        if command == "shell dumpsys package com.nullxoid.android":
            return "Package [com.nullxoid.android]\n"
        raise AssertionError(f"unexpected adb command: {command}")

    try:
        emit_android_real_device_ux_proof(
            tmp_path / "proof.json",
            signin_passed=True,
            chat_passed=True,
            runtime_model="Qwen/Qwen3-4B-GGUF",
            adb_reader=fake_adb,
        )
    except RuntimeError as exc:
        assert str(exc) == "android_package_version_missing"
    else:
        raise AssertionError("expected android_package_version_missing")


def test_emit_android_real_device_ux_proof_allows_explicit_app_version_override(tmp_path):
    def fake_adb(args):
        command = " ".join(args)
        if command == "get-serialno":
            return "RAW-DEVICE-123"
        if command == "shell getprop ro.product.manufacturer":
            return "Google"
        if command == "shell getprop ro.product.model":
            return "Pixel 9"
        if command == "shell getprop ro.build.version.release":
            return "16"
        if command == "shell getprop ro.build.version.sdk":
            return "36"
        if command == "shell dumpsys package com.nullxoid.android":
            return "Package [com.nullxoid.android]\n"
        raise AssertionError(f"unexpected adb command: {command}")

    output = tmp_path / "proof.json"
    result = emit_android_real_device_ux_proof(
        output,
        signin_passed=True,
        chat_passed=True,
        app_version="1.2.3-operator",
        runtime_model="Qwen/Qwen3-4B-GGUF",
        adb_reader=fake_adb,
    )
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert result["ok"] is True
    assert payload["app"]["version"] == "1.2.3-operator"


def test_emit_android_real_device_ux_cli(capsys, monkeypatch, tmp_path):
    output = tmp_path / "proof.json"

    def fake_emit(output_path, **kwargs):
        assert output_path == str(output)
        assert kwargs["adb_serial"] == "RAW-DEVICE-123"
        assert kwargs["signin_passed"] is True
        assert kwargs["chat_passed"] is True
        assert kwargs["runtime_provider"] == "llamacpp"
        assert kwargs["runtime_model"] == "Qwen/Qwen3-4B-GGUF"
        assert kwargs["runtime_endpoint_label"] == "ct729-text-8081"
        assert kwargs["capture_screenshot"] is True
        assert kwargs["artifact_dir"] == str(tmp_path / "artifacts")
        return {
            "ok": True,
            "output": str(output),
            "proof_id": "android-cli-proof",
            "platform": "android",
            "validation": {"ok": True},
        }

    monkeypatch.setattr(aibenchie_local, "emit_android_real_device_ux_proof", fake_emit)

    exit_code = aibenchie_local.main(
        [
            "--emit-android-real-device-ux-proof",
            "--real-device-ux-output",
            str(output),
            "--real-device-ux-adb-serial",
            "RAW-DEVICE-123",
            "--real-device-ux-signin-passed",
            "--real-device-ux-chat-passed",
            "--real-device-ux-runtime-provider",
            "llamacpp",
            "--real-device-ux-runtime-model",
            "Qwen/Qwen3-4B-GGUF",
            "--real-device-ux-runtime-endpoint-label",
            "ct729-text-8081",
            "--real-device-ux-capture-screenshot",
            "--real-device-ux-artifact-dir",
            str(tmp_path / "artifacts"),
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["proof_id"] == "android-cli-proof"


def test_android_real_device_ux_preflight_reports_missing_device_without_raw_ids():
    result = check_android_real_device_ux_preflight(
        adb_reader=lambda args: "List of devices attached\n" if args == ["devices"] else "",
    ).as_dict()

    assert result["ok"] is False
    assert result["device_count"] == 0
    checks = {check["name"]: check for check in result["checks"]}
    assert checks["connected_device"]["failure"] == "adb_device_missing"
    assert "RAW-DEVICE" not in json.dumps(result)


def test_android_real_device_ux_preflight_hashes_connected_device_and_checks_package():
    def fake_adb(args):
        command = " ".join(args)
        if command == "devices":
            return "List of devices attached\nRAW-DEVICE-123\tdevice\nOFFLINE-DEVICE\toffline\n"
        if command == "shell dumpsys package com.nullxoid.android":
            return "Package [com.nullxoid.android]\n  versionName=1.2.3\n"
        raise AssertionError(f"unexpected adb command: {command}")

    result = check_android_real_device_ux_preflight(adb_reader=fake_adb).as_dict()

    assert result["ok"] is True
    assert result["device_count"] == 2
    assert result["devices"][0]["state"] == "device"
    assert result["devices"][0]["device_id_hash"] != "RAW-DEVICE-123"
    assert "RAW-DEVICE-123" not in json.dumps(result)
    assert "OFFLINE-DEVICE" not in json.dumps(result)


def test_android_real_device_ux_preflight_ignores_adb_daemon_lines():
    def fake_adb(args):
        command = " ".join(args)
        if command == "devices":
            return (
                "* daemon not running; starting now at tcp:5037\n"
                "* daemon started successfully\n"
                "List of devices attached\n"
                "RAW-DEVICE-123\tdevice\n"
            )
        if command == "shell dumpsys package com.nullxoid.android":
            return "Package [com.nullxoid.android]\n  versionName=1.2.3\n"
        raise AssertionError(f"unexpected adb command: {command}")

    result = check_android_real_device_ux_preflight(adb_reader=fake_adb).as_dict()

    assert result["ok"] is True
    assert result["device_count"] == 1
    assert result["devices"][0]["state"] == "device"


def test_android_real_device_ux_preflight_supports_selected_adb_serial_without_leaking_it():
    def fake_adb(args):
        command = " ".join(args)
        if command == "devices":
            return "List of devices attached\nFIRST\tdevice\nSECOND\tdevice\n"
        if command == "shell dumpsys package com.nullxoid.android":
            return "Package [com.nullxoid.android]\n  versionName=1.2.3\n"
        raise AssertionError(f"unexpected adb command: {command}")

    result = check_android_real_device_ux_preflight(adb_serial="SECOND", adb_reader=fake_adb).as_dict()
    checks = {check["name"]: check for check in result["checks"]}

    assert result["ok"] is True
    assert checks["selected_device"]["ok"] is True
    assert checks["selected_device"]["detail"]["selector_used"] is True
    assert "SECOND" not in json.dumps(result)


def test_android_real_device_ux_preflight_cli(capsys, monkeypatch):
    def fake_preflight(**kwargs):
        assert kwargs["package_name"] == "com.nullxoid.android"
        assert kwargs["adb_serial"] == "RAW-DEVICE-123"
        return check_android_real_device_ux_preflight(
            adb_reader=lambda args: "List of devices attached\nRAW-DEVICE-123\tdevice\n"
            if args == ["devices"]
            else "Package [com.nullxoid.android]\n  versionName=1.2.3\n"
        )

    monkeypatch.setattr(aibenchie_local, "check_android_real_device_ux_preflight", fake_preflight)

    exit_code = aibenchie_local.main(["--android-real-device-ux-preflight", "--real-device-ux-adb-serial", "RAW-DEVICE-123", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["checks"][0]["name"] == "adb_devices"
