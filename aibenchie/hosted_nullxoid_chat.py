from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from http.cookiejar import CookieJar
from typing import Any

from aibenchie.hosted_nullxoid_auth import (
    normalize_base_path,
    normalize_origin,
    request_json,
)

CSRF_COOKIE = "nx_csrf"


def _looks_like_cloudflare_challenge(body: str) -> bool:
    lowered = body.lower()
    return "cf-mitigated" in lowered or "challenges.cloudflare.com" in lowered or "just a moment" in lowered


def _non_json_failure(step: str, status: int, body: Any, *, expected_status: int = 200) -> str:
    if isinstance(body, str):
        stripped = body.lstrip()
        if _looks_like_cloudflare_challenge(body):
            return f"{step}_challenged"
        if stripped.startswith("<"):
            return f"{step}_returned_html"
        return f"{step}_not_json"
    if status != expected_status:
        detail = (body.get("detail") or body.get("error")) if isinstance(body, dict) else body
        suffix = f":{detail}" if detail else ""
        return f"{step}_http_{status}{suffix}"
    return ""


def _stream_failure(status: int, content_type: str, body: str) -> str:
    stripped = body.lstrip()
    if _looks_like_cloudflare_challenge(body):
        return "chat_stream_challenged"
    if stripped.startswith("<"):
        return "chat_stream_returned_html"
    if status != 200:
        return f"chat_stream_http_{status}"
    if "json" in content_type.lower():
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            return "chat_stream_invalid_json"
        if isinstance(payload, dict) and (payload.get("detail") or payload.get("error")):
            return "chat_stream_json_error"
    return "chat_stream_missing_output"

@dataclass
class HostedChatResult:
    ok: bool
    origin: str
    base_path: str
    login_status: int
    stream_status: int
    operations_status: int = 0
    user_id: str = ""
    workspace_id: str = ""
    project_id: str = ""
    model: str = ""
    operations_summary: dict[str, Any] = field(default_factory=dict)
    stream_preview: str = ""
    steps: list[str] = field(default_factory=list)
    failure: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "origin": self.origin,
            "base_path": self.base_path,
            "login_status": self.login_status,
            "stream_status": self.stream_status,
            "operations_status": self.operations_status,
            "user_id": self.user_id,
            "workspace_id": self.workspace_id,
            "project_id": self.project_id,
            "model": self.model,
            "operations_summary": self.operations_summary,
            "stream_preview": self.stream_preview,
            "steps": self.steps,
            "failure": self.failure,
        }


def csrf_token(cookie_jar: CookieJar) -> str:
    for cookie in cookie_jar:
        if cookie.name == CSRF_COOKIE:
            return str(cookie.value)
    return ""


def request_stream(
    opener: urllib.request.OpenerDirector,
    origin: str,
    base_path: str,
    path: str,
    *,
    csrf: str,
    payload: dict[str, Any],
    timeout: int = 45,
) -> tuple[int, str, str]:
    request = urllib.request.Request(
        f"{origin}{base_path}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Accept": "text/event-stream,application/json;q=0.8,*/*;q=0.5",
            "Content-Type": "application/json",
            "Origin": origin,
            "X-CSRF-Token": csrf,
        },
        method="POST",
    )
    try:
        with opener.open(request, timeout=timeout) as response:
            return int(response.status), str(response.headers.get("content-type", "")), response.read().decode(
                "utf-8", errors="replace"
            )
    except urllib.error.HTTPError as exc:
        return int(exc.code), str(exc.headers.get("content-type", "")), exc.read().decode("utf-8", errors="replace")


def _pick_user_id(auth_body: Any) -> str:
    if not isinstance(auth_body, dict):
        return ""
    user = auth_body.get("user")
    if not isinstance(user, dict):
        return ""
    return str(user.get("id") or "").strip()


def _pick_workspace(workspaces_body: Any) -> str:
    if not isinstance(workspaces_body, dict):
        return ""
    workspaces = workspaces_body.get("workspaces")
    if not isinstance(workspaces, list):
        return ""
    active = str(workspaces_body.get("active_workspace_id") or "").strip()
    if active and any(isinstance(item, dict) and item.get("workspace_id") == active for item in workspaces):
        return active
    for workspace in workspaces:
        if isinstance(workspace, dict) and workspace.get("workspace_id"):
            return str(workspace["workspace_id"])
    return ""


def _pick_project(projects_body: Any) -> str:
    if not isinstance(projects_body, dict):
        return ""
    projects = projects_body.get("projects")
    if not isinstance(projects, list):
        return ""
    for project in projects:
        if not isinstance(project, dict):
            continue
        if project.get("slug") == "general" and (project.get("project_id") or project.get("id")):
            return str(project.get("project_id") or project.get("id"))
    for project in projects:
        if isinstance(project, dict) and (project.get("project_id") or project.get("id")):
            return str(project.get("project_id") or project.get("id"))
    return ""


def _pick_model(models_body: Any) -> str:
    if not isinstance(models_body, dict):
        return ""
    models = models_body.get("models")
    if not isinstance(models, list):
        return ""
    for model in models:
        if isinstance(model, str) and model.strip():
            return model.strip()
        if isinstance(model, dict):
            value = model.get("id") or model.get("name") or model.get("model")
            if value:
                return str(value).strip()
    return ""


def _iter_string_values(value: Any):
    if isinstance(value, str):
        yield value
        return
    if isinstance(value, dict):
        for child in value.values():
            yield from _iter_string_values(child)
        return
    if isinstance(value, list):
        for child in value:
            yield from _iter_string_values(child)


def _operations_status_failure(status: int, body: Any) -> str:
    failure = _non_json_failure("operations_status", status, body)
    if failure:
        return failure
    if not isinstance(body, dict):
        return "operations_status_not_object"
    if body.get("ok") is not True:
        return "operations_status_not_ok"

    backend = body.get("backend")
    if not isinstance(backend, dict):
        return "operations_backend_missing"
    if backend.get("service") != "wrapper_backend":
        return "operations_backend_wrong_service"
    if backend.get("status") != "ok":
        return "operations_backend_not_ok"

    deploy = body.get("deploy")
    if isinstance(deploy, dict):
        mount = str(deploy.get("mount") or "")
        if mount and mount != "/nullxoid/":
            return "operations_wrong_mount"

    nullbridge = body.get("nullbridge")
    if not isinstance(nullbridge, dict):
        return "operations_nullbridge_status_missing"
    if nullbridge.get("credentials_exposed") is not False:
        return "operations_nullbridge_credentials_exposed"

    path_needles = ("/home/", "/root/", "C:\\", "\\Users\\", ".ssh", ".env")
    secret_needles = (
        "bearer ",
        "authorization:",
        "nx_session=",
        "nx_csrf=",
        "private key",
        "begin openssh private key",
        "begin rsa private key",
    )
    for text in _iter_string_values(body):
        lowered = text.lower()
        for needle in path_needles:
            if needle.lower() in lowered:
                return f"operations_status_path_leak:{needle}"
        for needle in secret_needles:
            if needle in lowered:
                return f"operations_status_secret_leak:{needle}"
    return ""


def _operations_status_summary(body: Any) -> dict[str, Any]:
    if not isinstance(body, dict):
        return {}
    backend = body.get("backend") if isinstance(body.get("backend"), dict) else {}
    deploy = body.get("deploy") if isinstance(body.get("deploy"), dict) else {}
    runtime = body.get("runtime") if isinstance(body.get("runtime"), dict) else {}
    resource = body.get("resource") if isinstance(body.get("resource"), dict) else {}
    nullbridge = body.get("nullbridge") if isinstance(body.get("nullbridge"), dict) else {}
    return {
        "backend_service": backend.get("service", ""),
        "backend_status": backend.get("status", ""),
        "deploy_mount": deploy.get("mount", ""),
        "canonical_origin": deploy.get("canonical_origin", ""),
        "runtime_provider": runtime.get("provider", ""),
        "runtime_status": runtime.get("status", ""),
        "resource_free_gb": resource.get("free_gb", 0),
        "resource_used_percent": resource.get("used_percent", 0),
        "nullbridge_credentials_exposed": nullbridge.get("credentials_exposed", None),
    }


def _stream_has_response(content_type: str, body: str) -> bool:
    stripped = body.strip()
    if not stripped or stripped.startswith("<"):
        return False
    if "json" in content_type.lower():
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            return False
        return isinstance(payload, dict) and not payload.get("detail") and not payload.get("error")
    return "data:" in body or "event:" in body or len(stripped) > 0


def run_hosted_nullxoid_chat_check(
    *,
    origin: str,
    username: str,
    password: str,
    base_path: str = "/nullxoid",
    model: str = "",
    prompt: str = "Reply with a short greeting for the NullXoid E2E check.",
    timeout: int = 45,
) -> HostedChatResult:
    resolved_origin = normalize_origin(origin)
    resolved_base_path = normalize_base_path(base_path)
    if not username.strip():
        raise ValueError("username is required")
    if not password:
        raise ValueError("password is required")

    steps: list[str] = []
    jar = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    login_status, login_body = request_json(
        opener,
        resolved_origin,
        resolved_base_path,
        "/auth/login",
        method="POST",
        payload={"username": username, "password": password},
        timeout=timeout,
    )
    steps.append(f"login:{login_status}")
    login_failure = _non_json_failure("login", login_status, login_body)
    if login_failure:
        return HostedChatResult(
            ok=False,
            origin=resolved_origin,
            base_path=resolved_base_path,
            login_status=login_status,
            stream_status=0,
            steps=steps,
            failure=login_failure,
        )

    csrf = csrf_token(jar)
    if not csrf:
        return HostedChatResult(
            ok=False,
            origin=resolved_origin,
            base_path=resolved_base_path,
            login_status=login_status,
            stream_status=0,
            steps=steps,
            failure="missing_csrf_cookie",
        )

    auth_status, auth_body = request_json(opener, resolved_origin, resolved_base_path, "/auth/me", timeout=timeout)
    steps.append(f"auth_me:{auth_status}")
    auth_failure = _non_json_failure("auth_me", auth_status, auth_body)
    if auth_failure:
        return HostedChatResult(
            ok=False,
            origin=resolved_origin,
            base_path=resolved_base_path,
            login_status=login_status,
            stream_status=0,
            steps=steps,
            failure=auth_failure,
        )
    user_id = _pick_user_id(auth_body)
    if not user_id:
        return HostedChatResult(
            ok=False,
            origin=resolved_origin,
            base_path=resolved_base_path,
            login_status=login_status,
            stream_status=0,
            steps=steps,
            failure="missing_user_id",
        )

    workspaces_status, workspaces_body = request_json(
        opener, resolved_origin, resolved_base_path, "/api/workspaces", timeout=timeout
    )
    steps.append(f"workspaces:{workspaces_status}")
    workspaces_failure = _non_json_failure("workspaces", workspaces_status, workspaces_body)
    if workspaces_failure:
        return HostedChatResult(
            ok=False,
            origin=resolved_origin,
            base_path=resolved_base_path,
            login_status=login_status,
            stream_status=0,
            user_id=user_id,
            steps=steps,
            failure=workspaces_failure,
        )
    workspace_id = _pick_workspace(workspaces_body)
    if not workspace_id:
        return HostedChatResult(
            ok=False,
            origin=resolved_origin,
            base_path=resolved_base_path,
            login_status=login_status,
            stream_status=0,
            user_id=user_id,
            steps=steps,
            failure="missing_workspace",
        )

    projects_status, projects_body = request_json(
        opener,
        resolved_origin,
        resolved_base_path,
        f"/api/projects?workspace_id={urllib.parse.quote(workspace_id)}",
        timeout=timeout,
    )
    steps.append(f"projects:{projects_status}")
    projects_failure = _non_json_failure("projects", projects_status, projects_body)
    if projects_failure:
        return HostedChatResult(
            ok=False,
            origin=resolved_origin,
            base_path=resolved_base_path,
            login_status=login_status,
            stream_status=0,
            user_id=user_id,
            workspace_id=workspace_id,
            steps=steps,
            failure=projects_failure,
        )
    project_id = _pick_project(projects_body)
    if not project_id:
        return HostedChatResult(
            ok=False,
            origin=resolved_origin,
            base_path=resolved_base_path,
            login_status=login_status,
            stream_status=0,
            user_id=user_id,
            workspace_id=workspace_id,
            steps=steps,
            failure="missing_project",
        )

    selected_model = model.strip()
    if not selected_model:
        models_status, models_body = request_json(opener, resolved_origin, resolved_base_path, "/api/models", timeout=timeout)
        steps.append(f"models:{models_status}")
        models_failure = _non_json_failure("models", models_status, models_body)
        if models_failure:
            return HostedChatResult(
                ok=False,
                origin=resolved_origin,
                base_path=resolved_base_path,
                login_status=login_status,
                stream_status=0,
                user_id=user_id,
                workspace_id=workspace_id,
                project_id=project_id,
                steps=steps,
                failure=models_failure,
            )
        selected_model = _pick_model(models_body)
    if not selected_model:
        return HostedChatResult(
            ok=False,
            origin=resolved_origin,
            base_path=resolved_base_path,
            login_status=login_status,
            stream_status=0,
            user_id=user_id,
            workspace_id=workspace_id,
            project_id=project_id,
            steps=steps,
            failure="missing_model",
        )

    operations_status, operations_body = request_json(
        opener,
        resolved_origin,
        resolved_base_path,
        "/api/operations/status",
        timeout=timeout,
    )
    steps.append(f"operations_status:{operations_status}")
    operations_failure = _operations_status_failure(operations_status, operations_body)
    operations_summary = _operations_status_summary(operations_body)
    if operations_failure:
        return HostedChatResult(
            ok=False,
            origin=resolved_origin,
            base_path=resolved_base_path,
            login_status=login_status,
            stream_status=0,
            operations_status=operations_status,
            user_id=user_id,
            workspace_id=workspace_id,
            project_id=project_id,
            model=selected_model,
            operations_summary=operations_summary,
            steps=steps,
            failure=operations_failure,
        )

    stream_status, content_type, stream_body = request_stream(
        opener,
        resolved_origin,
        resolved_base_path,
        "/chat/stream",
        csrf=csrf,
        payload={
            "model": selected_model,
            "messages": [{"role": "user", "content": prompt}],
            "attachments": [],
            "workspace_id": workspace_id,
            "project_id": project_id,
            "tenant_id": "default",
            "user_id": user_id,
        },
        timeout=timeout,
    )
    steps.append(f"chat_stream:{stream_status}")
    ok = stream_status == 200 and _stream_has_response(content_type, stream_body)
    failure = "" if ok else _stream_failure(stream_status, content_type, stream_body)
    return HostedChatResult(
        ok=ok,
        origin=resolved_origin,
        base_path=resolved_base_path,
        login_status=login_status,
        stream_status=stream_status,
        operations_status=operations_status,
        user_id=user_id,
        workspace_id=workspace_id,
        project_id=project_id,
        model=selected_model,
        operations_summary=operations_summary,
        stream_preview=stream_body[:240],
        steps=steps,
        failure=failure,
    )


def run_from_env() -> HostedChatResult:
    return run_hosted_nullxoid_chat_check(
        origin=os.environ.get("AIBENCHIE_NULLXOID_ORIGIN", ""),
        base_path=os.environ.get("AIBENCHIE_NULLXOID_BASE_PATH", "/nullxoid"),
        username=os.environ.get("AIBENCHIE_NULLXOID_USERNAME", ""),
        password=os.environ.get("AIBENCHIE_NULLXOID_PASSWORD", ""),
        model=os.environ.get("AIBENCHIE_NULLXOID_MODEL", ""),
        prompt=os.environ.get("AIBENCHIE_NULLXOID_PROMPT", "Reply with a short greeting for the NullXoid E2E check."),
    )
