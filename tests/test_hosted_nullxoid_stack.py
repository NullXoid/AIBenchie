from __future__ import annotations

from aibenchie import hosted_nullxoid_stack


def test_hosted_stack_check_detects_wrapper_manifest_and_json_errors(monkeypatch):
    calls = []

    def fake_request_raw(origin, path, *, host_header="", method="GET", payload=None, timeout=15):
        calls.append((origin, path, host_header, method, payload))
        if path == "/nullxoid/":
            return 200, "text/html; charset=utf-8", "<html><title>NullXoid Gallery</title></html>"
        if path == "/nullxoid/manifest.webmanifest":
            return 200, "application/manifest+json", '{"name":"NullXoid"}'
        if path == "/nullxoid/health":
            return 200, "application/json", '{"status":"ok"}'
        if path == "/nullxoid/auth/login":
            return 401, "application/json", '{"detail":"Invalid username or password"}'
        raise AssertionError(path)

    monkeypatch.setattr(hosted_nullxoid_stack, "request_raw", fake_request_raw)

    result = hosted_nullxoid_stack.run_hosted_nullxoid_stack_check(
        origin="http://127.0.0.1",
        base_path="/nullxoid",
        host_header="www.echolabs.diy",
    )

    assert result.ok is True
    assert [route.name for route in result.routes] == [
        "wrapper_page",
        "wrapper_manifest",
        "backend_health",
        "api_errors_are_json",
    ]
    assert calls[0][2] == "www.echolabs.diy"


def test_hosted_stack_check_fails_on_public_site_wrapper_fallback(monkeypatch):
    def fake_request_raw(origin, path, *, host_header="", method="GET", payload=None, timeout=15):
        if path == "/nullxoid/":
            return 200, "text/html", "If this fallback page appears, the mounted NullXoid wrapper build has not been deployed."
        return 200, "application/json", '{"ok":true}'

    monkeypatch.setattr(hosted_nullxoid_stack, "request_raw", fake_request_raw)

    result = hosted_nullxoid_stack.run_hosted_nullxoid_stack_check(origin="https://www.echolabs.diy")

    assert result.ok is False
    assert result.routes[0].name == "wrapper_page"
    assert result.routes[0].ok is False


def test_hosted_stack_check_fails_when_api_error_is_html(monkeypatch):
    def fake_request_raw(origin, path, *, host_header="", method="GET", payload=None, timeout=15):
        if path == "/nullxoid/":
            return 200, "text/html", "<html>NullXoid Gallery</html>"
        if path == "/nullxoid/manifest.webmanifest":
            return 200, "application/json", '{"name":"NullXoid"}'
        if path == "/nullxoid/health":
            return 200, "application/json", '{"status":"ok"}'
        return 500, "text/html", "<html>Internal Server Error</html>"

    monkeypatch.setattr(hosted_nullxoid_stack, "request_raw", fake_request_raw)

    result = hosted_nullxoid_stack.run_hosted_nullxoid_stack_check(origin="https://www.echolabs.diy")

    assert result.ok is False
    assert result.routes[-1].name == "api_errors_are_json"
    assert result.routes[-1].ok is False
