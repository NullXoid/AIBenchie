from __future__ import annotations

import json
import os
import urllib.parse
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from http.cookiejar import Cookie, CookieJar
from typing import Any

from aibenchie.hosted_nullxoid_auth import normalize_base_path, normalize_origin, read_json_response


PEN_TEST_SESSION_ID = "aibenchie-pen-test-nonexistent-session"


@dataclass(frozen=True)
class PenetrationProbe:
    name: str
    ok: bool
    status: int
    expected: list[int]
    failure: str = ""
    detail: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "ok": self.ok,
            "status": self.status,
            "expected": self.expected,
            "failure": self.failure,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class HostedNullXoidPenetrationResult:
    ok: bool
    origin: str
    base_path: str
    probes: list[PenetrationProbe]
    failure: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "origin": self.origin,
            "base_path": self.base_path,
            "probes": [probe.as_dict() for probe in self.probes],
            "failure": self.failure,
        }


@dataclass
class _LoginSession:
    opener: urllib.request.OpenerDirector
    jar: CookieJar
    session_token: str
    csrf_token: str


def _request_json(
    opener: urllib.request.OpenerDirector,
    origin: str,
    base_path: str,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    origin_header: str | None = None,
    timeout: int = 15,
) -> tuple[int, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request_headers = {"Origin": origin if origin_header is None else origin_header, "Accept": "application/json"}
    if body is not None:
        request_headers["Content-Type"] = "application/json"
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(
        f"{origin}{base_path}{path}",
        data=body,
        headers=request_headers,
        method=method,
    )
    try:
        with opener.open(request, timeout=timeout) as response:
            return int(response.status), read_json_response(response)
    except urllib.error.HTTPError as exc:
        return int(exc.code), read_json_response(exc)


def _cookie_value(jar: CookieJar, name: str) -> str:
    for cookie in jar:
        if cookie.name == name:
            return str(cookie.value)
    return ""


def _make_cookie(name: str, value: str, origin: str) -> Cookie:
    domain = urllib.parse.urlparse(origin).hostname or "localhost"
    return Cookie(
        version=0,
        name=name,
        value=value,
        port=None,
        port_specified=False,
        domain=domain,
        domain_specified=True,
        domain_initial_dot=False,
        path="/",
        path_specified=True,
        secure=origin.startswith("https://"),
        expires=None,
        discard=True,
        comment=None,
        comment_url=None,
        rest={},
        rfc2109=False,
    )


def _login_session(
    *,
    origin: str,
    base_path: str,
    username: str,
    password: str,
    timeout: int,
) -> tuple[_LoginSession | None, PenetrationProbe]:
    jar = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    login_status, login_body = _request_json(
        opener,
        origin,
        base_path,
        "/auth/login",
        method="POST",
        payload={"username": username, "password": password},
        timeout=timeout,
    )
    auth_status, auth_body = _request_json(opener, origin, base_path, "/auth/me", timeout=timeout)
    session_token = _cookie_value(jar, "nx_session")
    csrf_token = _cookie_value(jar, "nx_csrf")
    if isinstance(auth_body, dict) and auth_body.get("csrf_token"):
        csrf_token = str(auth_body.get("csrf_token"))
    authenticated = isinstance(auth_body, dict) and auth_body.get("authenticated") is True
    ok = login_status == 200 and auth_status == 200 and bool(session_token) and bool(csrf_token) and authenticated
    detail = {
        "login_status": login_status,
        "authenticated_status": auth_status,
        "has_session_cookie": bool(session_token),
        "has_csrf_token": bool(csrf_token),
        "authenticated": authenticated,
    }
    if login_status >= 400:
        detail["login_detail"] = login_body.get("detail") if isinstance(login_body, dict) else str(login_body)
    probe = PenetrationProbe(
        name="credentialed_login_prerequisite",
        ok=ok,
        status=auth_status if login_status == 200 else login_status,
        expected=[200],
        failure="" if ok else "credentialed_login_failed",
        detail=detail,
    )
    if not ok:
        return None, probe
    return _LoginSession(opener=opener, jar=jar, session_token=session_token, csrf_token=csrf_token), probe


def _probe_status(name: str, status: int, expected: list[int], *, detail: dict[str, Any] | None = None) -> PenetrationProbe:
    ok = status in expected
    return PenetrationProbe(
        name=name,
        ok=ok,
        status=status,
        expected=expected,
        failure="" if ok else f"unexpected_http_{status}",
        detail=detail or {},
    )


def run_hosted_nullxoid_penetration_check(
    *,
    origin: str,
    username: str,
    password: str,
    base_path: str = "/nullxoid",
    timeout: int = 15,
) -> HostedNullXoidPenetrationResult:
    resolved_origin = normalize_origin(origin)
    resolved_base_path = normalize_base_path(base_path)
    if not username.strip():
        raise ValueError("username is required")
    if not password:
        raise ValueError("password is required")

    probes: list[PenetrationProbe] = []

    anonymous_jar = CookieJar()
    anonymous = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(anonymous_jar))
    status, _ = _request_json(
        anonymous,
        resolved_origin,
        resolved_base_path,
        f"/auth/sessions/{PEN_TEST_SESSION_ID}/revoke",
        method="POST",
        headers={"x-csrf-token": "forged-csrf-token"},
        timeout=timeout,
    )
    probes.append(_probe_status("anonymous_csrf_header_cannot_mutate", status, [401, 403]))

    session, login_probe = _login_session(
        origin=resolved_origin,
        base_path=resolved_base_path,
        username=username,
        password=password,
        timeout=timeout,
    )
    probes.append(login_probe)
    if session is None:
        failure = ";".join(probe.failure for probe in probes if not probe.ok)
        return HostedNullXoidPenetrationResult(
            ok=False,
            origin=resolved_origin,
            base_path=resolved_base_path,
            probes=probes,
            failure=failure,
        )

    status, _ = _request_json(
        session.opener,
        resolved_origin,
        resolved_base_path,
        f"/auth/sessions/{PEN_TEST_SESSION_ID}/revoke",
        method="POST",
        timeout=timeout,
    )
    probes.append(_probe_status("session_cookie_without_csrf_cannot_mutate", status, [403]))

    status, _ = _request_json(
        session.opener,
        resolved_origin,
        resolved_base_path,
        f"/auth/sessions/{PEN_TEST_SESSION_ID}/revoke",
        method="POST",
        headers={"x-csrf-token": "wrong-csrf-token"},
        timeout=timeout,
    )
    probes.append(_probe_status("wrong_csrf_cannot_mutate", status, [403]))

    status, _ = _request_json(
        session.opener,
        resolved_origin,
        resolved_base_path,
        f"/auth/sessions/{PEN_TEST_SESSION_ID}/revoke",
        method="POST",
        headers={"x-csrf-token": session.csrf_token},
        origin_header="https://evil.example.invalid",
        timeout=timeout,
    )
    probes.append(_probe_status("forged_origin_rejected_before_mutation", status, [403]))

    second, second_login_probe = _login_session(
        origin=resolved_origin,
        base_path=resolved_base_path,
        username=username,
        password=password,
        timeout=timeout,
    )
    probes.append(
        PenetrationProbe(
            name="second_login_prerequisite",
            ok=second_login_probe.ok,
            status=second_login_probe.status,
            expected=second_login_probe.expected,
            failure="" if second_login_probe.ok else "second_login_failed",
            detail=second_login_probe.detail,
        )
    )
    if second is not None:
        status, _ = _request_json(
            second.opener,
            resolved_origin,
            resolved_base_path,
            f"/auth/sessions/{PEN_TEST_SESSION_ID}/revoke",
            method="POST",
            headers={"x-csrf-token": session.csrf_token},
            timeout=timeout,
        )
        probes.append(_probe_status("csrf_from_other_session_cannot_mutate", status, [403]))

    logout_status, _ = _request_json(
        session.opener,
        resolved_origin,
        resolved_base_path,
        "/auth/logout",
        method="POST",
        headers={"x-csrf-token": session.csrf_token},
        timeout=timeout,
    )
    probes.append(_probe_status("logout_probe_session_revoked", logout_status, [200]))
    replay_jar = CookieJar()
    replay_jar.set_cookie(_make_cookie("nx_session", session.session_token, resolved_origin))
    replay_jar.set_cookie(_make_cookie("nx_csrf", session.csrf_token, resolved_origin))
    replay = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(replay_jar))
    status, _ = _request_json(
        replay,
        resolved_origin,
        resolved_base_path,
        f"/auth/sessions/{PEN_TEST_SESSION_ID}/revoke",
        method="POST",
        headers={"x-csrf-token": session.csrf_token},
        timeout=timeout,
    )
    probes.append(_probe_status("revoked_session_cannot_mutate", status, [401, 403]))

    failure = ";".join(probe.failure for probe in probes if not probe.ok)
    return HostedNullXoidPenetrationResult(
        ok=not failure,
        origin=resolved_origin,
        base_path=resolved_base_path,
        probes=probes,
        failure=failure,
    )


def run_from_env() -> HostedNullXoidPenetrationResult:
    return run_hosted_nullxoid_penetration_check(
        origin=os.environ.get("AIBENCHIE_NULLXOID_ORIGIN", ""),
        base_path=os.environ.get("AIBENCHIE_NULLXOID_BASE_PATH", "/nullxoid"),
        username=os.environ.get("AIBENCHIE_NULLXOID_USERNAME", ""),
        password=os.environ.get("AIBENCHIE_NULLXOID_PASSWORD", ""),
        timeout=int(os.environ.get("AIBENCHIE_NULLXOID_PENETRATION_TIMEOUT", "15")),
    )
