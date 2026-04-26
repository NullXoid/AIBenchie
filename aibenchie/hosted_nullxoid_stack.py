from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from aibenchie.hosted_nullxoid_auth import normalize_base_path, normalize_origin


@dataclass
class RouteResult:
    name: str
    status: int
    content_type: str
    ok: bool
    failure: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "content_type": self.content_type,
            "ok": self.ok,
            "failure": self.failure,
        }


@dataclass
class HostedStackResult:
    ok: bool
    origin: str
    base_path: str
    routes: list[RouteResult] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "origin": self.origin,
            "base_path": self.base_path,
            "routes": [route.as_dict() for route in self.routes],
        }


def request_raw(
    origin: str,
    path: str,
    *,
    host_header: str = "",
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: int = 15,
) -> tuple[int, str, str]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(f"{origin}{path}", data=body, method=method)
    request.add_header("Accept", "application/json,text/html;q=0.8,*/*;q=0.5")
    if body is not None:
        request.add_header("Content-Type", "application/json")
    if host_header:
        request.add_header("Host", host_header)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return int(response.status), str(response.headers.get("content-type", "")), response.read().decode(
                "utf-8", errors="replace"
            )
    except urllib.error.HTTPError as exc:
        return int(exc.code), str(exc.headers.get("content-type", "")), exc.read().decode("utf-8", errors="replace")


def looks_like_json(text: str) -> bool:
    try:
        json.loads(text)
        return True
    except json.JSONDecodeError:
        return False


def json_payload(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def looks_like_cloudflare_challenge(text: str) -> bool:
    lowered = text.lower()
    return "cf-mitigated" in lowered or "challenges.cloudflare.com" in lowered or "just a moment" in lowered


def json_route_ok(status: int, content_type: str, body: str, *, allowed_statuses: set[int]) -> bool:
    return (
        status in allowed_statuses
        and "json" in content_type.lower()
        and looks_like_json(body)
        and not body.lstrip().startswith("<")
        and not looks_like_cloudflare_challenge(body)
    )


def public_html_route_ok(status: int, content_type: str, body: str) -> bool:
    return (
        status == 200
        and "text/html" in content_type.lower()
        and not looks_like_cloudflare_challenge(body)
        and not body.lstrip().startswith("<!doctype html><html><head><title>just a moment")
    )


def wrapper_page_failure(status: int, content_type: str, body: str) -> str:
    lowered = body.lower()
    if looks_like_cloudflare_challenge(body):
        return "wrapper_page_challenged"
    if status != 200:
        return "wrapper_page_not_200"
    if "fallback page appears" in lowered or "mounted nullxoid wrapper build has not been deployed" in lowered:
        return "wrapper_fallback_page"
    if "text/html" not in content_type.lower():
        return "wrapper_page_not_html"
    return ""


def manifest_failure(status: int, content_type: str, body: str) -> str:
    lowered_type = content_type.lower()
    if looks_like_cloudflare_challenge(body):
        return "manifest_challenged"
    if status != 200:
        return "manifest_not_200"
    if body.lstrip().startswith("<"):
        return "manifest_returned_html"
    if "json" not in lowered_type and "manifest" not in lowered_type:
        return "manifest_not_json"
    if not looks_like_json(body):
        return "manifest_not_json"
    return ""


def model_route_ok(status: int, content_type: str, body: str) -> bool:
    if not json_route_ok(status, content_type, body, allowed_statuses={200, 401, 403}):
        return False
    payload = json_payload(body)
    if status == 200:
        return isinstance(payload, dict) and isinstance(payload.get("models"), list)
    return isinstance(payload, dict) and bool(payload.get("detail") or payload.get("error"))


def health_route_ok(status: int, content_type: str, body: str) -> bool:
    if not json_route_ok(status, content_type, body, allowed_statuses={200}):
        return False
    payload = json_payload(body)
    return isinstance(payload, dict) and payload.get("status") == "ok"


def run_hosted_nullxoid_stack_check(
    *,
    origin: str,
    base_path: str = "/nullxoid",
    host_header: str = "",
    timeout: int = 15,
) -> HostedStackResult:
    resolved_origin = normalize_origin(origin)
    resolved_base_path = normalize_base_path(base_path)
    routes: list[RouteResult] = []

    status, content_type, body = request_raw(
        resolved_origin, f"{resolved_base_path}/", host_header=host_header, timeout=timeout
    )
    failure = wrapper_page_failure(status, content_type, body)
    routes.append(
        RouteResult(
            name="wrapper_page",
            status=status,
            content_type=content_type,
            ok=not failure,
            failure=failure,
        )
    )

    status, content_type, body = request_raw(
        resolved_origin, f"{resolved_base_path}/manifest.webmanifest", host_header=host_header, timeout=timeout
    )
    failure = manifest_failure(status, content_type, body)
    routes.append(
        RouteResult(
            name="wrapper_manifest",
            status=status,
            content_type=content_type,
            ok=not failure,
            failure=failure,
        )
    )

    status, content_type, body = request_raw(
        resolved_origin, f"{resolved_base_path}/health", host_header=host_header, timeout=timeout
    )
    routes.append(
        RouteResult(
            name="backend_health",
            status=status,
            content_type=content_type,
            ok=health_route_ok(status, content_type, body),
            failure="" if health_route_ok(status, content_type, body) else "health_not_backend_json",
        )
    )

    status, content_type, body = request_raw(
        resolved_origin,
        f"{resolved_base_path}/auth/login",
        host_header=host_header,
        method="POST",
        payload={"username": "aibenchie-invalid", "password": "aibenchie-invalid"},
        timeout=timeout,
    )
    routes.append(
        RouteResult(
            name="mounted_auth_errors_are_json",
            status=status,
            content_type=content_type,
            ok=json_route_ok(status, content_type, body, allowed_statuses={400, 401, 403}),
            failure="" if status in {400, 401, 403} else "unexpected_auth_error_status",
        )
    )

    status, content_type, body = request_raw(resolved_origin, "/health", host_header=host_header, timeout=timeout)
    routes.append(
        RouteResult(
            name="root_health_route_not_challenged",
            status=status,
            content_type=content_type,
            ok=health_route_ok(status, content_type, body),
            failure="" if health_route_ok(status, content_type, body) else "root_health_not_backend_json",
        )
    )

    status, content_type, body = request_raw(
        resolved_origin,
        "/auth/login",
        host_header=host_header,
        method="POST",
        payload={"username": "aibenchie-invalid", "password": "aibenchie-invalid"},
        timeout=timeout,
    )
    routes.append(
        RouteResult(
            name="root_auth_errors_are_json",
            status=status,
            content_type=content_type,
            ok=json_route_ok(status, content_type, body, allowed_statuses={400, 401, 403}),
            failure="" if status in {400, 401, 403} else "unexpected_root_auth_error_status",
        )
    )

    status, content_type, body = request_raw(resolved_origin, "/api/models", host_header=host_header, timeout=timeout)
    routes.append(
        RouteResult(
            name="root_model_route_contract",
            status=status,
            content_type=content_type,
            ok=model_route_ok(status, content_type, body),
            failure="" if status in {200, 401, 403} else "root_models_unexpected_status",
        )
    )

    return HostedStackResult(
        ok=all(route.ok for route in routes),
        origin=resolved_origin,
        base_path=resolved_base_path,
        routes=routes,
    )


def run_from_env() -> HostedStackResult:
    return run_hosted_nullxoid_stack_check(
        origin=os.environ.get("AIBENCHIE_NULLXOID_ORIGIN", ""),
        base_path=os.environ.get("AIBENCHIE_NULLXOID_BASE_PATH", "/nullxoid"),
        host_header=os.environ.get("AIBENCHIE_NULLXOID_HOST_HEADER", ""),
    )
