from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from http.cookiejar import CookieJar
from typing import Any


REQUIRED_COOKIE_NAMES = {"nx_session", "nx_csrf"}


@dataclass
class HostedAuthResult:
    ok: bool
    origin: str
    base_path: str
    anonymous_status: int
    login_status: int
    authenticated_status: int
    authenticated: bool
    cookie_names: list[str] = field(default_factory=list)
    failure: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "origin": self.origin,
            "base_path": self.base_path,
            "anonymous_status": self.anonymous_status,
            "login_status": self.login_status,
            "authenticated_status": self.authenticated_status,
            "authenticated": self.authenticated,
            "cookie_names": self.cookie_names,
            "failure": self.failure,
        }


def normalize_origin(value: str) -> str:
    parsed = urllib.parse.urlparse(value.strip().rstrip("/"))
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("origin must be an http(s) origin")
    if parsed.path not in {"", "/"}:
        raise ValueError("origin must not include a path; use base_path separately")
    return f"{parsed.scheme}://{parsed.netloc}"


def normalize_base_path(value: str) -> str:
    cleaned = value.strip().strip("/")
    return f"/{cleaned}" if cleaned else ""


def read_json_response(response: Any) -> Any:
    raw = response.read().decode("utf-8", errors="replace")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def request_json(
    opener: urllib.request.OpenerDirector,
    origin: str,
    base_path: str,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: int = 15,
) -> tuple[int, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Origin": origin, "Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        f"{origin}{base_path}{path}",
        data=body,
        headers=headers,
        method=method,
    )
    try:
        with opener.open(request, timeout=timeout) as response:
            return int(response.status), read_json_response(response)
    except urllib.error.HTTPError as exc:
        return int(exc.code), read_json_response(exc)


def cookie_names(cookie_jar: CookieJar) -> list[str]:
    return sorted({cookie.name for cookie in cookie_jar})


def run_hosted_nullxoid_auth_check(
    *,
    origin: str,
    username: str,
    password: str,
    base_path: str = "/nullxoid",
    timeout: int = 15,
) -> HostedAuthResult:
    resolved_origin = normalize_origin(origin)
    resolved_base_path = normalize_base_path(base_path)
    if not username.strip():
        raise ValueError("username is required")
    if not password:
        raise ValueError("password is required")

    jar = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    anonymous_status, _ = request_json(
        opener,
        resolved_origin,
        resolved_base_path,
        "/auth/me",
        timeout=timeout,
    )
    login_status, login_body = request_json(
        opener,
        resolved_origin,
        resolved_base_path,
        "/auth/login",
        method="POST",
        payload={"username": username, "password": password},
        timeout=timeout,
    )
    authenticated_status, authenticated_body = request_json(
        opener,
        resolved_origin,
        resolved_base_path,
        "/auth/me",
        timeout=timeout,
    )

    names = cookie_names(jar)
    missing = sorted(REQUIRED_COOKIE_NAMES.difference(names))
    authenticated = isinstance(authenticated_body, dict) and authenticated_body.get("authenticated") is True
    failure = ""
    if login_status >= 400:
        detail = login_body.get("detail") if isinstance(login_body, dict) else login_body
        failure = f"login_http_{login_status}:{detail}"
    elif missing:
        failure = f"missing_cookies:{','.join(missing)}"
    elif authenticated_status != 200 or not authenticated:
        failure = f"auth_state_not_authenticated:{authenticated_status}"

    return HostedAuthResult(
        ok=not failure,
        origin=resolved_origin,
        base_path=resolved_base_path,
        anonymous_status=anonymous_status,
        login_status=login_status,
        authenticated_status=authenticated_status,
        authenticated=authenticated,
        cookie_names=names,
        failure=failure,
    )


def run_from_env() -> HostedAuthResult:
    return run_hosted_nullxoid_auth_check(
        origin=os.environ.get("AIBENCHIE_NULLXOID_ORIGIN", ""),
        base_path=os.environ.get("AIBENCHIE_NULLXOID_BASE_PATH", "/nullxoid"),
        username=os.environ.get("AIBENCHIE_NULLXOID_USERNAME", ""),
        password=os.environ.get("AIBENCHIE_NULLXOID_PASSWORD", ""),
    )

