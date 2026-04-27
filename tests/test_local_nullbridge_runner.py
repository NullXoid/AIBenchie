from __future__ import annotations

from pathlib import Path

import pytest

import aibenchie_local
from aibenchie.local_nullbridge_runner import (
    BACKEND_IDS,
    LocalNullBridgeRunner,
    find_repo_root,
    generate_service_secrets,
    run_local_trust_path,
)


def test_generate_service_secrets_are_ephemeral_and_complete():
    first = generate_service_secrets()
    second = generate_service_secrets()
    assert set(first) == set(BACKEND_IDS)
    assert set(second) == set(BACKEND_IDS)
    assert first != second
    assert all(len(value) >= 32 for value in first.values())


def test_find_repo_root_does_not_require_private_path(monkeypatch, tmp_path):
    repo = tmp_path / "NullBridge"
    (repo / "backend" / "scripts").mkdir(parents=True)
    (repo / "backend" / "infra" / "nullbridge").mkdir(parents=True)
    (repo / "backend" / "scripts" / "nullbridge_api.py").write_text("# placeholder\n", encoding="utf-8")
    monkeypatch.setenv("AIBENCHIE_NULLBRIDGE_REPO", str(repo))
    assert find_repo_root() == repo


def test_local_nullbridge_runner_proves_allow_and_deny_without_persisting_secrets():
    repo = find_repo_root()
    if repo is None:
        pytest.skip("NullBridge repo not available")
    result = run_local_trust_path()
    assert result["ok"] is True
    assert result["allow"]["status"] == 202
    assert result["deny"]["status"] == 403
    assert result["secrets_persisted"] is False


def test_local_nullbridge_runner_temp_root_is_removed_after_stop():
    repo = find_repo_root()
    if repo is None:
        pytest.skip("NullBridge repo not available")
    with LocalNullBridgeRunner(repo) as bridge:
        temp_root = bridge.temp_root
        assert temp_root.exists()
        assert (temp_root / "infra" / "nullbridge" / "backend-registry.json").is_file()
    assert not Path(temp_root).exists()


def test_cli_trust_smoke_uses_local_runner_without_ollama(monkeypatch, capsys):
    monkeypatch.setattr(
        aibenchie_local,
        "run_local_trust_path",
        lambda: {
            "ok": True,
            "allow": {"status": 202},
            "deny": {"status": 403},
            "secrets_persisted": False,
        },
    )

    assert aibenchie_local.main(["--trust-smoke"]) == 0
    output = capsys.readouterr().out
    assert "Trust Fabric Smoke Test" in output
    assert "Allow route: HTTP 202" in output
    assert "Deny route: HTTP 403" in output
    assert "Result: PASS" in output


def test_cli_privacy_proof_uses_ephemeral_keys(monkeypatch, capsys):
    class Proof:
        def as_dict(self):
            return {
                "ok": True,
                "roundtrip_ok": True,
                "wrong_key_rejected": True,
                "tamper_rejected": True,
                "plaintext_visible_in_blob": False,
            }

    monkeypatch.setattr(aibenchie_local, "run_e2ee_storage_proof", lambda: Proof())

    assert aibenchie_local.main(["--privacy-proof"]) == 0
    output = capsys.readouterr().out
    assert "NullPrivacy E2EE Storage Proof" in output
    assert "Wrong key rejected: True" in output
    assert "Result: PASS" in output


def test_cli_ephemeral_hosted_chat_prints_without_credentials(monkeypatch, capsys):
    class Hosted:
        def as_dict(self):
            return {
                "ok": True,
                "origin": "https://app.example.test",
                "base_path": "/nullxoid",
                "helper_origin": "http://127.0.0.1:8090",
                "create_status": 200,
                "cleanup_status": 200,
                "chat": {
                    "stream_status": 200,
                    "workspace_id": "ws-1",
                    "project_id": "proj-1",
                    "model": "llama.cpp:qwen",
                },
                "failure": "",
            }

    monkeypatch.setattr(aibenchie_local, "run_hosted_nullxoid_ephemeral_chat_from_env", lambda: Hosted())

    assert aibenchie_local.main(["--hosted-nullxoid-ephemeral-chat"]) == 0
    output = capsys.readouterr().out
    assert "Hosted NullXoid Ephemeral Chat Check" in output
    assert "Model runtime: llama.cpp:qwen" in output
    assert "password" not in output.lower()
    assert "Result: PASS" in output
