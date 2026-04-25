from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


DEFAULT_TIMEOUT_SECONDS = 8
DEFAULT_AUDIENCE = "nullbridge"


def env(name: str, default: str = "") -> str:
    return str(os.getenv(name, default) or "").strip()


def enabled() -> bool:
    return env("AIBENCHIE_LIVE_TRUST_PATH") in {"1", "true", "yes", "on"}


def live_nullbridge_url() -> str:
    return env("AIBENCHIE_LIVE_NULLBRIDGE_URL").rstrip("/")


def live_wrapper_url() -> str:
    return env("AIBENCHIE_LIVE_WRAPPER_URL").rstrip("/")


def service_secrets() -> dict[str, str]:
    raw = env("AIBENCHIE_LIVE_NULLBRIDGE_SERVICE_JWT_SECRETS")
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("AIBENCHIE_LIVE_NULLBRIDGE_SERVICE_JWT_SECRETS must be JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError("AIBENCHIE_LIVE_NULLBRIDGE_SERVICE_JWT_SECRETS must be a JSON object")
    return {str(key): str(value) for key, value in parsed.items() if str(key).strip() and str(value).strip()}


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def service_jwt(
    *,
    secret: str,
    caller: str,
    capability: str,
    target_role: str,
    audience: str = DEFAULT_AUDIENCE,
    ttl_seconds: int = 60,
) -> str:
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "iss": caller,
        "sub": caller,
        "aud": audience,
        "iat": now,
        "nbf": now - 5,
        "exp": now + max(1, int(ttl_seconds)),
        "jti": f"aibenchie-live-{caller}-{now}",
        "capability": capability,
        "targetRole": target_role,
    }
    signing_input = ".".join(
        [
            b64url(json.dumps(header, separators=(",", ":")).encode("utf-8")),
            b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
        ]
    )
    signature = hmac.new(secret.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    return f"{signing_input}.{b64url(signature)}"


def request_json(
    method: str,
    url: str,
    *,
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> tuple[int, dict[str, Any]]:
    payload = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=payload, method=method)
    request.add_header("Accept", "application/json")
    if body is not None:
        request.add_header("Content-Type", "application/json")
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = {"error": text}
        return exc.code, data


def route_check(
    *,
    base_url: str,
    caller: str,
    secret: str,
    target_role: str,
    capability: str,
    platform: str,
    user_id: str = "aibenchie_live_user",
) -> tuple[int, dict[str, Any]]:
    request_id = f"aibenchie-live-{caller}-{capability.replace('.', '-')}-{int(time.time())}"
    token = service_jwt(secret=secret, caller=caller, capability=capability, target_role=target_role)
    return request_json(
        "POST",
        f"{base_url.rstrip('/')}/bridge/requests",
        headers={
            "X-NullBridge-Service": caller,
            "Authorization": f"Bearer {token}",
        },
        body={
            "requestId": request_id,
            "targetRole": target_role,
            "capability": capability,
            "actingUser": {
                "userId": user_id,
                "roles": ["user"],
                "workspaceId": "aibenchie_live_workspace",
                "platform": platform,
            },
            "payload": {"source": "aibenchie_live_trust_path"},
        },
    )


def health(base_url: str) -> tuple[int, dict[str, Any]]:
    return request_json("GET", f"{base_url.rstrip('/')}/health")


def wrapper_greeting(base_url: str) -> tuple[int, dict[str, Any]]:
    return request_json("GET", f"{base_url.rstrip('/')}/api/aibenchie/greeting")

