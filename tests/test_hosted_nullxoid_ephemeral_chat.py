from __future__ import annotations

from aibenchie import hosted_nullxoid_ephemeral_chat
from aibenchie.hosted_nullxoid_chat import HostedChatResult


def test_ephemeral_chat_creates_runs_and_cleans_without_leaking_password(monkeypatch):
    requests = []

    def fake_request_json(opener, origin, base_path, path, *, method="GET", payload=None, timeout=15):
        requests.append((method, path))
        if path == "/auth/e2e/test-user":
            return 200, {
                "ok": True,
                "user_id": "user-e2e-1",
                "username": "aibenchie-e2e-1",
                "password": "generated-secret",
            }
        if path == "/auth/e2e/test-user/user-e2e-1":
            return 200, {"ok": True, "deleted": True}
        raise AssertionError(path)

    def fake_chat_check(**kwargs):
        assert kwargs["username"] == "aibenchie-e2e-1"
        assert kwargs["password"] == "generated-secret"
        return HostedChatResult(
            ok=True,
            origin=kwargs["origin"],
            base_path=kwargs["base_path"],
            login_status=200,
            stream_status=200,
            user_id="user-e2e-1",
            workspace_id="ws-1",
            project_id="proj-1",
            model="llama.cpp:qwen",
        )

    monkeypatch.setattr(hosted_nullxoid_ephemeral_chat, "request_json", fake_request_json)
    monkeypatch.setattr(hosted_nullxoid_ephemeral_chat, "run_hosted_nullxoid_chat_check", fake_chat_check)

    result = hosted_nullxoid_ephemeral_chat.run_ephemeral_hosted_nullxoid_chat_check(
        origin="https://www.echolabs.diy",
        base_path="/nullxoid",
        helper_origin="http://127.0.0.1:8090",
    )

    payload = result.as_dict()
    assert result.ok is True
    assert result.create_status == 200
    assert ("DELETE", "/auth/e2e/test-user/user-e2e-1") in requests
    assert "generated-secret" not in str(payload)


def test_ephemeral_chat_fails_when_create_route_is_unavailable(monkeypatch):
    def fake_request_json(opener, origin, base_path, path, *, method="GET", payload=None, timeout=15):
        return 404, {"detail": "not_found"}

    monkeypatch.setattr(hosted_nullxoid_ephemeral_chat, "request_json", fake_request_json)

    result = hosted_nullxoid_ephemeral_chat.run_ephemeral_hosted_nullxoid_chat_check(
        origin="https://www.echolabs.diy",
        base_path="/nullxoid",
        helper_origin="http://127.0.0.1:8090",
    )

    assert result.ok is False
    assert result.failure == "create_test_user_http_404"


def test_ephemeral_chat_cleans_up_when_chat_fails(monkeypatch):
    requests = []

    def fake_request_json(opener, origin, base_path, path, *, method="GET", payload=None, timeout=15):
        requests.append((method, path))
        if path == "/auth/e2e/test-user":
            return 200, {
                "ok": True,
                "user_id": "user-e2e-2",
                "username": "aibenchie-e2e-2",
                "password": "generated-secret",
            }
        if path == "/auth/e2e/test-user/user-e2e-2":
            return 200, {"ok": True, "deleted": True}
        raise AssertionError(path)

    def fake_chat_check(**kwargs):
        return HostedChatResult(
            ok=False,
            origin=kwargs["origin"],
            base_path=kwargs["base_path"],
            login_status=200,
            stream_status=500,
            failure="chat_stream_http_500",
        )

    monkeypatch.setattr(hosted_nullxoid_ephemeral_chat, "request_json", fake_request_json)
    monkeypatch.setattr(hosted_nullxoid_ephemeral_chat, "run_hosted_nullxoid_chat_check", fake_chat_check)

    result = hosted_nullxoid_ephemeral_chat.run_ephemeral_hosted_nullxoid_chat_check(
        origin="https://www.echolabs.diy",
        base_path="/nullxoid",
        helper_origin="http://127.0.0.1:8090",
    )

    assert result.ok is False
    assert result.failure == "chat_stream_http_500"
    assert ("DELETE", "/auth/e2e/test-user/user-e2e-2") in requests
