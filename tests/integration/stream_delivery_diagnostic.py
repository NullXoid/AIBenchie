"""Opt-in arrival measurement using AIBenchie's existing hosted chat driver."""
import argparse
import importlib.util
import json
from pathlib import Path
import uuid

from aibenchie.hosted_nullxoid_chat import request_stream, csrf_token, _pick_project


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--account-helper", type=Path, required=True)
    parser.add_argument("--origin", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("existing_account_check", args.account_helper)
    account = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(account)
    account.BASE = args.origin
    account.client.addheaders = [("User-Agent", "NullXoid-Canvas-Operator/1")]
    user = account.login()
    workspace = account.call("/api/workspaces/active")["workspace"]["workspace_id"]
    project = _pick_project(account.call("/api/projects?workspace_id=" + workspace))
    settings = account.call("/api/settings?tenant_id=default&user_id=" + user["user_id"])["settings"]
    model = settings["llm"]["default_model"]
    timings = []
    status, content_type, body = request_stream(
        account.client, args.origin, "", "/chat/stream", csrf=csrf_token(account.jar), timeout=90,
        payload=dict(model=model, messages=[dict(role="user", content=
            "Explain in about 80 words how rain forms. Plain text only, no tools or actions.")],
            session_id="aibenchie-stream-" + uuid.uuid4().hex, workspace_id=workspace,
            project_id=project, tenant_id="default", user_id=user["user_id"],
            stream_live=True, provider_thinking=False, reasoning="off", tool_confirmation_event="tool_confirm"),
        event_timings=timings,
    )
    tokens = [item for item in timings if item["event"] == "token" and item["delta_chars"]]
    result = dict(origin=args.origin, model=model, status=status, content_type=content_type,
        physical_ui_acceptance=False, existing_chat_modified=False, events=timings,
        token_events=len(tokens), total_chars=sum(item["delta_chars"] for item in tokens),
        token_delivery_span_ms=round(tokens[-1]["elapsed_ms"] - tokens[0]["elapsed_ms"], 1) if tokens else None,
        completed=any(item["event"] == "done" for item in timings),
        error=any(item["event"] == "error" for item in timings))
    if status != 200:
        try:
            result["failure_detail"] = json.loads(body).get("detail", "Non-success response")
        except json.JSONDecodeError:
            result["failure_detail"] = "Non-JSON response"
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))
    if status != 200 or not result["completed"] or result["error"] or not tokens:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
