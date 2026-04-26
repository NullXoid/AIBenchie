from __future__ import annotations

from aibenchie import hosted_nullxoid_chat


def test_hosted_chat_check_streams_after_login(monkeypatch):
    calls = []

    def fake_request_json(opener, origin, base_path, path, *, method="GET", payload=None, timeout=15):
        calls.append((method, path))
        if path == "/auth/login":
            return 200, {"ok": True}
        if path == "/auth/me":
            return 200, {"authenticated": True, "user": {"id": "user-1", "username": "admin"}}
        if path == "/api/workspaces":
            return 200, {"active_workspace_id": "ws-1", "workspaces": [{"workspace_id": "ws-1"}]}
        if path == "/api/projects?workspace_id=ws-1":
            return 200, {"projects": [{"project_id": "proj-1", "slug": "general"}]}
        if path == "/api/models":
            return 200, {"models": [{"id": "llama.cpp:qwen"}]}
        raise AssertionError(path)

    def fake_request_stream(opener, origin, base_path, path, *, csrf, payload, timeout=45):
        assert path == "/chat/stream"
        assert csrf == "csrf-token"
        assert payload["user_id"] == "user-1"
        assert payload["workspace_id"] == "ws-1"
        assert payload["project_id"] == "proj-1"
        assert payload["model"] == "llama.cpp:qwen"
        return 200, "text/event-stream", 'event: token\ndata: {"text":"Hello"}\n\nevent: done\ndata: {}\n\n'

    monkeypatch.setattr(hosted_nullxoid_chat, "request_json", fake_request_json)
    monkeypatch.setattr(hosted_nullxoid_chat, "request_stream", fake_request_stream)
    monkeypatch.setattr(hosted_nullxoid_chat, "csrf_token", lambda jar: "csrf-token")

    result = hosted_nullxoid_chat.run_hosted_nullxoid_chat_check(
        origin="https://www.echolabs.diy",
        base_path="/nullxoid",
        username="admin",
        password="runtime-only",
    )

    assert result.ok is True
    assert result.stream_status == 200
    assert ("GET", "/api/models") in calls


def test_hosted_chat_check_fails_on_stream_http_500(monkeypatch):
    def fake_request_json(opener, origin, base_path, path, *, method="GET", payload=None, timeout=15):
        if path == "/auth/login":
            return 200, {"ok": True}
        if path == "/auth/me":
            return 200, {"authenticated": True, "user": {"id": "user-1"}}
        if path == "/api/workspaces":
            return 200, {"workspaces": [{"workspace_id": "ws-1"}]}
        if path == "/api/projects?workspace_id=ws-1":
            return 200, {"projects": [{"project_id": "proj-1"}]}
        raise AssertionError(path)

    def fake_request_stream(opener, origin, base_path, path, *, csrf, payload, timeout=45):
        return 500, "text/plain", "Internal Server Error"

    monkeypatch.setattr(hosted_nullxoid_chat, "request_json", fake_request_json)
    monkeypatch.setattr(hosted_nullxoid_chat, "request_stream", fake_request_stream)
    monkeypatch.setattr(hosted_nullxoid_chat, "csrf_token", lambda jar: "csrf-token")

    result = hosted_nullxoid_chat.run_hosted_nullxoid_chat_check(
        origin="https://www.echolabs.diy",
        base_path="/nullxoid",
        username="admin",
        password="runtime-only",
        model="llama.cpp:qwen",
    )

    assert result.ok is False
    assert result.failure == "chat_stream_http_500"
