from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from aibenchie.local_ollama import DEFAULT_OLLAMA_URL, benchmark_ollama_model, list_ollama_models, model_name
from aibenchie.auth_provider_config import run_from_env as run_auth_provider_config_from_env
from aibenchie.local_nullbridge_runner import run_local_notification_path, run_local_trust_path
from aibenchie.nullbridge_platform_adapters import run_from_env as run_nullbridge_platform_adapters_from_env
from aibenchie.nullprivacy import run_e2ee_storage_proof
from aibenchie.e2ee_readiness import run_e2ee_readiness_check
from aibenchie.echolabs_store import run_from_env as run_echolabs_store_from_env
from aibenchie.hosted_nullxoid_auth import run_from_env as run_hosted_nullxoid_auth_from_env
from aibenchie.hosted_nullxoid_chat import run_from_env as run_hosted_nullxoid_chat_from_env
from aibenchie.hosted_nullxoid_ephemeral_chat import run_from_env as run_hosted_nullxoid_ephemeral_chat_from_env
from aibenchie.hosted_nullxoid_stack import run_from_env as run_hosted_nullxoid_stack_from_env
from aibenchie.companion_remote_backend import run_from_env as run_companion_remote_backend_from_env
from aibenchie.deploy_addon import execute_deploy_addon, run_deploy_addon_check, verify_deploy_plan
from aibenchie.distribution_hygiene import run_distribution_hygiene_check
from aibenchie.docker_support import run_docker_support_gate, validate_docker_support_proof
from aibenchie.generated_output_policy import run_generated_output_policy_check
from aibenchie.android_release_gate import DEFAULT_ANDROID_RELEASE_VERDICT_OUTPUT, run_android_release_gate
from aibenchie.android_onboarding_e2e import DEFAULT_ANDROID_ONBOARDING_E2E_OUTPUT, run_android_onboarding_e2e
from aibenchie.public_scoreboard import write_public_scoreboard
from aibenchie.real_device_ux import (
    DEFAULT_ANDROID_BASE_URL,
    DEFAULT_ANDROID_PACKAGE,
    DEFAULT_ANDROID_PROOF_OUTPUT,
    check_android_real_device_ux_preflight,
    emit_android_real_device_ux_proof,
    validate_real_device_ux_proof,
)
from aibenchie.release import (
    DEFAULT_EVIDENCE_ROOT as DEFAULT_RELEASE_SPINE_EVIDENCE_ROOT,
    DEFAULT_STORE_CAPABILITIES as DEFAULT_RELEASE_SPINE_STORE_CAPABILITIES,
    DEFAULT_SUITE_VERSION as DEFAULT_RELEASE_SPINE_SUITE_VERSION,
    DEFAULT_WORKFLOW_MATRIX as DEFAULT_RELEASE_SPINE_WORKFLOW_MATRIX,
    promote_passing_candidate,
    validate_workflow_matrix,
    verify_release_spine,
)
from aibenchie.release_artifacts import emit_release_artifacts_manifest, verify_release_artifacts_manifest
from aibenchie.release_bundle import package_release_artifacts
from aibenchie.resource_budget import run_resource_budget_check
from aibenchie.secure_signin_setup import run_from_env as run_secure_signin_setup_from_env
from aibenchie.suite_security import run_suite_security_check
from aibenchie.suite_security_privacy import run_from_env as run_suite_security_privacy_from_env
from aibenchie.suite_test_catalog import run_suite_tests_from_env
from aibenchie.universal_e2e import run_universal_e2e
from aibenchie.zero_knowledge_devices import run_zero_knowledge_device_lifecycle_proof


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
        "--e2ee-readiness",
        action="store_true",
        help="Run the release-blocking NullPrivacy E2EE readiness gate.",
    )
    parser.add_argument(
        "--zero-knowledge-device-proof",
        action="store_true",
        help="Run the zero-knowledge device enrollment, recovery, and revocation proof.",
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
        "--release-spine-verify",
        action="store_true",
        help="Write release truth spine latest-build/latest-verdict evidence.",
    )
    parser.add_argument(
        "--release-spine-promote-passing",
        action="store_true",
        help="Promote a passing release truth spine build to latest-passing.json.",
    )
    parser.add_argument(
        "--release-spine-validate-workflows",
        action="store_true",
        help="Validate EchoLabs workflow proof folders and Store mappings.",
    )
    parser.add_argument("--release-spine-build-id", default="", help="Build id for release-spine commands.")
    parser.add_argument(
        "--release-spine-evidence-root",
        default=str(DEFAULT_RELEASE_SPINE_EVIDENCE_ROOT),
        help="Evidence root for release-spine commands.",
    )
    parser.add_argument(
        "--release-spine-suite-version",
        default=DEFAULT_RELEASE_SPINE_SUITE_VERSION,
        help="Suite version recorded by --release-spine-verify.",
    )
    parser.add_argument(
        "--release-spine-workflow-matrix",
        default=str(DEFAULT_RELEASE_SPINE_WORKFLOW_MATRIX),
        help="Workflow matrix path for --release-spine-validate-workflows.",
    )
    parser.add_argument(
        "--release-spine-store-capabilities",
        default=str(DEFAULT_RELEASE_SPINE_STORE_CAPABILITIES),
        help="Store capability mapping path for --release-spine-validate-workflows.",
    )
    parser.add_argument(
        "--release-artifacts",
        default="",
        help="Optional JSON file with release artifact digest, SBOM, signature, and manifest evidence.",
    )
    parser.add_argument(
        "--emit-release-artifacts",
        action="store_true",
        help="Emit release-artifacts.json for wrapper, Android, and public packages.",
    )
    parser.add_argument(
        "--package-release-artifacts",
        action="store_true",
        help="Package wrapper, Android/Companion, and public-site build outputs, then emit release-artifacts.json.",
    )
    parser.add_argument(
        "--verify-release-artifacts",
        action="store_true",
        help="Verify release-artifacts.json digests, SBOM hashes, signature hashes, and manifest hashes.",
    )
    parser.add_argument("--release-artifacts-output", default="release-artifacts.json", help="Output path for --emit-release-artifacts.")
    parser.add_argument("--release-artifacts-sidecar-dir", default="", help="Directory for generated SBOM/signature/package manifests.")
    parser.add_argument(
        "--release-package-output-dir",
        default="release-packages",
        help="Output directory for --package-release-artifacts.",
    )
    parser.add_argument("--wrapper-package", default="", help="Wrapper release package path or build output source.")
    parser.add_argument("--android-package", default="", help="Android/Companion release package path or build output source.")
    parser.add_argument("--public-package", default="", help="Public website/package path or build output source.")
    parser.add_argument(
        "--release-artifact-signature-algorithm",
        default="",
        help="Signature algorithm used for release-artifacts.json evidence. Defaults to hmac-sha256-v1.",
    )
    parser.add_argument(
        "--release-artifact-key-id",
        default="",
        help="Signing key id recorded in release-artifacts.json. Secret material is read from AIBENCHIE_RELEASE_ATTESTATION_SECRET.",
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
        "--resource-manager-evidence",
        default="",
        help="Optional Resource Manager runtime evidence JSON for --resource-budget.",
    )
    parser.add_argument(
        "--resource-manager-require-runtime",
        action="store_true",
        help="Require Resource Manager runtime lease, cleanup, retention, and pressure evidence for --resource-budget.",
    )
    parser.add_argument(
        "--generated-output-policy",
        action="store_true",
        help="Run repo generated-output hygiene checks for reports/data paths.",
    )
    parser.add_argument(
        "--distribution-hygiene",
        action="store_true",
        help="Run release-blocking distribution hygiene checks for private data, secrets, and package leaks.",
    )
    parser.add_argument(
        "--distribution-hygiene-root",
        default="",
        help="Repository root for --distribution-hygiene. Defaults to AIBENCHIE_DISTRIBUTION_ROOT or this repo.",
    )
    parser.add_argument(
        "--distribution-package",
        action="append",
        default=[],
        help="Package file to scan with --distribution-hygiene. Repeat for multiple packages.",
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
        "--suite-security-privacy",
        action="store_true",
        help="Run the M36 suite security/privacy release-gate definition check.",
    )
    parser.add_argument(
        "--suite-tests",
        action="store_true",
        help="Run AIBenchie's master suite test catalog across configured suite repositories.",
    )
    parser.add_argument(
        "--universal-e2e",
        action="store_true",
        help="Run manifest-driven universal API/UX E2E checks.",
    )
    parser.add_argument(
        "--universal-e2e-manifest",
        default="",
        help="JSON/YAML manifest path for --universal-e2e.",
    )
    parser.add_argument(
        "--universal-e2e-lane",
        action="append",
        default=[],
        help="Run one E2E lane from the manifest. Repeat for multiple lanes, or use all.",
    )
    parser.add_argument(
        "--universal-e2e-output",
        default="",
        help="Optional JSON output path for the Universal E2E verdict.",
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
    parser.add_argument(
        "--secure-signin-setup",
        action="store_true",
        help="Run secure sign-in setup policy, Android UI, wrapper feature, and hosted route gates.",
    )
    parser.add_argument(
        "--auth-provider-config",
        action="store_true",
        help="Run passkey/OIDC provider configuration contract checks.",
    )
    parser.add_argument(
        "--auth-provider-config-require-real",
        action="store_true",
        help="Require non-template passkey/OIDC provider values for --auth-provider-config.",
    )
    parser.add_argument(
        "--auth-provider-config-device-proof",
        default="",
        help="Optional ignored JSON proof of physical Android passkey enrollment for --auth-provider-config.",
    )
    parser.add_argument(
        "--auth-provider-config-require-device-proof",
        action="store_true",
        help="Require physical Android passkey enrollment proof for --auth-provider-config.",
    )
    parser.add_argument(
        "--nullbridge-platform-adapters",
        action="store_true",
        help="Run the M35 platform backend NullBridge adapter E2E gate.",
    )
    parser.add_argument(
        "--echolabs-store",
        action="store_true",
        help="Run the EchoLabs Store + Creative Workflows Alpha source/integration gate.",
    )
    parser.add_argument(
        "--deploy-addon",
        action="store_true",
        help="Run the provider-neutral AIBenchie deploy add-on contract gate.",
    )
    parser.add_argument(
        "--deploy-addon-config",
        default="",
        help="Deploy add-on config path. Defaults to AIBENCHIE_DEPLOY_ADDON_CONFIG or the public-safe example.",
    )
    parser.add_argument(
        "--deploy-addon-require-token",
        action="store_true",
        help="Require the configured provider token environment variable to be populated.",
    )
    parser.add_argument(
        "--deploy-addon-plan-output",
        default="",
        help="Optional path to write the sanitized deploy plan when --deploy-addon passes.",
    )
    parser.add_argument(
        "--verify-deploy-plan",
        action="store_true",
        help="Verify a saved provider-neutral deploy plan without publishing.",
    )
    parser.add_argument(
        "--execute-deploy-addon",
        action="store_true",
        help="Publish a verified deploy add-on release. Requires dry_run=false, token env, and exact tag confirmation.",
    )
    parser.add_argument(
        "--deploy-publish-confirm",
        default="",
        help="Exact release tag required for --execute-deploy-addon. May also be set with AIBENCHIE_DEPLOY_PUBLISH_CONFIRM.",
    )
    parser.add_argument(
        "--deploy-plan",
        default="",
        help="Deploy plan path for --verify-deploy-plan.",
    )
    parser.add_argument(
        "--docker-support",
        action="store_true",
        help="Run the Docker support boundary gate. Docker remains unsupported until this gate evolves and passes in supported mode.",
    )
    parser.add_argument(
        "--docker-support-proof",
        default="",
        help="Validate a private Docker supported-mode proof JSON without changing the guarded Docker boundary.",
    )
    parser.add_argument(
        "--android-real-device-ux-preflight",
        action="store_true",
        help="Check adb device/package readiness for Android real-device UX proof without generating release proof.",
    )
    parser.add_argument(
        "--android-release-gate",
        action="store_true",
        help="Run the Android app release verdict gate for update notes, APK evidence, and optional device preflight.",
    )
    parser.add_argument(
        "--android-onboarding-e2e",
        action="store_true",
        help="Run the Android onboarding setup QR/deep-link E2E contract gate.",
    )
    parser.add_argument(
        "--android-onboarding-repo",
        default=os.environ.get(
            "AIBENCHIE_ANDROID_ONBOARDING_REPO",
            os.environ.get("AIBENCHIE_ECHOLABS_ANDROID_ROOT", "../NullXoidAndroid"),
        ),
        help="Android repository root for --android-onboarding-e2e.",
    )
    parser.add_argument(
        "--android-onboarding-output",
        default=str(DEFAULT_ANDROID_ONBOARDING_E2E_OUTPUT),
        help="Output path for the Android onboarding E2E verdict JSON.",
    )
    parser.add_argument(
        "--android-onboarding-run-gradle",
        action="store_true",
        help="Also run the focused Gradle OnboardingUxTest as part of --android-onboarding-e2e.",
    )
    parser.add_argument(
        "--android-onboarding-gradle-timeout",
        type=int,
        default=240,
        help="Timeout in seconds for --android-onboarding-run-gradle.",
    )
    parser.add_argument(
        "--android-release-repo",
        default=os.environ.get("AIBENCHIE_ANDROID_RELEASE_REPO", "."),
        help="Repository root for --android-release-gate.",
    )
    parser.add_argument(
        "--android-release-apk",
        default=os.environ.get("AIBENCHIE_ANDROID_RELEASE_APK", ""),
        help="Android APK artifact path for --android-release-gate.",
    )
    parser.add_argument(
        "--android-release-update-notes",
        default=os.environ.get("AIBENCHIE_ANDROID_RELEASE_UPDATE_NOTES", "frontend/app/UPDATE_NOTES.md"),
        help="Android update notes path for --android-release-gate.",
    )
    parser.add_argument(
        "--android-release-output",
        default=str(DEFAULT_ANDROID_RELEASE_VERDICT_OUTPUT),
        help="Output path for the Android release verdict JSON.",
    )
    parser.add_argument(
        "--android-release-package",
        default=os.environ.get("AIBENCHIE_ANDROID_RELEASE_PACKAGE", ""),
        help="Android package name for --android-release-gate.",
    )
    parser.add_argument(
        "--android-release-base-url",
        default=os.environ.get("AIBENCHIE_ANDROID_RELEASE_BASE_URL", ""),
        help="Backend base URL used by the Android release candidate.",
    )
    parser.add_argument("--android-release-adb", default="adb", help="adb executable for Android release gate.")
    parser.add_argument(
        "--android-release-adb-serial",
        default=os.environ.get("AIBENCHIE_ANDROID_SERIAL", ""),
        help="Optional adb serial for Android release gate. The raw value is not written to verdict output.",
    )
    parser.add_argument(
        "--android-release-require-device",
        action="store_true",
        help="Fail --android-release-gate unless the selected connected Android device has the candidate package installed.",
    )
    parser.add_argument(
        "--real-device-ux-proof",
        default="",
        help="Validate a public-safe real-device UX proof JSON file.",
    )
    parser.add_argument(
        "--emit-android-real-device-ux-proof",
        action="store_true",
        help="Generate an ignored public-safe Android real-device UX proof from a connected adb device.",
    )
    parser.add_argument(
        "--real-device-ux-output",
        default=str(DEFAULT_ANDROID_PROOF_OUTPUT),
        help="Output path for --emit-android-real-device-ux-proof.",
    )
    parser.add_argument("--real-device-ux-adb", default="adb", help="adb executable for Android proof generation.")
    parser.add_argument(
        "--real-device-ux-adb-serial",
        default="",
        help="Optional adb device serial selector for Android proof generation. The raw value is not written to proof output.",
    )
    parser.add_argument(
        "--real-device-ux-package",
        default=DEFAULT_ANDROID_PACKAGE,
        help="Android package name for proof generation.",
    )
    parser.add_argument(
        "--real-device-ux-base-url",
        default=DEFAULT_ANDROID_BASE_URL,
        help="Base URL recorded in generated Android proof evidence.",
    )
    parser.add_argument("--real-device-ux-app-version", default="", help="Override detected Android app version.")
    parser.add_argument("--real-device-ux-proof-id", default="", help="Override generated Android proof id.")
    parser.add_argument(
        "--real-device-ux-runtime-provider",
        default=os.environ.get("AIBENCHIE_REAL_DEVICE_UX_RUNTIME_PROVIDER", ""),
        help="Public-safe runtime provider label recorded in generated Android proof evidence.",
    )
    parser.add_argument(
        "--real-device-ux-runtime-model",
        default=os.environ.get("AIBENCHIE_REAL_DEVICE_UX_RUNTIME_MODEL", ""),
        help="Public-safe runtime model label recorded in generated Android proof evidence.",
    )
    parser.add_argument(
        "--real-device-ux-runtime-endpoint-label",
        default=os.environ.get("AIBENCHIE_REAL_DEVICE_UX_RUNTIME_ENDPOINT_LABEL", ""),
        help="Public-safe runtime endpoint label recorded in generated Android proof evidence.",
    )
    parser.add_argument(
        "--real-device-ux-signin-passed",
        action="store_true",
        help="Mark the generated Android sign-in workflow as passed after operator confirmation.",
    )
    parser.add_argument(
        "--real-device-ux-chat-passed",
        action="store_true",
        help="Mark the generated Android chat workflow as passed after operator confirmation.",
    )
    parser.add_argument(
        "--real-device-ux-capture-screenshot",
        action="store_true",
        help="Capture an ignored adb screenshot artifact and record only its hash in the generated Android proof.",
    )
    parser.add_argument(
        "--real-device-ux-artifact-dir",
        default="",
        help="Optional ignored artifact directory for generated Android proof screenshots.",
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

    if args.universal_e2e:
        if not args.universal_e2e_manifest:
            failure = {"ok": False, "verdict": "fail", "failure": "missing_universal_e2e_manifest"}
            print(json.dumps(failure, indent=2) if args.json else "Result: FAIL (missing universal E2E manifest)")
            return 1
        result = run_universal_e2e(args.universal_e2e_manifest, lanes=args.universal_e2e_lane).as_dict()
        if args.universal_e2e_output:
            output_path = Path(args.universal_e2e_output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print(f"Universal E2E: {result['suite_id']}")
            print(f"Verdict: {result['verdict'].upper()}")
            for lane in result["lanes"]:
                print(f"- {lane['id']}: {'PASS' if lane['ok'] else 'FAIL'}")
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

    if args.e2ee_readiness:
        result = run_e2ee_readiness_check().as_dict()
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print("NullPrivacy E2EE Readiness Gate")
            print(f"Policy: {result['policy_path']}")
            print(f"Evidence: {result['evidence_path']}")
            print(f"Crypto proof: {'PASS' if result['proof'].get('ok') else 'FAIL'}")
            for target in result["targets"]:
                suffix = f" ({'; '.join(target['failures'])})" if target["failures"] else ""
                print(f"{target['target']}: {'PASS' if target['ok'] else 'FAIL'}{suffix}")
            print("Result: PASS" if result["ok"] else "Result: FAIL")
        return 0 if result["ok"] else 1

    if args.zero_knowledge_device_proof:
        result = run_zero_knowledge_device_lifecycle_proof().as_dict()
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print("Zero-Knowledge Device Lifecycle Proof")
            print(f"Device enrollment: {result['device_enrollment_ok']}")
            print(f"Recovery secret restores key: {result['recovery_secret_restores_key']}")
            print(f"Wrong recovery secret rejected: {result['wrong_recovery_secret_rejected']}")
            print(f"Revoked device rejected after rotation: {result['revoked_device_rejected_after_rotation']}")
            print(f"Audit redacted: {result['audit_redacted']}")
            print("Result: PASS" if result["ok"] else "Result: FAIL")
        return 0 if result["ok"] else 1

    if args.release_spine_verify:
        result = verify_release_spine(
            suite="echolabs",
            evidence_root=args.release_spine_evidence_root,
            build_id=args.release_spine_build_id,
            suite_version=args.release_spine_suite_version,
        )
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print("AIBenchie Release Truth Spine")
            print(f"Build: {result['build_id']}")
            print(f"Status: {result['status']}")
            print(f"Verdict: {result['aibenchie_verdict']}")
            print(f"Evidence: {result['build_evidence_dir']}")
            print("Result: PASS" if result["ok"] else "Result: FAIL")
        return 0 if result["ok"] else 1

    if args.release_spine_promote_passing:
        result = promote_passing_candidate(
            build_id=args.release_spine_build_id,
            evidence_root=args.release_spine_evidence_root,
        )
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print("AIBenchie Release Truth Spine Promotion")
            print(f"Build: {result['build_id'] or '(missing)'}")
            if result.get("failures"):
                print("Failures:")
                for failure in result["failures"]:
                    print(f"- {failure}")
            print("Result: PASS" if result["ok"] else "Result: FAIL")
        return 0 if result["ok"] else 1

    if args.release_spine_validate_workflows:
        result = validate_workflow_matrix(
            matrix=args.release_spine_workflow_matrix,
            store_capabilities=args.release_spine_store_capabilities,
            evidence_root=args.release_spine_evidence_root,
            build_id=args.release_spine_build_id,
        )
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print("AIBenchie Workflow Matrix Validation")
            print(f"Build: {result['build_id']}")
            print(f"Workflows: {result['workflow_count']}")
            print(f"Prerelease workflows: {result['prerelease_count']}")
            if result["failures"]:
                print("Failures:")
                for failure in result["failures"]:
                    print(f"- {failure}")
            print("Result: PASS" if result["ok"] else "Result: FAIL")
        return 0 if result["ok"] else 1

    if args.release_report:
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

    if args.package_release_artifacts:
        required = {
            "wrapper": args.wrapper_package,
            "android": args.android_package,
            "public": args.public_package,
        }
        missing = [kind for kind, path in required.items() if not path]
        if missing:
            failure = {"ok": False, "failure": f"missing required package sources: {', '.join(missing)}"}
            print(json.dumps(failure, indent=2, sort_keys=True) if args.json else f"Result: FAIL ({failure['failure']})")
            return 1

        release_artifacts_output = (
            Path(args.release_package_output_dir) / "release-artifacts.json"
            if args.release_artifacts_output == "release-artifacts.json"
            else Path(args.release_artifacts_output)
        )
        try:
            result = package_release_artifacts(
                wrapper_source=Path(args.wrapper_package),
                android_source=Path(args.android_package),
                public_source=Path(args.public_package),
                output_dir=Path(args.release_package_output_dir),
                manifest_output=release_artifacts_output,
                sidecar_dir=Path(args.release_artifacts_sidecar_dir) if args.release_artifacts_sidecar_dir else None,
                signature_algorithm=args.release_artifact_signature_algorithm
                or "hmac-sha256-v1",
                signing_key_id=args.release_artifact_key_id or "release-attestation-key",
            )
        except Exception as exc:
            failure = {"ok": False, "failure": str(exc)}
            print(json.dumps(failure, indent=2, sort_keys=True) if args.json else f"Result: FAIL ({exc})")
            return 1
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print("AIBenchie Release Package Bundle")
            print(f"Output directory: {result['output_dir']}")
            print(f"Release artifacts: {result['release_artifacts']}")
            for kind, path in result["packages"].items():
                print(f"{kind}: {path}")
            print("Result: PASS")
        return 0

    if args.emit_release_artifacts:
        package_args = {
            "wrapper": args.wrapper_package,
            "android": args.android_package,
            "public": args.public_package,
        }
        packages = {kind: Path(path) for kind, path in package_args.items() if path}
        try:
            result = emit_release_artifacts_manifest(
                packages=packages,
                output=Path(args.release_artifacts_output),
                sidecar_dir=Path(args.release_artifacts_sidecar_dir) if args.release_artifacts_sidecar_dir else None,
                signature_algorithm=args.release_artifact_signature_algorithm
                or "hmac-sha256-v1",
                signing_key_id=args.release_artifact_key_id or "release-attestation-key",
            )
        except Exception as exc:
            failure = {"ok": False, "failure": str(exc)}
            print(json.dumps(failure, indent=2, sort_keys=True) if args.json else f"Result: FAIL ({exc})")
            return 1
        if args.json:
            print(json.dumps({"ok": True, "output": str(Path(args.release_artifacts_output)), "manifest": result}, indent=2, sort_keys=True))
        else:
            print("AIBenchie Release Artifacts Manifest")
            print(f"Output: {Path(args.release_artifacts_output)}")
            print(f"Artifacts: {len(result.get('artifacts', []))}")
            print("Result: PASS")
        return 0

    if args.verify_release_artifacts:
        manifest_path = Path(args.release_artifacts or args.release_artifacts_output)
        result = verify_release_artifacts_manifest(manifest_path).as_dict()
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print("AIBenchie Release Artifacts Verification")
            print(f"Manifest: {result['manifest']}")
            for artifact in result["artifacts"]:
                suffix = f" ({'; '.join(artifact['failures'])})" if artifact["failures"] else ""
                print(f"{artifact['kind'] or artifact['name']}: {'PASS' if artifact['ok'] else 'FAIL'}{suffix}")
            if result["failures"]:
                print("Failures:")
                for failure in result["failures"]:
                    print(f"- {failure}")
            print("Result: PASS" if result["ok"] else "Result: FAIL")
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
        if args.resource_manager_evidence:
            import os

            os.environ["AIBENCHIE_RESOURCE_MANAGER_EVIDENCE"] = args.resource_manager_evidence
        if args.resource_manager_require_runtime:
            import os

            os.environ["AIBENCHIE_RESOURCE_MANAGER_REQUIRE_RUNTIME"] = "1"
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
            runtime = result.get("runtime") or {}
            if runtime.get("required") or runtime.get("checks"):
                runtime_status = "PASS" if runtime.get("ok") else "FAIL"
                print(f"Runtime evidence: {runtime_status} ({runtime.get('path', '')})")
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

    if args.distribution_hygiene:
        result = run_distribution_hygiene_check(
            root=Path(args.distribution_hygiene_root) if args.distribution_hygiene_root else None,
            packages=[Path(item) for item in args.distribution_package],
        ).as_dict()
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print("AIBenchie Distribution Hygiene Gate")
            print(f"Root: {result['root']}")
            print(f"Scanned files: {result['scanned_files']}")
            print(f"Scanned packages: {result['scanned_packages']}")
            if result["findings"]:
                print("Findings:")
                for finding in result["findings"]:
                    print(
                        f"- {finding['source']}:{finding['path']} "
                        f"[{finding['rule']}] {finding['detail']}"
                    )
            print("Result: PASS" if result["ok"] else "Result: FAIL")
        return 0 if result["ok"] else 1

    if args.public_scoreboard:
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

    if args.suite_security_privacy:
        result = run_suite_security_privacy_from_env().as_dict()
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print("AIBenchie M36 Suite Security/Privacy Gate")
            print(f"Verdict: {result['releaseVerdict']}")
            for name, check in result["m36SecurityPrivacy"].items():
                suffix = ""
                if check.get("failures"):
                    suffix = f" ({'; '.join(check['failures'])})"
                print(f"{name}: {check['status'].upper()} [{check['severity']}]{suffix}")
            if result["knownPending"]:
                print("Known pending:")
                for group, items in result["knownPending"].items():
                    print(f"- {group}: {', '.join(items)}")
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

    if args.secure_signin_setup:
        result = run_secure_signin_setup_from_env().as_dict()
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print("Secure Sign-In Setup Gate")
            print(f"Android repo: {result['android_repo']}")
            print(f"Wrapper repo: {result['wrapper_repo']}")
            print(f"Public API: {result['public_api']}")
            for check in result["checks"]:
                status = "PASS" if check["ok"] else f"FAIL ({check['failure']})"
                print(f"{check['name']}: {status}")
            print("Result: PASS" if result["ok"] else "Result: FAIL")
        return 0 if result["ok"] else 1

    if args.auth_provider_config:
        if args.auth_provider_config_require_real:
            import os

            os.environ["AIBENCHIE_AUTH_PROVIDER_CONFIG_REQUIRE_REAL"] = "1"
        if args.auth_provider_config_device_proof:
            import os

            os.environ["AIBENCHIE_AUTH_PROVIDER_DEVICE_PROOF"] = args.auth_provider_config_device_proof
        if args.auth_provider_config_require_device_proof:
            import os

            os.environ["AIBENCHIE_AUTH_PROVIDER_CONFIG_REQUIRE_DEVICE_PROOF"] = "1"
        result = run_auth_provider_config_from_env().as_dict()
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print("EchoLabs Auth Provider Configuration Gate")
            print(f"Config: {result['config_path']}")
            print(f"Device proof: {result['device_proof_path']}")
            print(f"Template: {result['template']}")
            print(f"Require real values: {result['require_real']}")
            print(f"Require device proof: {result['require_device_proof']}")
            for check in result["checks"]:
                status = "PASS" if check["ok"] else f"FAIL ({check['failure']})"
                print(f"{check['name']}: {status}")
            print("Result: PASS" if result["ok"] else "Result: FAIL")
        return 0 if result["ok"] else 1

    if args.nullbridge_platform_adapters:
        result = run_nullbridge_platform_adapters_from_env()
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print("NullBridge Platform Backend Adapter Gate")
            print(f"Repo: {result.get('repo') or '(not found)'}")
            for platform, status in (result.get("m35PlatformAdapters") or {}).items():
                print(f"{platform}: {status}")
            print("Result: PASS" if result["ok"] else f"Result: FAIL ({result.get('failure')})")
        return 0 if result["ok"] else 1

    if args.echolabs_store:
        result = run_echolabs_store_from_env().as_dict()
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print("EchoLabs Store + Creative Workflows Alpha Gate")
            for name, check in result["echolabsStore"].items():
                suffix = f" ({'; '.join(check.get('failures', []))})" if check.get("failures") else ""
                print(f"{name}: {check['status'].upper()}{suffix}")
            print("Result: PASS" if result["ok"] else "Result: FAIL")
        return 0 if result["ok"] else 1

    if args.verify_deploy_plan:
        if not args.deploy_plan:
            result = {
                "ok": False,
                "plan_path": "",
                "checks": [
                    {
                        "name": "deploy_plan_path",
                        "ok": False,
                        "failure": "deploy_plan_path_missing",
                        "detail": {},
                    }
                ],
                "deploy_plan": {},
            }
        else:
            result = verify_deploy_plan(Path(args.deploy_plan)).as_dict()
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print("AIBenchie Deploy Plan Verifier")
            print(f"Plan: {result['plan_path'] or '(missing)'}")
            for check in result["checks"]:
                status = "PASS" if check["ok"] else f"FAIL ({check['failure']})"
                print(f"{check['name']}: {status}")
            print("Result: PASS" if result["ok"] else "Result: FAIL")
        return 0 if result["ok"] else 1

    if args.execute_deploy_addon:
        result = execute_deploy_addon(
            config_path=Path(args.deploy_addon_config) if args.deploy_addon_config else None,
            publish_confirm=args.deploy_publish_confirm,
        ).as_dict()
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print("AIBenchie Deploy Add-on Executor")
            print(f"Config: {result['config_path']}")
            print(f"Provider: {result['provider']}")
            print(f"Repository: {result['repository']}")
            print(f"Release tag: {result['release_tag']}")
            print(f"Published: {result['published']}")
            for check in result["checks"]:
                status = "PASS" if check["ok"] else f"FAIL ({check['failure']})"
                print(f"{check['name']}: {status}")
            print("Result: PASS" if result["ok"] else "Result: FAIL")
        return 0 if result["ok"] else 1

    if args.docker_support:
        result = run_docker_support_gate().as_dict()
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print("AIBenchie Docker Support Boundary Gate")
            print(f"Status: {result['status']}")
            for check in result["checks"]:
                status = "PASS" if check["ok"] else f"FAIL ({check['failure']})"
                print(f"{check['name']}: {status}")
            print("Result: PASS" if result["ok"] else "Result: FAIL")
        return 0 if result["ok"] else 1

    if args.docker_support_proof:
        result = validate_docker_support_proof(args.docker_support_proof).as_dict()
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print("AIBenchie Docker Supported-Mode Proof")
            print(f"Proof: {result['proof_path']}")
            print(f"Status: {result['status']}")
            for check in result["checks"]:
                status = "PASS" if check["ok"] else f"FAIL ({check['failure']})"
                print(f"{check['name']}: {status}")
            print("Result: PASS" if result["ok"] else "Result: FAIL")
        return 0 if result["ok"] else 1

    if args.android_release_gate:
        result = run_android_release_gate(
            repo=args.android_release_repo,
            apk=args.android_release_apk,
            update_notes=args.android_release_update_notes,
            package_name=args.android_release_package,
            base_url=args.android_release_base_url,
            output=args.android_release_output,
            adb=args.android_release_adb,
            adb_serial=args.android_release_adb_serial,
            require_device=args.android_release_require_device,
        )
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print("AIBenchie Android Release Gate")
            print(f"Repo: {result['repo']['name']} ({result['repo']['branch']} {str(result['repo']['commit'])[:12]})")
            print(f"Package: {result['android']['package'] or '(missing)'}")
            print(f"Base URL: {result['android']['base_url'] or '(missing)'}")
            if result.get("artifacts"):
                artifact = result["artifacts"][0]
                print(f"APK: {artifact['path']} sha256={artifact['sha256'][:12]}...")
            else:
                print("APK: missing")
            if result.get("notes"):
                print(f"Update notes: {result['notes'].get('latest_entry') or '(missing latest entry)'}")
            if result["android"].get("device_checked"):
                print(f"Device preflight: checked, installed={result['android'].get('installed_version') or 'unknown'}")
            else:
                print("Device preflight: skipped")
            for check in result["checks"]:
                label = check["status"].upper()
                suffix = f" ({check['failure']})" if check.get("failure") else ""
                print(f"{check['name']}: {label}{suffix}")
            print(f"Verdict: {result['verdict'].upper()}")
            print("Result: PASS" if result["ok"] else "Result: FAIL")
        return 0 if result["ok"] else 1

    if args.android_onboarding_e2e:
        result = run_android_onboarding_e2e(
            repo=args.android_onboarding_repo,
            output=args.android_onboarding_output,
            run_gradle=args.android_onboarding_run_gradle,
            gradle_timeout_seconds=args.android_onboarding_gradle_timeout,
        )
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print("AIBenchie Android Onboarding E2E Gate")
            print(f"Repo: {result['repo']['name']} ({result['repo'].get('branch', 'unknown')} {str(result['repo'].get('commit', 'unknown'))[:12]})")
            print(f"Contract: {result['contract']['name']}")
            print(f"Gradle requested: {result['contract']['gradle_requested']}")
            for check in result["checks"]:
                label = check["status"].upper()
                suffix = f" ({check['failure']})" if check.get("failure") else ""
                print(f"{check['name']}: {label}{suffix}")
            print(f"Verdict: {result['verdict'].upper()}")
            print("Result: PASS" if result["ok"] else "Result: FAIL")
        return 0 if result["ok"] else 1

    if args.android_real_device_ux_preflight:
        result = check_android_real_device_ux_preflight(
            adb=args.real_device_ux_adb,
            adb_serial=args.real_device_ux_adb_serial,
            package_name=args.real_device_ux_package,
        ).as_dict()
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print("AIBenchie Android Real-Device UX Preflight")
            print(f"Package: {result['package_name']}")
            print(f"Devices: {result['device_count']}")
            for check in result["checks"]:
                status = "PASS" if check["ok"] else f"FAIL ({check['failure']})"
                print(f"{check['name']}: {status}")
            print("Result: PASS" if result["ok"] else "Result: FAIL")
        return 0 if result["ok"] else 1

    if args.emit_android_real_device_ux_proof:
        try:
            result = emit_android_real_device_ux_proof(
                args.real_device_ux_output,
                adb=args.real_device_ux_adb,
                adb_serial=args.real_device_ux_adb_serial,
                package_name=args.real_device_ux_package,
                base_url=args.real_device_ux_base_url,
                app_version=args.real_device_ux_app_version,
                proof_id=args.real_device_ux_proof_id,
                signin_passed=args.real_device_ux_signin_passed,
                chat_passed=args.real_device_ux_chat_passed,
                runtime_provider=args.real_device_ux_runtime_provider,
                runtime_model=args.real_device_ux_runtime_model,
                runtime_endpoint_label=args.real_device_ux_runtime_endpoint_label,
                capture_screenshot=args.real_device_ux_capture_screenshot,
                artifact_dir=args.real_device_ux_artifact_dir or None,
            )
        except Exception as exc:
            result = {"ok": False, "output": args.real_device_ux_output, "failure": str(exc)}
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print("AIBenchie Android Real-Device UX Proof Generator")
            print(f"Output: {result.get('output', args.real_device_ux_output)}")
            if result.get("failure"):
                print(f"Failure: {result['failure']}")
            elif result.get("validation"):
                print(f"Proof id: {result['proof_id']}")
                validation = result.get("validation") or {}
                runtime = validation.get("runtime") if isinstance(validation.get("runtime"), dict) else {}
                app = validation.get("app") if isinstance(validation.get("app"), dict) else {}
                environment = validation.get("environment") if isinstance(validation.get("environment"), dict) else {}
                if app.get("version"):
                    print(f"App version: {app.get('version')}")
                if environment.get("base_url"):
                    print(f"Base URL: {environment.get('base_url')}")
                if runtime.get("model"):
                    print(f"Runtime model: {runtime.get('model')}")
                if runtime.get("provider"):
                    print(f"Runtime provider: {runtime.get('provider')}")
                if runtime.get("endpoint_label"):
                    print(f"Runtime endpoint: {runtime.get('endpoint_label')}")
                print("Validation: PASS" if result["ok"] else "Validation: FAIL")
            print("Result: PASS" if result.get("ok") else "Result: FAIL")
        return 0 if result.get("ok") else 1

    if args.real_device_ux_proof:
        result = validate_real_device_ux_proof(args.real_device_ux_proof).as_dict()
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print("AIBenchie Real-Device UX Proof")
            print(f"Proof: {result['proof_path']}")
            print(f"Platform: {result['platform']}")
            print(f"Proof id: {result['proof_id']}")
            app = result.get("app") if isinstance(result.get("app"), dict) else {}
            environment = result.get("environment") if isinstance(result.get("environment"), dict) else {}
            runtime = result.get("runtime") if isinstance(result.get("runtime"), dict) else {}
            if app.get("version"):
                print(f"App version: {app.get('version')}")
            if app.get("build_type"):
                print(f"App build type: {app.get('build_type')}")
            if environment.get("base_url"):
                print(f"Base URL: {environment.get('base_url')}")
            if environment.get("network"):
                print(f"Network: {environment.get('network')}")
            if runtime.get("model"):
                print(f"Runtime model: {runtime.get('model')}")
            if runtime.get("provider"):
                print(f"Runtime provider: {runtime.get('provider')}")
            if runtime.get("endpoint_label"):
                print(f"Runtime endpoint: {runtime.get('endpoint_label')}")
            for check in result["checks"]:
                status = "PASS" if check["ok"] else f"FAIL ({check['failure']})"
                print(f"{check['name']}: {status}")
            print("Result: PASS" if result["ok"] else "Result: FAIL")
        return 0 if result["ok"] else 1

    if args.deploy_addon:
        result = run_deploy_addon_check(
            config_path=Path(args.deploy_addon_config) if args.deploy_addon_config else None,
            require_token=args.deploy_addon_require_token,
        ).as_dict()
        plan_output = args.deploy_addon_plan_output.strip()
        if plan_output:
            result["deploy_plan_output"] = ""
            result["deploy_plan_written"] = False
            if result["ok"]:
                output_path = Path(plan_output)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(json.dumps(result["deploy_plan"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
                result["deploy_plan_output"] = str(output_path.resolve())
                result["deploy_plan_written"] = True
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print("AIBenchie Deploy Add-on Gate")
            print(f"Config: {result['config_path']}")
            print(f"Provider: {result['provider']}")
            print(f"Repository: {result['repository']}")
            print(f"Release tag: {result['release_tag']}")
            print(f"Dry run: {result['dry_run']}")
            for check in result["checks"]:
                status = "PASS" if check["ok"] else f"FAIL ({check['failure']})"
                print(f"{check['name']}: {status}")
            if result.get("deploy_plan_written"):
                print(f"Deploy plan: {result['deploy_plan_output']}")
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
