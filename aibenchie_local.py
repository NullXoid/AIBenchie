from __future__ import annotations

import argparse
import json
import sys

from aibenchie.local_ollama import DEFAULT_OLLAMA_URL, benchmark_ollama_model, list_ollama_models, model_name
from aibenchie.local_nullbridge_runner import run_local_trust_path
from aibenchie.nullprivacy import run_e2ee_storage_proof
from aibenchie.hosted_nullxoid_auth import run_from_env as run_hosted_nullxoid_auth_from_env
from aibenchie.hosted_nullxoid_chat import run_from_env as run_hosted_nullxoid_chat_from_env
from aibenchie.hosted_nullxoid_ephemeral_chat import run_from_env as run_hosted_nullxoid_ephemeral_chat_from_env
from aibenchie.hosted_nullxoid_stack import run_from_env as run_hosted_nullxoid_stack_from_env
from aibenchie.resource_budget import run_resource_budget_check


DEFAULT_PROMPT = "Reply with one sentence explaining what AIBenchie verifies before a release."


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run public-safe local AIBenchie checks.")
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL, help="Local Ollama URL. Only localhost URLs are allowed.")
    parser.add_argument("--model", default="", help="Model to test. Defaults to the first detected model.")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT, help="Bounded prompt for the local model test.")
    parser.add_argument("--list-models", action="store_true", help="List detected local Ollama models and exit.")
    parser.add_argument(
        "--trust-smoke",
        action="store_true",
        help="Run a local NullBridge trust-fabric smoke test with temporary generated secrets.",
    )
    parser.add_argument(
        "--privacy-proof",
        action="store_true",
        help="Run a local E2EE storage proof with temporary generated keys.",
    )
    parser.add_argument(
        "--release-report",
        action="store_true",
        help="Write AIBenchie release verdict summary and encrypted full report.",
    )
    parser.add_argument(
        "--hosted-nullxoid-auth",
        action="store_true",
        help="Run the hosted NullXoid login check using AIBENCHIE_NULLXOID_* environment variables.",
    )
    parser.add_argument(
        "--hosted-nullxoid-stack",
        action="store_true",
        help="Run hosted NullXoid wrapper route checks using AIBENCHIE_NULLXOID_* environment variables.",
    )
    parser.add_argument(
        "--hosted-nullxoid-chat",
        action="store_true",
        help="Run a credentialed hosted NullXoid chat stream check using AIBENCHIE_NULLXOID_* environment variables.",
    )
    parser.add_argument(
        "--hosted-nullxoid-ephemeral-chat",
        action="store_true",
        help="Run hosted NullXoid chat E2E with a loopback-created short-lived test user.",
    )
    parser.add_argument(
        "--resource-budget",
        action="store_true",
        help="Run local storage/cache/log budget checks. Override with AIBENCHIE_RESOURCE_* environment variables.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.trust_smoke:
        result = run_local_trust_path()
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print("Trust Fabric Smoke Test")
            print(f"Allow route: HTTP {result['allow']['status']}")
            print(f"Deny route: HTTP {result['deny']['status']}")
            print(f"Secrets persisted: {result['secrets_persisted']}")
            print("Result: PASS" if result["ok"] else "Result: FAIL")
        return 0 if result["ok"] else 1

    if args.privacy_proof:
        result = run_e2ee_storage_proof().as_dict()
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print("NullPrivacy E2EE Storage Proof")
            print(f"Roundtrip: {result['roundtrip_ok']}")
            print(f"Wrong key rejected: {result['wrong_key_rejected']}")
            print(f"Tamper rejected: {result['tamper_rejected']}")
            print(f"Plaintext visible in blob: {result['plaintext_visible_in_blob']}")
            print("Result: PASS" if result["ok"] else "Result: FAIL")
        return 0 if result["ok"] else 1

    if args.release_report:
        from pathlib import Path

        from aibenchie.release_report import write_release_report

        result = write_release_report(Path(__file__).resolve().parent, run_trust_smoke=True)
        print(json.dumps(result, indent=2) if args.json else f"Verdict: {result['verdict']}\nSummary: {result['summary']}")
        return 0 if result["ok"] else 1

    if args.hosted_nullxoid_auth:
        result = run_hosted_nullxoid_auth_from_env().as_dict()
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print("Hosted NullXoid Auth Check")
            print(f"Origin: {result['origin']}")
            print(f"Base path: {result['base_path']}")
            print(f"Anonymous auth state: HTTP {result['anonymous_status']}")
            print(f"Login: HTTP {result['login_status']}")
            print(f"Post-login auth state: HTTP {result['authenticated_status']}")
            print(f"Cookies: {', '.join(result['cookie_names']) or '(none)'}")
            print("Result: PASS" if result["ok"] else f"Result: FAIL ({result['failure']})")
        return 0 if result["ok"] else 1

    if args.hosted_nullxoid_stack:
        result = run_hosted_nullxoid_stack_from_env().as_dict()
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print("Hosted NullXoid Stack Check")
            print(f"Origin: {result['origin']}")
            print(f"Base path: {result['base_path']}")
            for route in result["routes"]:
                status = "PASS" if route["ok"] else f"FAIL ({route['failure']})"
                print(f"{route['name']}: HTTP {route['status']} {status}")
            print("Result: PASS" if result["ok"] else "Result: FAIL")
        return 0 if result["ok"] else 1

    if args.hosted_nullxoid_chat:
        result = run_hosted_nullxoid_chat_from_env().as_dict()
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print("Hosted NullXoid Chat Check")
            print(f"Origin: {result['origin']}")
            print(f"Base path: {result['base_path']}")
            print(f"Login: HTTP {result['login_status']}")
            print(f"Chat stream: HTTP {result['stream_status']}")
            print(f"Workspace: {result['workspace_id'] or '(none)'}")
            print(f"Project: {result['project_id'] or '(none)'}")
            print(f"Model: {result['model'] or '(none)'}")
            print("Result: PASS" if result["ok"] else f"Result: FAIL ({result['failure']})")
        return 0 if result["ok"] else 1

    if args.hosted_nullxoid_ephemeral_chat:
        result = run_hosted_nullxoid_ephemeral_chat_from_env().as_dict()
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            chat = result.get("chat") or {}
            print("Hosted NullXoid Ephemeral Chat Check")
            print(f"Origin: {result['origin']}")
            print(f"Base path: {result['base_path']}")
            print(f"Helper origin: {result['helper_origin']}")
            print(f"Create test user: HTTP {result['create_status']}")
            print(f"Chat stream: HTTP {chat.get('stream_status', 0)}")
            print(f"Workspace: {chat.get('workspace_id') or '(none)'}")
            print(f"Project: {chat.get('project_id') or '(none)'}")
            print(f"Model runtime: {chat.get('model') or '(none)'}")
            print(f"Cleanup test user: HTTP {result['cleanup_status']}")
            print("Result: PASS" if result["ok"] else f"Result: FAIL ({result['failure']})")
        return 0 if result["ok"] else 1

    if args.resource_budget:
        result = run_resource_budget_check().as_dict()
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print("AIBenchie Resource Budget Check")
            disk = result["disk"]
            disk_status = "PASS" if disk["ok"] else f"FAIL ({disk['failure']})"
            print(
                f"Disk {disk['root']}: {disk['used_gb']} GiB used, "
                f"{disk['free_gb']} GiB free, {disk['used_percent']}% used: {disk_status}"
            )
            for item in result["items"]:
                status = "PASS" if item["ok"] else f"FAIL ({item['failure']})"
                print(f"{item['name']}: {item['mb_used']} MiB / {item['max_mb']} MiB: {status}")
            print("Result: PASS" if result["ok"] else "Result: FAIL")
        return 0 if result["ok"] else 1

    models = list_ollama_models(args.ollama_url)
    model_names = [model_name(item) for item in models if model_name(item)]

    if args.list_models:
        payload = {"ollama_url": args.ollama_url, "model_count": len(model_names), "models": model_names}
        print(json.dumps(payload, indent=2) if args.json else "\n".join(model_names))
        return 0

    selected = args.model or (model_names[0] if model_names else "")
    if not selected:
        raise SystemExit("Ollama responded, but no models were listed.")

    result = benchmark_ollama_model(args.ollama_url, selected, args.prompt)
    result["model_count"] = len(model_names)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Model: {result['model']}")
        print(f"Latency: {result['elapsed_seconds']}s")
        print(f"Tokens/sec: {result['tokens_per_second']}")
        print(f"Response: {result['response']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
