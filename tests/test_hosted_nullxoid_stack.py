from __future__ import annotations

import json

from aibenchie import hosted_nullxoid_stack


VALID_MANIFEST = json.dumps(
    {
        "name": "NullXoid",
        "start_url": "/nullxoid/",
        "scope": "/nullxoid/",
        "icons": [{"src": "/nullxoid/icons/nx-192.svg"}],
    }
)


def test_hosted_stack_check_detects_wrapper_manifest_and_json_errors(monkeypatch):
    calls = []

    def fake_request_raw(origin, path, *, host_header="", method="GET", payload=None, timeout=15):
        calls.append((origin, path, host_header, method, payload))
        if path == "/nullxoid/":
            return 200, "text/html; charset=utf-8", "<html><title>NullXoid Gallery</title></html>"
        if path == "/nullxoid/manifest.webmanifest":
            return 200, "application/manifest+json", VALID_MANIFEST
        if path == "/nullxoid/health":
            return 200, "application/json", '{"status":"ok"}'
        if path == "/nullxoid/auth/login":
            return 401, "application/json", '{"detail":"Invalid username or password"}'
        if path == "/nullxoid/models":
            return 401, "application/json", '{"detail":"Authentication required"}'
        if path == "/health":
            return 200, "application/json", '{"status":"ok"}'
        if path == "/auth/login":
            return 401, "application/json", '{"detail":"Invalid username or password"}'
        if path == "/api/models":
            return 200, "application/json", '{"models":[{"id":"llama.cpp:qwen3"}]}'
        raise AssertionError(path)

    monkeypatch.setattr(hosted_nullxoid_stack, "request_raw", fake_request_raw)

    result = hosted_nullxoid_stack.run_hosted_nullxoid_stack_check(
        origin="http://127.0.0.1",
        base_path="/nullxoid",
        host_header="app.example.test",
    )

    assert result.ok is True
    assert [route.name for route in result.routes] == [
        "wrapper_page",
        "wrapper_manifest",
        "backend_health",
        "mounted_auth_errors_are_json",
        "mounted_model_route_contract",
        "root_health_route_not_challenged",
        "root_auth_errors_are_json",
        "root_model_route_contract",
    ]
    assert calls[0][2] == "app.example.test"


def test_hosted_stack_check_fails_on_public_site_wrapper_fallback(monkeypatch):
    def fake_request_raw(origin, path, *, host_header="", method="GET", payload=None, timeout=15):
        if path == "/nullxoid/":
            return 200, "text/html", "If this fallback page appears, the mounted NullXoid wrapper build has not been deployed."
        return 200, "application/json", '{"ok":true}'

    monkeypatch.setattr(hosted_nullxoid_stack, "request_raw", fake_request_raw)

    result = hosted_nullxoid_stack.run_hosted_nullxoid_stack_check(origin="https://app.example.test")

    assert result.ok is False
    assert result.routes[0].name == "wrapper_page"
    assert result.routes[0].ok is False
    assert result.routes[0].failure == "wrapper_fallback_page"


def test_hosted_stack_check_fails_when_api_error_is_html(monkeypatch):
    def fake_request_raw(origin, path, *, host_header="", method="GET", payload=None, timeout=15):
        if path == "/nullxoid/":
            return 200, "text/html", "<html>NullXoid Gallery</html>"
        if path == "/nullxoid/manifest.webmanifest":
            return 200, "application/json", VALID_MANIFEST
        if path == "/nullxoid/health":
            return 200, "application/json", '{"status":"ok"}'
        return 500, "text/html", "<html>Internal Server Error</html>"

    monkeypatch.setattr(hosted_nullxoid_stack, "request_raw", fake_request_raw)

    result = hosted_nullxoid_stack.run_hosted_nullxoid_stack_check(origin="https://app.example.test")

    assert result.ok is False
    assert result.routes[3].name == "mounted_auth_errors_are_json"
    assert result.routes[3].ok is False


def test_hosted_stack_check_fails_when_manifest_is_challenged(monkeypatch):
    def fake_request_raw(origin, path, *, host_header="", method="GET", payload=None, timeout=15):
        if path == "/nullxoid/":
            return 200, "text/html", "<html>NullXoid Gallery</html>"
        if path == "/nullxoid/manifest.webmanifest":
            return 403, "text/html", '<script src="https://challenges.cloudflare.com/challenge"></script>'
        return 200, "application/json", '{"status":"ok"}'

    monkeypatch.setattr(hosted_nullxoid_stack, "request_raw", fake_request_raw)

    result = hosted_nullxoid_stack.run_hosted_nullxoid_stack_check(origin="https://app.example.test")

    assert result.ok is False
    assert result.routes[1].name == "wrapper_manifest"
    assert result.routes[1].failure == "manifest_challenged"


def test_hosted_stack_check_fails_when_root_api_is_challenged(monkeypatch):
    def fake_request_raw(origin, path, *, host_header="", method="GET", payload=None, timeout=15):
        if path == "/nullxoid/":
            return 200, "text/html", "<html>NullXoid Gallery</html>"
        if path == "/nullxoid/manifest.webmanifest":
            return 200, "application/json", VALID_MANIFEST
        if path == "/nullxoid/health":
            return 200, "application/json", '{"status":"ok"}'
        if path == "/nullxoid/auth/login":
            return 401, "application/json", '{"detail":"Invalid username or password"}'
        if path == "/nullxoid/models":
            return 401, "application/json", '{"detail":"Authentication required"}'
        if path == "/health":
            return 200, "application/json", '{"status":"ok"}'
        if path == "/auth/login":
            return 403, "text/html", '<script src="https://challenges.cloudflare.com/challenge"></script>'
        if path == "/api/models":
            return 403, "text/html", '<script src="https://challenges.cloudflare.com/challenge"></script>'
        raise AssertionError(path)

    monkeypatch.setattr(hosted_nullxoid_stack, "request_raw", fake_request_raw)

    result = hosted_nullxoid_stack.run_hosted_nullxoid_stack_check(origin="https://app.example.test")

    assert result.ok is False
    failures = {route.name for route in result.routes if not route.ok}
    assert "root_auth_errors_are_json" in failures
    assert "root_model_route_contract" in failures


def test_hosted_stack_check_accepts_auth_required_model_route(monkeypatch):
    def fake_request_raw(origin, path, *, host_header="", method="GET", payload=None, timeout=15):
        if path == "/nullxoid/":
            return 200, "text/html", "<html>NullXoid Gallery</html>"
        if path == "/nullxoid/manifest.webmanifest":
            return 200, "application/json", VALID_MANIFEST
        if path == "/nullxoid/health":
            return 200, "application/json", '{"status":"ok"}'
        if path == "/nullxoid/auth/login":
            return 401, "application/json", '{"detail":"Invalid username or password"}'
        if path == "/nullxoid/models":
            return 401, "application/json", '{"detail":"Authentication required"}'
        if path == "/health":
            return 200, "application/json", '{"status":"ok"}'
        if path == "/auth/login":
            return 401, "application/json", '{"detail":"Invalid username or password"}'
        if path == "/api/models":
            return 401, "application/json", '{"detail":"Authentication required"}'
        raise AssertionError(path)

    monkeypatch.setattr(hosted_nullxoid_stack, "request_raw", fake_request_raw)

    result = hosted_nullxoid_stack.run_hosted_nullxoid_stack_check(origin="https://app.example.test")

    assert result.ok is True


def test_hosted_stack_check_fails_when_root_health_is_public_html(monkeypatch):
    def fake_request_raw(origin, path, *, host_header="", method="GET", payload=None, timeout=15):
        if path == "/nullxoid/":
            return 200, "text/html", "<html>NullXoid Gallery</html>"
        if path == "/nullxoid/manifest.webmanifest":
            return 200, "application/json", VALID_MANIFEST
        if path == "/nullxoid/health":
            return 200, "application/json", '{"status":"ok"}'
        if path == "/nullxoid/auth/login":
            return 401, "application/json", '{"detail":"Invalid username or password"}'
        if path == "/nullxoid/models":
            return 401, "application/json", '{"detail":"Authentication required"}'
        if path == "/health":
            return 200, "text/html; charset=utf-8", "<html>public site fallback</html>"
        if path == "/auth/login":
            return 401, "application/json", '{"detail":"Invalid username or password"}'
        if path == "/api/models":
            return 401, "application/json", '{"detail":"Authentication required"}'
        raise AssertionError(path)

    monkeypatch.setattr(hosted_nullxoid_stack, "request_raw", fake_request_raw)

    result = hosted_nullxoid_stack.run_hosted_nullxoid_stack_check(origin="https://app.example.test")

    assert result.ok is False
    failures = {route.name: route.failure for route in result.routes if not route.ok}
    assert failures["root_health_route_not_challenged"] == "root_health_not_backend_json"


def test_hosted_stack_check_fails_when_mounted_model_route_is_html(monkeypatch):
    def fake_request_raw(origin, path, *, host_header="", method="GET", payload=None, timeout=15):
        if path == "/nullxoid/":
            return 200, "text/html", "<html>NullXoid Gallery</html>"
        if path == "/nullxoid/manifest.webmanifest":
            return 200, "application/manifest+json", VALID_MANIFEST
        if path == "/nullxoid/health":
            return 200, "application/json", '{"status":"ok"}'
        if path == "/nullxoid/auth/login":
            return 401, "application/json", '{"detail":"Invalid username or password"}'
        if path == "/nullxoid/models":
            return 403, "text/html", '<script src="https://challenges.cloudflare.com/challenge"></script>'
        if path == "/health":
            return 200, "application/json", '{"status":"ok"}'
        if path == "/auth/login":
            return 401, "application/json", '{"detail":"Invalid username or password"}'
        if path == "/api/models":
            return 401, "application/json", '{"detail":"Authentication required"}'
        raise AssertionError(path)

    monkeypatch.setattr(hosted_nullxoid_stack, "request_raw", fake_request_raw)

    result = hosted_nullxoid_stack.run_hosted_nullxoid_stack_check(origin="https://app.example.test")

    assert result.ok is False
    failures = {route.name: route.failure for route in result.routes if not route.ok}
    assert failures["mounted_model_route_contract"] == "mounted_model_challenged"


def test_hosted_stack_check_fails_when_manifest_points_outside_mount(monkeypatch):
    root_manifest = json.dumps(
        {
            "name": "NullXoid",
            "start_url": "/",
            "scope": "/",
            "icons": [{"src": "/icons/nx-192.svg"}],
        }
    )

    def fake_request_raw(origin, path, *, host_header="", method="GET", payload=None, timeout=15):
        if path == "/nullxoid/":
            return 200, "text/html", "<html>NullXoid Gallery</html>"
        if path == "/nullxoid/manifest.webmanifest":
            return 200, "application/manifest+json", root_manifest
        return 200, "application/json", '{"status":"ok"}'

    monkeypatch.setattr(hosted_nullxoid_stack, "request_raw", fake_request_raw)

    result = hosted_nullxoid_stack.run_hosted_nullxoid_stack_check(origin="https://app.example.test")

    assert result.ok is False
    assert result.routes[1].name == "wrapper_manifest"
    assert result.routes[1].failure == "manifest_start_url_outside_base_path"
