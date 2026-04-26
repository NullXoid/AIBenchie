from __future__ import annotations

import os
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from http.cookiejar import CookieJar
from typing import Any

from aibenchie.hosted_nullxoid_auth import normalize_base_path, normalize_origin, request_json
from aibenchie.hosted_nullxoid_chat import HostedChatResult, run_hosted_nullxoid_chat_check


@dataclass
class EphemeralHostedChatResult:
    ok: bool
    origin: str
    base_path: str
    helper_origin: str
    create_status: int
    cleanup_status: int
    chat: dict[str, Any] = field(default_factory=dict)
    user_id: str = ""
    username: str = ""
    failure: str = ""
    cleanup_ok: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "origin": self.origin,
            "base_path": self.base_path,
            "helper_origin": self.helper_origin,
            "create_status": self.create_status,
            "cleanup_status": self.cleanup_status,
            "chat": self.chat,
            "user_id": self.user_id,
            "username": self.username,
            "failure": self.failure,
            "cleanup_ok": self.cleanup_ok,
        }


def _safe_chat_dict(result: HostedChatResult) -> dict[str, Any]:
    payload = result.as_dict()
    return {key: value for key, value in payload.items() if key not in {"password"}}


def run_ephemeral_hosted_nullxoid_chat_check(
    *,
    origin: str,
    helper_origin: str,
    base_path: str = "/nullxoid",
    model: str = "",
    prompt: str = "Reply with a short greeting for the NullXoid E2E check.",
    timeout: int = 45,
) -> EphemeralHostedChatResult:
    resolved_origin = normalize_origin(origin)
    resolved_base_path = normalize_base_path(base_path)
    resolved_helper_origin = normalize_origin(helper_origin)

    helper_jar = CookieJar()
    helper = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(helper_jar))
    user_id = ""
    username = ""
    create_status = 0
    cleanup_status = 0
    cleanup_ok = False
    chat_payload: dict[str, Any] = {}
    failure = ""
    result = EphemeralHostedChatResult(
        ok=False,
        origin=resolved_origin,
        base_path=resolved_base_path,
        helper_origin=resolved_helper_origin,
        create_status=create_status,
        cleanup_status=cleanup_status,
    )

    try:
        create_status, create_body = request_json(
            helper,
            resolved_helper_origin,
            "",
            "/auth/e2e/test-user",
            method="POST",
            timeout=timeout,
        )
        result.create_status = create_status
        if create_status != 200 or not isinstance(create_body, dict):
            result.failure = f"create_test_user_http_{create_status}"
            return result

        user_id = str(create_body.get("user_id") or "").strip()
        username = str(create_body.get("username") or "").strip()
        password = str(create_body.get("password") or "")
        result.user_id = user_id
        result.username = username
        if not user_id or not username or not password:
            result.failure = "create_test_user_missing_fields"
            return result

        chat_result = run_hosted_nullxoid_chat_check(
            origin=resolved_origin,
            base_path=resolved_base_path,
            username=username,
            password=password,
            model=model,
            prompt=prompt,
            timeout=timeout,
        )
        chat_payload = _safe_chat_dict(chat_result)
        failure = "" if chat_result.ok else chat_result.failure
        result.ok = chat_result.ok
        result.chat = chat_payload
        result.failure = failure
        return result
    finally:
        if user_id:
            cleanup_status, cleanup_body = request_json(
                helper,
                resolved_helper_origin,
                "",
                f"/auth/e2e/test-user/{urllib.parse.quote(user_id, safe='')}",
                method="DELETE",
                timeout=timeout,
            )
            cleanup_ok = (
                cleanup_status == 200
                and isinstance(cleanup_body, dict)
                and cleanup_body.get("ok") is True
                and cleanup_body.get("deleted") is True
            )
            result.cleanup_status = cleanup_status
            result.cleanup_ok = cleanup_ok
            if not cleanup_ok and result.ok:
                result.ok = False
                result.failure = "cleanup_test_user_failed"
            if chat_payload:
                chat_payload["cleanup_status"] = cleanup_status


def run_from_env() -> EphemeralHostedChatResult:
    return run_ephemeral_hosted_nullxoid_chat_check(
        origin=os.environ.get("AIBENCHIE_NULLXOID_ORIGIN", ""),
        base_path=os.environ.get("AIBENCHIE_NULLXOID_BASE_PATH", "/nullxoid"),
        helper_origin=os.environ.get("AIBENCHIE_NULLXOID_EPHEMERAL_HELPER_ORIGIN", "http://127.0.0.1:8090"),
        model=os.environ.get("AIBENCHIE_NULLXOID_MODEL", ""),
        prompt=os.environ.get("AIBENCHIE_NULLXOID_PROMPT", "Reply with a short greeting for the NullXoid E2E check."),
    )
