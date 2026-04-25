from __future__ import annotations

import json
from http.cookiejar import Cookie, CookieJar

import pytest

from aibenchie.hosted_nullxoid_auth import (
    normalize_base_path,
    normalize_origin,
    run_hosted_nullxoid_auth_check,
)


class FakeResponse:
    def __init__(self, status: int, body: dict):
        self.status = status
        self._body = json.dumps(body).encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def make_cookie(name: str, value: str) -> Cookie:
    return Cookie(
        version=0,
        name=name,
        value=value,
        port=None,
        port_specified=False,
        domain="example.invalid",
        domain_specified=False,
        domain_initial_dot=False,
        path="/",
        path_specified=True,
        secure=False,
        expires=None,
        discard=True,
        comment=None,
        comment_url=None,
        rest={},
        rfc2109=False,
    )


class FakeOpener:
    def __init__(self, jar: CookieJar, responses: list[FakeResponse], *, set_login_cookies: bool = True):
        self.jar = jar
        self.responses = responses
        self.requests = []
        self.set_login_cookies = set_login_cookies

    def open(self, request, timeout=15):
        self.requests.append((request.full_url, request.get_method(), dict(request.header_items())))
        response = self.responses.pop(0)
        if self.set_login_cookies and request.full_url.endswith("/auth/login") and response.status == 200:
            self.jar.set_cookie(make_cookie("nx_session", "session-value"))
            self.jar.set_cookie(make_cookie("nx_csrf", "csrf-value"))
        return response


def test_normalize_origin_rejects_paths():
    assert normalize_origin("https://example.invalid/") == "https://example.invalid"
    with pytest.raises(ValueError, match="must not include a path"):
        normalize_origin("https://example.invalid/nullxoid")


def test_normalize_base_path_accepts_blank_or_mount():
    assert normalize_base_path("") == ""
    assert normalize_base_path("/nullxoid/") == "/nullxoid"


def test_hosted_auth_check_verifies_login_cookies_and_auth_state(monkeypatch):
    captured = {}

    def fake_build_opener(cookie_processor):
        opener = FakeOpener(
            cookie_processor.cookiejar,
            [
                FakeResponse(200, {"authenticated": False}),
                FakeResponse(200, {"user": {"username": "admin"}}),
                FakeResponse(200, {"authenticated": True}),
            ],
        )
        captured["opener"] = opener
        return opener

    monkeypatch.setattr("aibenchie.hosted_nullxoid_auth.urllib.request.build_opener", fake_build_opener)

    result = run_hosted_nullxoid_auth_check(
        origin="https://example.invalid",
        base_path="/nullxoid",
        username="admin",
        password="not-persisted",
    )

    assert result.ok is True
    assert result.cookie_names == ["nx_csrf", "nx_session"]
    opener = captured["opener"]
    assert opener.requests[1][0] == "https://example.invalid/nullxoid/auth/login"
    assert opener.requests[1][1] == "POST"


def test_hosted_auth_check_fails_when_cookies_do_not_stick(monkeypatch):
    def fake_build_opener(cookie_processor):
        return FakeOpener(
            cookie_processor.cookiejar,
            [
                FakeResponse(200, {"authenticated": False}),
                FakeResponse(200, {"user": {"username": "admin"}}),
                FakeResponse(200, {"authenticated": False}),
            ],
            set_login_cookies=False,
        )

    monkeypatch.setattr("aibenchie.hosted_nullxoid_auth.urllib.request.build_opener", fake_build_opener)

    result = run_hosted_nullxoid_auth_check(
        origin="https://example.invalid",
        base_path="/nullxoid",
        username="admin",
        password="not-persisted",
    )

    assert result.ok is False
    assert result.failure == "missing_cookies:nx_csrf,nx_session"
