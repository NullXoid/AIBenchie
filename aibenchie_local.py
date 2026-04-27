from __future__ import annotations

import argparse
import json
import sys

from aibenchie.local_ollama import DEFAULT_OLLAMA_URL, benchmark_ollama_model, list_ollama_models, model_name
from aibenchie.local_nullbridge_runner import run_local_notification_path, run_local_trust_path
from aibenchie.nullprivacy import run_e2ee_storage_proof
from aibenchie.hosted_nullxoid_auth import run_from_env as run_hosted_nullxoid_auth_from_env
from aibenchie.hosted_nullxoid_chat import run_from_env as run_hosted_nullxoid_chat_from_env
from aibenchie.hosted_nullxoid_ephemeral_chat import run_from_env as run_hosted_nullxoid_ephemeral_chat_from_env
from aibenchie.hosted_nullxoid_stack import run_from_env as run_hosted_nullxoid_stack_from_env
from aibenchie.companion_remote_backend import run_from_env as run_companion_remote_backend_from_env
from aibenchie.generated_output_policy import run_generated_output_policy_check
from aibenchie.public_scoreboard import write_public_scoreboard
from aibenchie.resource_budget import run_resource_budget_check
from aibenchie.suite_security import run_suite_security_check
from aibenchie.suite_test_catalog import run_suite_tests_from_env


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
        "--notification-smoke",
        action="store_true",
        help="Run a local NullBridge notification trust smoke test with temporary generated secrets.",
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
    parser.add_argument("--release-id", default="", help="Optional release id for --release-report output.")
    parser.add_argument(
        "--release-type",
        default="internal",
        help="Release type for --release-report output: public, private, internal, retroactive, or reconstructed.",
    )
    parser.add_argument("--release-scope", default="", help="Short scope summary for --release-report output.")
    parser.add_argument(
        "--release-retroactive",
        action="store_true",
        help="Mark generated release details as a retroactive or reconstructed entry.",
    )
    parser.add_argument("--release-confidence", default="high", help="Confidence label for release details.")
    parser.add_argument("--release-operator", default="", help="Operator label for release details.")
    parser.add_argument("--release-reviewer", default="", help="Reviewer label for release details.")
    parser.add_argument(
        "--release-artifacts",
        default="",
        help="Optional JSON file with release artifact digest, SBOM, signature, and manifest evidence.",
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
    parser.add_argument(
        "--generated-output-policy",
        action="store_true",
        help="Run repo generated-output hygiene checks for reports/data paths.",
    )
    parser.add_argument(
        "--public-scoreboard",
        action="store_true",
        help="Write a public-safe scoreboard using the latest valid runtime report in each class.",
    )
    parser.add_argument(
        "--public-scoreboard-output",
        default="",
        help="Optional output path for --public-scoreboard. Defaults to public_export/aibenchie-scoreboard.json.",
    )
    parser.add_argument(
        "--suite-security",
        action="store_true",
        help="Run the NullXoid suite security E2E gate against hosted API routes and repo hygiene checks.",
    )
    parser.add_argument(
        "--suite-tests",
        action="store_true",
        help="Run AIBenchie's master suite test catalog across configured suite repositories.",
    )
    parser.add_argument(
        "--suite-test-target",
        action="append",
        default=[],
        help="Run a named suite test target. Repeat for multiple targets, or use all.",
    )
    parser.add_argument(
        "--suite-test-optional",
        action="store_true",
        help="Include optional suite test targets such as Android unit checks.",
    )
    parser.add_argument(
        "--suite-test-require-all",
        action="store_true",
        help="Fail instead of skipping when a configured suite repository or required test file is missing.",
    )
    parser.add_argument(
        "--companion-remote-backend",
        action="store_true",
        help="Run the NullXoid Companion/Android public API backend contract gate.",
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

    if args.notification_smoke:
        result = run_local_notification_path()
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print("Notification Trust Smoke Test")
            print(f"Publish route: HTTP {result['publish']['status']}")
            print(f"Subscribe route: HTTP {result['query']['status']}")
            print(f"Direct frontend denied: HTTP {result['direct_frontend_denied']['status']}")
            print(f"Website publish denied: HTTP {result['website_publish_denied']['status']}")
            print(f"Source identity bound: HTTP {result['source_identity_bound']['status']}")
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

        from aibenchie.release_report import load_artifact_attestation_manifest, write_release_report

        artifacts = (
            load_artifact_attestation_manifest(Path(args.release_artifacts))
            if args.release_artifacts
            else None
        )

        result = write_release_report(
            Path(__file__).resolve().parent,
            run_trust_smoke=True,
            release_id=args.release_id or None,
            release_type=args.release_type,
            scope=args.release_scope,
            retroactive=args.release_retroactive,
            confidence=args.release_confidence,
            operator=args.release_operator,
            reviewer=args.release_reviewer,
            artifacts=artifacts,
        )
        print(
            json.dumps(result, indent=2)
            if args.json
            else (
                f"Verdict: {result['verdict']}\n"
                f"Summary: {result['summary']}\n"
                f"Release details: {result['release_details_markdown']}"
            )
        )
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
            print(f"Operations status: HTTP {result['operations_status']}")
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

    if args.generated_output_policy:
        result = run_generated_output_policy_check().as_dict()
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print("AIBenchie Generated Output Policy Check")
            print(f"Root: {result['root']}")
            for budget in result["budgets"]:
                status = "PASS" if budget["ok"] else f"FAIL ({budget['failure']})"
                print(
                    f"{budget['name']}: {budget['mb_used']} MiB / {budget['max_mb']} MiB, "
                    f"{budget['file_count']} / {budget['max_files']} files: {status}"
                )
            if result["forbidden_files"]:
                print("Forbidden generated files:")
                for item in result["forbidden_files"]:
                    print(f"- {item['path']} ({item['failure']})")
            if result["dirty_tracked_files"]:
                print("Dirty tracked generated outputs:")
                for item in result["dirty_tracked_files"]:
                    print(f"- {item['path']} ({item['status']})")
            print("Result: PASS" if result["ok"] else "Result: FAIL")
        return 0 if result["ok"] else 1

    if args.public_scoreboard:
        from pathlib import Path

        result = write_public_scoreboard(output=Path(args.public_scoreboard_output) if args.public_scoreboard_output else None)
        payload = result.as_dict()
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            overall = payload["scoreboard"].get("overall", {}) if payload["scoreboard"] else {}
            print("AIBenchie Public Scoreboard Export")
            print(f"Output: {payload['output']}")
            print(f"Included reports: {payload['included_reports']}")
            print(f"Skipped reports: {payload['skipped_reports']}")
            print(f"Overall score: {overall.get('score', 0)}")
            print(f"Grade: {overall.get('grade', 'unknown')}")
            print("Result: PASS" if payload["ok"] else f"Result: FAIL ({payload['failure']})")
        return 0 if payload["ok"] else 1

    if args.suite_security:
        result = run_suite_security_check().as_dict()
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print("AIBenchie Suite Security E2E Gate")
            print(f"Origin: {result['origin']}")
            print(f"Base path: {result['base_path']}")
            for check in result["checks"]:
                if check["status"] == "skip":
                    suffix = f" ({check['detail'].get('reason', 'optional check skipped')})"
                elif check["failure"]:
                    suffix = f" ({check['failure']})"
                else:
                    suffix = ""
                print(f"{check['name']}: {check['status'].upper()} [{check['severity']}]{suffix}")
            print("Result: PASS" if result["ok"] else "Result: FAIL")
        return 0 if result["ok"] else 1

    if args.suite_tests:
        result = run_suite_tests_from_env(
            selected_targets=args.suite_test_target or None,
            include_optional=args.suite_test_optional,
            require_all=args.suite_test_require_all,
        ).as_dict()
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print("AIBenchie Master Suite Test Catalog")
            print(f"Root: {result['root']}")
            print(f"Targets: {', '.join(result['selected_targets'])}")
            for item in result["results"]:
                suffix = f" ({item['failure']})" if item["failure"] else ""
                repo = f" [{item['repo']}]" if item["repo"] else ""
                print(f"{item['name']}: {item['status'].upper()}{suffix}{repo}")
            print("Result: PASS" if result["ok"] else "Result: FAIL")
        return 0 if result["ok"] else 1

    if args.companion_remote_backend:
        result = run_companion_remote_backend_from_env().as_dict()
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print("NullXoid Companion Remote Backend Gate")
            print(f"Android repo: {result['android_repo']}")
            print(f"Public API: {result['public_api']}")
            print(f"Origin: {result['origin']}")
            print(f"Base path: {result['base_path']}")
            for check in result["checks"]:
                status = "PASS" if check["ok"] else f"FAIL ({check['failure']})"
                print(f"{check['name']}: {status}")
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
