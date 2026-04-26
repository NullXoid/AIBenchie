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

@dataclass
class HostedChatResult:
    ok: bool
    origin: str
    base_path: str
    login_status: int
    stream_status: int
    user_id: str = ""
    workspace_id: str = ""
    project_id: str = ""
    model: str = ""
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
            "user_id": self.user_id,
            "workspace_id": self.workspace_id,
            "project_id": self.project_id,
            "model": self.model,
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
    if login_status >= 400:
        detail = login_body.get("detail") if isinstance(login_body, dict) else login_body
        return HostedChatResult(
            ok=False,
            origin=resolved_origin,
            base_path=resolved_base_path,
            login_status=login_status,
            stream_status=0,
            steps=steps,
            failure=f"login_http_{login_status}:{detail}",
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
    failure = "" if ok else f"chat_stream_http_{stream_status}"
    return HostedChatResult(
        ok=ok,
        origin=resolved_origin,
        base_path=resolved_base_path,
        login_status=login_status,
        stream_status=stream_status,
        user_id=user_id,
        workspace_id=workspace_id,
        project_id=project_id,
        model=selected_model,
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
