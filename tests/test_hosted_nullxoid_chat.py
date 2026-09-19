from __future__ import annotations

from aibenchie import hosted_nullxoid_chat


def test_stream_arrival_diagnostic_records_events_without_response_text():
    import io
    from types import SimpleNamespace

    wire = b'event: token\ndata: {"delta":"Hello"}\n\nevent: token\ndata: {"delta":" world"}\n\nevent: done\ndata: {}\n\n'

    class Response(io.BytesIO):
        status = 200
        headers = {"content-type": "text/event-stream"}

    def opener(request, timeout):
        return Response(wire)

    timings = []
    result = hosted_nullxoid_chat.request_stream(
        SimpleNamespace(open=opener), "https://example.test", "", "/chat/stream",
        csrf="synthetic", payload={}, event_timings=timings,
    )
    assert result == (200, "text/event-stream", wire.decode())
    assert [item["event"] for item in timings] == ["token", "token", "done"]
    assert [item["delta_chars"] for item in timings] == [5, 6, 0]
    assert all(set(item) == {"event", "elapsed_ms", "delta_chars"} for item in timings)
    assert [item["elapsed_ms"] for item in timings] == sorted(item["elapsed_ms"] for item in timings)


GOOD_NOTIFICATION_EVENTS = (
    'event: notification_snapshot\ndata: {"notifications":[]}\n\n'
    'event: resource_status\ndata: {"ok":true,"used_percent":12}\n\n'
)


def operations_status_payload(**overrides):
    payload = {
        "ok": True,
        "backend": {"service": "wrapper_backend", "status": "ok"},
        "deploy": {"mount": "/nullxoid/", "canonical_origin": "https://app.example.test"},
        "runtime": {"provider": "local_runtime", "status": "ok"},
        "resources": {"free_gb": 18.0, "used_percent": 22.0},
        "notifications": {"status": "ok", "connected": True},
        "nullbridge": {"credentials_exposed": False},
    }
    payload.update(overrides)
    return payload


def notification_list_payload(**overrides):
    payload = {"ok": True, "notifications": []}
    payload.update(overrides)
    return payload


def good_notification_events(opener, origin, base_path, path, *, timeout=15):
    assert path == "/api/notifications/events?once=1"
    return 200, "text/event-stream", GOOD_NOTIFICATION_EVENTS


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
        if path == "/api/operations/status":
            return 200, operations_status_payload()
        if path == "/api/notifications?limit=10":
            return 200, notification_list_payload()
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
    monkeypatch.setattr(hosted_nullxoid_chat, "request_sse_once", good_notification_events)
    monkeypatch.setattr(hosted_nullxoid_chat, "csrf_token", lambda jar: "csrf-token")

    result = hosted_nullxoid_chat.run_hosted_nullxoid_chat_check(
        origin="https://app.example.test",
        base_path="/nullxoid",
        username="admin",
        password="runtime-only",
    )

    assert result.ok is True
    assert result.stream_status == 200
    assert result.operations_status == 200
    assert result.notification_status == 200
    assert result.notification_stream_status == 200
    assert result.operations_summary["backend_service"] == "wrapper_backend"
    assert result.operations_summary["resource_free_gb"] == 18.0
    assert result.notification_summary["resource_status_seen"] is True
    assert ("GET", "/api/models") in calls
    assert ("GET", "/api/operations/status") in calls
    assert ("GET", "/api/notifications?limit=10") in calls


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
        if path == "/api/operations/status":
            return 200, operations_status_payload()
        if path == "/api/notifications?limit=10":
            return 200, notification_list_payload()
        raise AssertionError(path)

    def fake_request_stream(opener, origin, base_path, path, *, csrf, payload, timeout=45):
        return 500, "text/plain", "Internal Server Error"

    monkeypatch.setattr(hosted_nullxoid_chat, "request_json", fake_request_json)
    monkeypatch.setattr(hosted_nullxoid_chat, "request_stream", fake_request_stream)
    monkeypatch.setattr(hosted_nullxoid_chat, "request_sse_once", good_notification_events)
    monkeypatch.setattr(hosted_nullxoid_chat, "csrf_token", lambda jar: "csrf-token")

    result = hosted_nullxoid_chat.run_hosted_nullxoid_chat_check(
        origin="https://app.example.test",
        base_path="/nullxoid",
        username="admin",
        password="runtime-only",
        model="llama.cpp:qwen",
    )

    assert result.ok is False
    assert result.failure == "chat_stream_http_500"


def test_hosted_chat_check_fails_on_stream_challenge_html(monkeypatch):
    def fake_request_json(opener, origin, base_path, path, *, method="GET", payload=None, timeout=15):
        if path == "/auth/login":
            return 200, {"ok": True}
        if path == "/auth/me":
            return 200, {"authenticated": True, "user": {"id": "user-1"}}
        if path == "/api/workspaces":
            return 200, {"workspaces": [{"workspace_id": "ws-1"}]}
        if path == "/api/projects?workspace_id=ws-1":
            return 200, {"projects": [{"project_id": "proj-1"}]}
        if path == "/api/operations/status":
            return 200, operations_status_payload()
        if path == "/api/notifications?limit=10":
            return 200, notification_list_payload()
        raise AssertionError(path)

    def fake_request_stream(opener, origin, base_path, path, *, csrf, payload, timeout=45):
        return 403, "text/html", '<script src="https://challenges.cloudflare.com/challenge"></script>'

    monkeypatch.setattr(hosted_nullxoid_chat, "request_json", fake_request_json)
    monkeypatch.setattr(hosted_nullxoid_chat, "request_stream", fake_request_stream)
    monkeypatch.setattr(hosted_nullxoid_chat, "request_sse_once", good_notification_events)
    monkeypatch.setattr(hosted_nullxoid_chat, "csrf_token", lambda jar: "csrf-token")

    result = hosted_nullxoid_chat.run_hosted_nullxoid_chat_check(
        origin="https://app.example.test",
        base_path="/nullxoid",
        username="admin",
        password="runtime-only",
        model="llama.cpp:qwen",
    )

    assert result.ok is False
    assert result.failure == "chat_stream_challenged"


def test_hosted_chat_check_fails_when_notifications_return_html(monkeypatch):
    def fake_request_json(opener, origin, base_path, path, *, method="GET", payload=None, timeout=15):
        if path == "/auth/login":
            return 200, {"ok": True}
        if path == "/auth/me":
            return 200, {"authenticated": True, "user": {"id": "user-1"}}
        if path == "/api/workspaces":
            return 200, {"workspaces": [{"workspace_id": "ws-1"}]}
        if path == "/api/projects?workspace_id=ws-1":
            return 200, {"projects": [{"project_id": "proj-1"}]}
        if path == "/api/operations/status":
            return 200, operations_status_payload()
        if path == "/api/notifications?limit=10":
            return 403, "<html>Forbidden</html>"
        raise AssertionError(path)

    monkeypatch.setattr(hosted_nullxoid_chat, "request_json", fake_request_json)
    monkeypatch.setattr(hosted_nullxoid_chat, "csrf_token", lambda jar: "csrf-token")

    result = hosted_nullxoid_chat.run_hosted_nullxoid_chat_check(
        origin="https://app.example.test",
        base_path="/nullxoid",
        username="admin",
        password="runtime-only",
        model="llama.cpp:qwen",
    )

    assert result.ok is False
    assert result.failure == "notifications_returned_html"


def test_hosted_chat_check_fails_when_notification_events_are_challenged(monkeypatch):
    def fake_request_json(opener, origin, base_path, path, *, method="GET", payload=None, timeout=15):
        if path == "/auth/login":
            return 200, {"ok": True}
        if path == "/auth/me":
            return 200, {"authenticated": True, "user": {"id": "user-1"}}
        if path == "/api/workspaces":
            return 200, {"workspaces": [{"workspace_id": "ws-1"}]}
        if path == "/api/projects?workspace_id=ws-1":
            return 200, {"projects": [{"project_id": "proj-1"}]}
        if path == "/api/operations/status":
            return 200, operations_status_payload()
        if path == "/api/notifications?limit=10":
            return 200, notification_list_payload()
        raise AssertionError(path)

    def fake_request_sse_once(opener, origin, base_path, path, *, timeout=15):
        return 403, "text/html", '<script src="https://challenges.cloudflare.com/challenge"></script>'

    monkeypatch.setattr(hosted_nullxoid_chat, "request_json", fake_request_json)
    monkeypatch.setattr(hosted_nullxoid_chat, "request_sse_once", fake_request_sse_once)
    monkeypatch.setattr(hosted_nullxoid_chat, "csrf_token", lambda jar: "csrf-token")

    result = hosted_nullxoid_chat.run_hosted_nullxoid_chat_check(
        origin="https://app.example.test",
        base_path="/nullxoid",
        username="admin",
        password="runtime-only",
        model="llama.cpp:qwen",
    )

    assert result.ok is False
    assert result.failure == "notification_events_challenged"


def test_hosted_chat_check_fails_when_notification_events_miss_resource_status(monkeypatch):
    def fake_request_json(opener, origin, base_path, path, *, method="GET", payload=None, timeout=15):
        if path == "/auth/login":
            return 200, {"ok": True}
        if path == "/auth/me":
            return 200, {"authenticated": True, "user": {"id": "user-1"}}
        if path == "/api/workspaces":
            return 200, {"workspaces": [{"workspace_id": "ws-1"}]}
        if path == "/api/projects?workspace_id=ws-1":
            return 200, {"projects": [{"project_id": "proj-1"}]}
        if path == "/api/operations/status":
            return 200, operations_status_payload()
        if path == "/api/notifications?limit=10":
            return 200, notification_list_payload()
        raise AssertionError(path)

    def fake_request_sse_once(opener, origin, base_path, path, *, timeout=15):
        return 200, "text/event-stream", 'event: notification_snapshot\ndata: {"notifications":[]}\n\n'

    monkeypatch.setattr(hosted_nullxoid_chat, "request_json", fake_request_json)
    monkeypatch.setattr(hosted_nullxoid_chat, "request_sse_once", fake_request_sse_once)
    monkeypatch.setattr(hosted_nullxoid_chat, "csrf_token", lambda jar: "csrf-token")

    result = hosted_nullxoid_chat.run_hosted_nullxoid_chat_check(
        origin="https://app.example.test",
        base_path="/nullxoid",
        username="admin",
        password="runtime-only",
        model="llama.cpp:qwen",
    )

    assert result.ok is False
    assert result.failure == "notification_events_missing_resource_status"


def test_hosted_chat_check_fails_when_models_route_returns_html(monkeypatch):
    def fake_request_json(opener, origin, base_path, path, *, method="GET", payload=None, timeout=15):
        if path == "/auth/login":
            return 200, {"ok": True}
        if path == "/auth/me":
            return 200, {"authenticated": True, "user": {"id": "user-1"}}
        if path == "/api/workspaces":
            return 200, {"workspaces": [{"workspace_id": "ws-1"}]}
        if path == "/api/projects?workspace_id=ws-1":
            return 200, {"projects": [{"project_id": "proj-1"}]}
        if path == "/api/models":
            return 403, "<html>Forbidden</html>"
        raise AssertionError(path)

    monkeypatch.setattr(hosted_nullxoid_chat, "request_json", fake_request_json)
    monkeypatch.setattr(hosted_nullxoid_chat, "csrf_token", lambda jar: "csrf-token")

    result = hosted_nullxoid_chat.run_hosted_nullxoid_chat_check(
        origin="https://app.example.test",
        base_path="/nullxoid",
        username="admin",
        password="runtime-only",
    )

    assert result.ok is False
    assert result.failure == "models_returned_html"


def test_hosted_chat_check_fails_when_login_is_challenged(monkeypatch):
    def fake_request_json(opener, origin, base_path, path, *, method="GET", payload=None, timeout=15):
        if path == "/auth/login":
            return 403, '<script src="https://challenges.cloudflare.com/challenge"></script>'
        raise AssertionError(path)

    monkeypatch.setattr(hosted_nullxoid_chat, "request_json", fake_request_json)

    result = hosted_nullxoid_chat.run_hosted_nullxoid_chat_check(
        origin="https://app.example.test",
        base_path="/nullxoid",
        username="admin",
        password="runtime-only",
    )

    assert result.ok is False
    assert result.failure == "login_challenged"


def test_hosted_chat_check_fails_when_operations_status_returns_html(monkeypatch):
    def fake_request_json(opener, origin, base_path, path, *, method="GET", payload=None, timeout=15):
        if path == "/auth/login":
            return 200, {"ok": True}
        if path == "/auth/me":
            return 200, {"authenticated": True, "user": {"id": "user-1"}}
        if path == "/api/workspaces":
            return 200, {"workspaces": [{"workspace_id": "ws-1"}]}
        if path == "/api/projects?workspace_id=ws-1":
            return 200, {"projects": [{"project_id": "proj-1"}]}
        if path == "/api/operations/status":
            return 403, "<html>Forbidden</html>"
        raise AssertionError(path)

    monkeypatch.setattr(hosted_nullxoid_chat, "request_json", fake_request_json)
    monkeypatch.setattr(hosted_nullxoid_chat, "csrf_token", lambda jar: "csrf-token")

    result = hosted_nullxoid_chat.run_hosted_nullxoid_chat_check(
        origin="https://app.example.test",
        base_path="/nullxoid",
        username="admin",
        password="runtime-only",
        model="llama.cpp:qwen",
    )

    assert result.ok is False
    assert result.failure == "operations_status_returned_html"


def test_hosted_chat_check_fails_when_operations_status_leaks_local_path(monkeypatch):
    def fake_request_json(opener, origin, base_path, path, *, method="GET", payload=None, timeout=15):
        if path == "/auth/login":
            return 200, {"ok": True}
        if path == "/auth/me":
            return 200, {"authenticated": True, "user": {"id": "user-1"}}
        if path == "/api/workspaces":
            return 200, {"workspaces": [{"workspace_id": "ws-1"}]}
        if path == "/api/projects?workspace_id=ws-1":
            return 200, {"projects": [{"project_id": "proj-1"}]}
        if path == "/api/operations/status":
            return 200, operations_status_payload(debug="/home/deploy/NullXoid/.env")
        raise AssertionError(path)

    monkeypatch.setattr(hosted_nullxoid_chat, "request_json", fake_request_json)
    monkeypatch.setattr(hosted_nullxoid_chat, "csrf_token", lambda jar: "csrf-token")

    result = hosted_nullxoid_chat.run_hosted_nullxoid_chat_check(
        origin="https://app.example.test",
        base_path="/nullxoid",
        username="admin",
        password="runtime-only",
        model="llama.cpp:qwen",
    )

    assert result.ok is False
    assert result.failure.startswith("operations_status_path_leak")


def test_hosted_chat_check_fails_when_operations_status_exposes_nullbridge_credentials(monkeypatch):
    def fake_request_json(opener, origin, base_path, path, *, method="GET", payload=None, timeout=15):
        if path == "/auth/login":
            return 200, {"ok": True}
        if path == "/auth/me":
            return 200, {"authenticated": True, "user": {"id": "user-1"}}
        if path == "/api/workspaces":
            return 200, {"workspaces": [{"workspace_id": "ws-1"}]}
        if path == "/api/projects?workspace_id=ws-1":
            return 200, {"projects": [{"project_id": "proj-1"}]}
        if path == "/api/operations/status":
            return 200, operations_status_payload(nullbridge={"credentials_exposed": True})
        raise AssertionError(path)

    monkeypatch.setattr(hosted_nullxoid_chat, "request_json", fake_request_json)
    monkeypatch.setattr(hosted_nullxoid_chat, "csrf_token", lambda jar: "csrf-token")

    result = hosted_nullxoid_chat.run_hosted_nullxoid_chat_check(
        origin="https://app.example.test",
        base_path="/nullxoid",
        username="admin",
        password="runtime-only",
        model="llama.cpp:qwen",
    )

    assert result.ok is False
    assert result.failure == "operations_nullbridge_credentials_exposed"
