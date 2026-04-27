from __future__ import annotations

import re
import subprocess
from datetime import datetime, timedelta, timezone

from tests.conftest import ROOT
from training.release_fabric import (
    POLICIES_ROOT,
    load_json,
    sha256_file,
    validate_actions_policy,
    validate_auth_policy,
    validate_aibenchie_gates,
    validate_aibenchie_summary,
    validate_breakglass_grant,
    validate_nullbridge_audit_log,
    validate_nullbridge_capabilities,
    validate_nullbridge_registry,
    validate_policy_tree,
    validate_publisher_inputs,
    validate_privacy_levels,
    validate_release_manifest,
    validate_release_policy,
    validate_resource_policy,
    validate_runner_policy,
    validate_setup_policy,
    validate_source_hosts_policy,
    validate_suite_adapter_compliance,
    validate_workflow_text,
    authorize_nullbridge_route,
)


def valid_manifest(digest: str = "a" * 64) -> dict:
    return {
        "product": "NullXoid",
        "version": "1.4.2",
        "source_commit": "abc1234",
        "source_provider": "forgejo",
        "source_repo": "git.example.invalid/YOUR_ORG/NullXoid",
        "aibenchie_report": "reports/aibenchie/1.4.2/summary.json",
        "aibenchie_verdict": "ship_candidate",
        "artifacts": [{"name": "nullxoid-wrapper.zip", "sha256": digest}],
        "sbom": {"name": "sbom.spdx.json", "sha256": digest},
        "capability_policy_hash": digest,
        "privacy_policy_hash": digest,
        "nullbridge_registry_hash": digest,
        "signed_by": "release_hardware_key",
        "signed_at": "2026-04-24T18:00:00Z",
        "signature": "sig_example",
    }


def valid_aibenchie_summary() -> dict:
    gates = load_json(POLICIES_ROOT / "aibenchie-gates.json")
    return {
        "version": "1.4.2",
        "source_commit": "abc1234",
        "verdict": "ship_candidate",
        "signature": "aibenchie_sig",
        "critical_blocks": [],
        "tracks": {track: "pass" for track in gates["required_tracks"]},
    }


def valid_breakglass_grant() -> dict:
    return {
        "grant_type": "break_glass",
        "grant_id": "bg_01HX",
        "forgejo_repo": "YOUR_ORG/NullXoid",
        "source_commit": "abc1234",
        "requested_capability": "release.publish_candidate",
        "target": "forgejo_package_registry",
        "environment": "staging",
        "allowed_until": (datetime.now(timezone.utc) + timedelta(minutes=20)).isoformat(),
        "max_duration_minutes": 30,
        "network_profile": "throttled_quarantine",
        "egress_allowlist": ["forgejo.example.invalid", "nullbridge.example.invalid", "aibenchie.example.invalid"],
        "forbidden_actions": ["read_user_data", "export_secrets", "publish_unsigned_update"],
        "checkpoint_required": True,
        "aibenchie_event_ref": "reports/aibenchie/breakglass/bg_01HX/summary.json",
        "encrypted_forgejo_record": "reports/breakglass/bg_01HX/full-record.json.encrypted",
        "reason": "Emergency release validation",
        "signed_by_hardware_key": True,
    }


def test_policy_tree_and_workflows_are_valid():
    assert validate_policy_tree(ROOT) == []


def test_core_policies_fail_closed():
    assert validate_release_policy(load_json(POLICIES_ROOT / "release-policy.json")) == []
    assert validate_source_hosts_policy(load_json(POLICIES_ROOT / "source-hosts.json")) == []
    assert validate_setup_policy(load_json(POLICIES_ROOT / "setup-policy.json")) == []
    assert validate_auth_policy(load_json(POLICIES_ROOT / "auth-policy.json")) == []
    assert validate_runner_policy(load_json(POLICIES_ROOT / "runner-policy.json")) == []
    assert validate_actions_policy(load_json(POLICIES_ROOT / "actions-policy.json")) == []
    assert validate_aibenchie_gates(load_json(POLICIES_ROOT / "aibenchie-gates.json")) == []
    assert validate_resource_policy(load_json(POLICIES_ROOT / "resource-policy.json")) == []
    assert validate_privacy_levels(load_json(POLICIES_ROOT / "privacy-levels.json")) == []
    assert validate_nullbridge_registry(load_json(POLICIES_ROOT / "nullbridge-registry.json")) == []
    assert validate_nullbridge_capabilities(load_json(POLICIES_ROOT / "nullbridge-capabilities.json")) == []


def test_source_host_policy_supports_user_choice_without_persisted_credentials():
    policy = load_json(POLICIES_ROOT / "source-hosts.json")
    assert validate_source_hosts_policy(policy) == []
    providers = {provider["id"]: provider for provider in policy["allowed_providers"]}
    assert providers["forgejo"]["kind"] == "open_source_self_hosted"
    assert providers["gitea"]["kind"] == "open_source_self_hosted"
    assert providers["github"]["kind"] == "commercial_saas"
    assert policy["credential_storage"] == "session_only"
    assert policy["forbid_persisted_credentials"] is True

    broken = {
        "default_provider": "private_only",
        "recommended_provider": "private_only",
        "credential_storage": "persisted",
        "forbid_persisted_credentials": False,
        "allowed_providers": [{"id": "forgejo", "label": "Forgejo", "personal_config": "stored_secret"}],
    }
    errors = validate_source_hosts_policy(broken)
    assert "provider:missing:gitea" in errors
    assert "provider:missing:github" in errors
    assert "default_provider:not_allowed" in errors
    assert "credential_storage:not_session_only" in errors
    assert "forbid_persisted_credentials:not_enforced" in errors
    assert "forgejo:personal_config:not_ephemeral" in errors


def test_setup_policy_requires_guided_ui_and_no_saved_personal_credentials():
    valid = load_json(POLICIES_ROOT / "setup-policy.json")
    assert validate_setup_policy(valid) == []

    broken = {
        "setup_mode": "cli_first",
        "cli_required_for_standard_setup": True,
        "personal_config_storage": "tracked_config",
        "save_personal_credentials": True,
        "validate_before_save": False,
        "export_redacted_support_bundle": False,
        "steps": [
            {
                "id": "choose_source_provider",
                "label": "Source",
                "requires_cli": True,
                "stores_secret": True,
            }
        ],
    }
    errors = validate_setup_policy(broken)
    assert "setup_mode:not_guided_ui_first" in errors
    assert "cli_required_for_standard_setup:not_false" in errors
    assert "personal_config_storage:not_ephemeral" in errors
    assert "save_personal_credentials:not_false" in errors
    assert "validate_before_save:not_enforced" in errors
    assert "export_redacted_support_bundle:not_enabled" in errors
    assert "setup_step:missing:choose_auth_method" in errors
    assert "choose_source_provider:requires_cli" in errors
    assert "choose_source_provider:stores_secret" in errors


def test_auth_policy_requires_passkeys_secure_storage_and_backend_bridge_boundary():
    valid = load_json(POLICIES_ROOT / "auth-policy.json")
    assert validate_auth_policy(valid) == []

    broken = {
        "primary_user_auth": "password",
        "allowed_user_auth_methods": ["password_only"],
        "frontend_token_storage": {
            "website": "localstorage",
            "android": "shared_preferences"
        },
        "session_requirements": {
            "short_lived": False,
            "refresh_rotation": False,
            "logout_revokes_server_session": False
        },
        "nullbridge_auth_boundary": "frontends_allowed",
        "service_auth_boundary": "frontend_to_nullbridge",
        "forbidden_controls": [],
        "admin_requirements": [],
    }
    errors = validate_auth_policy(broken)
    assert "primary_user_auth:not_passkey" in errors
    assert "allowed_user_auth_methods:missing:passkey" in errors
    assert "allowed_user_auth_methods:missing:oidc_pkce" in errors
    assert "allowed_user_auth_methods:password_only_allowed" in errors
    assert "frontend_token_storage:website:invalid" in errors
    assert "frontend_token_storage:android:invalid" in errors
    assert "frontend_token_storage:browser_local_storage_allowed" in errors
    assert "session_requirements:short_lived:not_enforced" in errors
    assert "nullbridge_auth_boundary:not_platform_backends_only" in errors
    assert "service_auth_boundary:not_backend_to_nullbridge_only" in errors
    assert "forbidden_control:missing:frontend_nullbridge_service_credentials" in errors
    assert "admin_requirement:missing:hardware_key_for_admin" in errors


def valid_bridge_request(**overrides) -> dict:
    request = {
        "trace_id": "trc_release_gate",
        "caller_backend_id": "android_backend",
        "service_auth_valid": True,
        "acting_user": {
            "user_id": "usr_release_gate",
            "roles": ["user"],
            "workspace_id": "ws_release_gate",
            "platform": "android",
        },
        "capability": "chat.stream",
        "target": "ollama_service",
        "platform": "android",
    }
    request.update(overrides)
    return request


def test_nullbridge_policy_validators_fail_closed():
    broken_registry = {
        "required_backend_identities": ["website_backend"],
        "requires_service_auth": False,
        "deny_unknown_backends": False,
        "deny_unknown_targets": False,
        "deny_unknown_capabilities": False,
        "audit_required": False,
    }
    registry_errors = validate_nullbridge_registry(broken_registry)
    assert "identity:missing:android_backend" in registry_errors
    assert "requires_service_auth:not_enforced" in registry_errors
    assert "deny_unknown_capabilities:not_enforced" in registry_errors

    broken_capabilities = {
        "deny_by_default": False,
        "capabilities": [{"capability": "chat.stream", "allowed_callers": [], "allowed_platforms": [], "allowed_targets": []}],
    }
    capability_errors = validate_nullbridge_capabilities(broken_capabilities)
    assert "deny_by_default:not_enforced" in capability_errors
    assert "chat.stream:allowed_callers:missing" in capability_errors
    assert "chat.stream:requires_user_auth:not_enforced" in capability_errors
    assert "capability:missing:artifacts.send_to_codex" in capability_errors


def test_nullbridge_route_gate_allows_only_registered_authorized_requests():
    allowed = authorize_nullbridge_route(valid_bridge_request())
    assert allowed["decision"] == "allow"
    assert validate_nullbridge_audit_log(allowed) == []

    cases = [
        (valid_bridge_request(caller_backend_id="unknown_backend"), "unknown_backend"),
        (valid_bridge_request(service_auth_valid=False), "invalid_service_auth"),
        (valid_bridge_request(capability="unknown.capability"), "unknown_capability"),
        (valid_bridge_request(target="codex_service"), "target_not_allowed"),
        (valid_bridge_request(acting_user={"platform": "android", "roles": ["user"]}), "missing_user_context"),
        (
            valid_bridge_request(
                capability="artifacts.send_to_codex",
                target="codex_service",
                platform="android",
                acting_user={"user_id": "usr_release_gate", "roles": ["user"], "platform": "android"},
            ),
            "caller_not_allowed",
        ),
    ]
    for request, reason in cases:
        decision = authorize_nullbridge_route(request)
        assert decision["decision"] == "deny"
        assert decision["reason"] == reason
        assert validate_nullbridge_audit_log(decision) == []


def test_nullbridge_audit_log_rejects_secret_bearing_entries():
    entry = authorize_nullbridge_route(valid_bridge_request())
    entry["authorization"] = "Bearer eyJhbGciOi..."
    entry["cookie"] = "session=secret"
    errors = validate_nullbridge_audit_log(entry)
    assert "audit:secret_leak:authorization" in errors
    assert "audit:secret_leak:bearer" in errors
    assert "audit:secret_leak:cookie" in errors


def test_resource_policy_requires_bounded_leases_and_mobile_limits():
    valid = load_json(POLICIES_ROOT / "resource-policy.json")
    assert validate_resource_policy(valid) == []

    broken = {
        "deny_unbounded_resources": False,
        "lease_required_for_heavy_work": False,
        "default_deny_without_profile": False,
        "profiles": {
            "android_unbounded": {
                "platform": "android",
                "limits": {
                    "max_cpu_percent": 250,
                    "max_memory_mb": 8192,
                    "max_parallel_jobs": 10,
                    "max_duration_seconds": 3600,
                },
            }
        },
        "capability_classes": {
            "model.inference": {
                "requires_lease": False,
                "allowed_profiles": [],
            }
        },
    }
    errors = validate_resource_policy(broken)
    assert "deny_unbounded_resources:not_enforced" in errors
    assert "lease_required_for_heavy_work:not_enforced" in errors
    assert "default_deny_without_profile:not_enforced" in errors
    assert "android_unbounded:max_cpu_percent:over_100" in errors
    assert "android_unbounded:max_parallel_jobs:too_high" in errors
    assert "android_unbounded:mobile_memory_limit:too_high" in errors
    assert "android_unbounded:mobile_duration_limit:too_high" in errors
    assert "model.inference:lease:not_required" in errors
    assert "model.inference:allowed_profiles:missing" in errors


def test_privacy_levels_require_level_1_to_3_controls_and_e2ee_targets():
    valid = load_json(POLICIES_ROOT / "privacy-levels.json")
    assert validate_privacy_levels(valid) == []

    broken = {
        "levels": {
            "1": {"name": "Fast Secure", "required_controls": [], "forbidden_controls": []},
            "2": {"name": "Secure Remote", "required_controls": ["https_tls"], "forbidden_controls": []},
            "3": {"name": "ISP Destination Hidden", "required_controls": ["vpn_or_exit_node"], "forbidden_controls": []},
        },
        "e2ee_storage_targets": ["saved_chats"],
    }
    errors = validate_privacy_levels(broken)
    assert "privacy_level:missing:0" in errors
    assert "privacy_level:1:required_controls:missing" in errors
    assert "privacy_level:1:required_control_missing:https_tls" in errors
    assert "privacy_level:1:forbidden_control_missing:legacy_auth" in errors
    assert "privacy_level:2:required_control_missing:secure_sessions" in errors
    assert "privacy_level:2:required_control_missing:prompt_editor_enabled" in errors
    assert "privacy_level:3:required_control_missing:dns_through_tunnel" in errors
    assert "privacy_level:3:required_control_missing:kill_switch" in errors
    assert "e2ee_storage_target:missing:private_artifacts" in errors


def test_aibenchie_report_preview_includes_mascot_asset():
    preview = ROOT / "docs" / "AIBENCHIE_REPORT_PREVIEW.html"
    mascot = ROOT / "docs" / "assets" / "aibenchie-mascots.png"
    assert preview.is_file()
    assert mascot.is_file()
    assert mascot.stat().st_size > 100_000
    text = preview.read_text(encoding="utf-8")
    assert "AIBenchie Release Verdict" in text
    assert "assets/aibenchie-mascots.png" in text
    assert "Resource management" in text


def test_streamlit_entrypoint_is_public_safe():
    app = ROOT / "streamlit_app.py"
    requirements = ROOT / "requirements.txt"
    assert app.is_file()
    assert requirements.is_file()
    text = app.read_text(encoding="utf-8")
    assert "st.set_page_config" in text
    assert "https://github.com/NullXoid/AIBenchie" in text
    assert "st.secrets" not in text
    assert "NULLBRIDGE_SERVICE_TOKEN" not in text
    assert "localStorage" not in text
    assert "from aibenchie.local_ollama import" in text
    local_ollama = (ROOT / "aibenchie" / "local_ollama.py").read_text(encoding="utf-8")
    assert "/api/tags" in local_ollama
    assert "/api/generate" in local_ollama
    assert "MAX_PREDICT_TOKENS = 128" in local_ollama
    assert "MAX_PROMPT_CHARS = 500" in local_ollama
    assert "ALLOWED_LOCAL_OLLAMA_HOSTS" in local_ollama
    assert "streamlit==1.43.2" in requirements.read_text(encoding="utf-8")


def test_runner_policy_blocks_sensitive_power_on_arbitrary_code_runners():
    policy = {"runners": [{"name": "bad", "arbitrary_code": True, "signing_authority": True}]}
    errors = validate_runner_policy(policy)
    assert "bad:arbitrary_code_with_sensitive_power" in errors
    assert "bad:signing_without_hardware_key" in errors


def test_workflow_policy_rejects_mutable_actions_and_production_secret_refs():
    errors = validate_workflow_text(
        "jobs:\n  test:\n    runs-on: runner-ci-trusted\n    steps:\n      - uses: actions/checkout@main\n      - run: echo NULLBRIDGE_SERVICE_TOKEN\n"
    )
    assert "mutable_action_ref:actions/checkout@main" in errors
    assert "workflow:production_secret_reference" in errors


def test_release_manifest_requires_hardware_signature_and_valid_digests():
    assert validate_release_manifest(valid_manifest()) == []
    broken = valid_manifest("not-a-digest")
    broken["source_provider"] = "unapproved_host"
    broken["signed_by"] = "ci_runner"
    errors = validate_release_manifest(broken)
    assert "source_provider:not_allowed" in errors
    assert "signature:not_hardware_identity" in errors
    assert any("sha256" in error for error in errors)


def test_aibenchie_summary_requires_signature_tracks_and_no_critical_blocks():
    assert validate_aibenchie_summary(valid_aibenchie_summary()) == []
    broken = valid_aibenchie_summary()
    broken.pop("signature")
    broken["critical_blocks"] = ["release_without_hardware_signature"]
    broken["tracks"].pop("privacy")
    errors = validate_aibenchie_summary(broken)
    assert "signature:missing" in errors
    assert "critical_blocks:present" in errors
    assert "track:missing:privacy" in errors


def test_publisher_rejects_digest_mismatch_unsigned_verdict_and_commit_mismatch(tmp_path):
    artifact = tmp_path / "nullxoid-wrapper.zip"
    sbom = tmp_path / "sbom.spdx.json"
    artifact.write_bytes(b"wrapper")
    sbom.write_bytes(b'{"sbom": true}')
    manifest = valid_manifest()
    manifest["artifacts"][0]["sha256"] = sha256_file(artifact)
    manifest["sbom"]["sha256"] = sha256_file(sbom)
    report = valid_aibenchie_summary()
    assert validate_publisher_inputs(manifest, report, tmp_path) == []

    broken_manifest = valid_manifest("0" * 64)
    broken_report = valid_aibenchie_summary()
    broken_report["source_commit"] = "different"
    broken_report.pop("signature")
    errors = validate_publisher_inputs(broken_manifest, broken_report, tmp_path)
    assert "signature:missing" in errors
    assert "aibenchie_report:source_commit_mismatch" in errors
    assert "artifact[0]:sha256_mismatch" in errors
    assert "sbom:sha256_mismatch" in errors


def test_breakglass_requires_hardware_key_scope_quarantine_checkpoint_and_expiry():
    assert validate_breakglass_grant(valid_breakglass_grant()) == []
    broken = valid_breakglass_grant()
    broken["signed_by_hardware_key"] = False
    broken["requested_capability"] = "admin.audit"
    broken["target"] = "production_user_database"
    broken["environment"] = "production"
    broken["network_profile"] = "open_internet"
    broken["checkpoint_required"] = False
    broken["encrypted_forgejo_record"] = "reports/breakglass/bg/full-record.json"
    broken["allowed_until"] = "2020-01-01T00:00:00+00:00"
    errors = validate_breakglass_grant(broken)
    assert "hardware_key:required" in errors
    assert "capability:not_allowed" in errors
    assert "target:not_allowed" in errors
    assert "environment:not_allowed" in errors
    assert "network_profile:not_quarantined" in errors
    assert "checkpoint:required" in errors
    assert "encrypted_forgejo_record:not_encrypted" in errors
    assert "grant:expired" in errors


def test_tracked_release_fabric_files_do_not_embed_private_local_settings():
    tracked = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True).splitlines()
    banned_patterns = [
        re.compile(r"\b192\.168\.\d{1,3}\.\d{1,3}\b"),
        re.compile(r"\b10\.0\.2\.2\b"),
        re.compile("git\\." + "echolabs", re.IGNORECASE),
        re.compile("echolabs" + "\\.diy", re.IGNORECASE),
        re.compile(r"\b" + "Echo" + r"Labs\b"),
        re.compile(r"\b" + "Xaso" + r"moru\b", re.IGNORECASE),
        re.compile(r"\b" + "ka" + r"som\b", re.IGNORECASE),
        re.compile("C:" + r"\\Users\\", re.IGNORECASE),
        re.compile("C:" + r"\\\\Users\\\\", re.IGNORECASE),
        re.compile("/home/" + "echolabs", re.IGNORECASE),
    ]
    scanned_suffixes = {".html", ".json", ".yaml", ".yml", ".md", ".py", ".txt", ".toml"}
    offenders = []
    for relative in tracked:
        path = ROOT / relative
        if path.suffix.lower() not in scanned_suffixes:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in banned_patterns:
            if pattern.search(text):
                offenders.append(relative)
                break
    assert offenders == []


def test_suite_adapter_compliance_requires_acting_user_and_frontend_boundaries(tmp_path):
    suite = tmp_path / "suite"
    wrapper_backend = suite / "Felnx" / "NullXoid" / ".NullXoid" / "backend"
    wrapper_frontend = suite / "Felnx" / "NullXoid" / "src"
    windows_backend = suite / "AiAssistant" / "src" / "bridge"
    windows_frontend = suite / "AiAssistant" / "src" / "ui"
    android_backend = (
        suite
        / "NullXoidAndroid"
        / "app"
        / "src"
        / "main"
        / "java"
        / "com"
        / "nullxoid"
        / "android"
        / "backend"
    )
    android_adapter = android_backend / "nullbridge"
    android_frontend = (
        suite
        / "NullXoidAndroid"
        / "app"
        / "src"
        / "main"
        / "java"
        / "com"
        / "nullxoid"
        / "android"
        / "ui"
    )
    nullbridge = suite / "NullBridge"

    for directory in [wrapper_backend, wrapper_frontend, windows_backend, windows_frontend, android_adapter, android_frontend]:
        directory.mkdir(parents=True)
    (wrapper_backend / "nullbridge_adapter.py").write_text('body = {"actingUser": acting_user}\n', encoding="utf-8")
    (wrapper_frontend / "App.tsx").write_text("export const ok = true\n", encoding="utf-8")
    (windows_backend / "nullbridge_service_adapter.cpp").write_text('request.insert("actingUser", actingUser);\n', encoding="utf-8")
    (windows_frontend / "main_window.cpp").write_text("// UI talks to backend only\n", encoding="utf-8")
    (android_adapter / "NullBridgeAdapter.kt").write_text('put("actingUser", actingUser)\n', encoding="utf-8")
    (android_frontend / "Home.kt").write_text("// Compose UI talks to embedded backend only\n", encoding="utf-8")

    (nullbridge / "backend" / "infra" / "nullbridge" / "inbox").mkdir(parents=True)
    (nullbridge / "backend" / "infra" / "nullbridge" / "backend-registry.json").write_text("{}", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=nullbridge, check=True, capture_output=True, text=True)
    subprocess.run(["git", "add", "backend/infra/nullbridge/backend-registry.json"], cwd=nullbridge, check=True)

    assert validate_suite_adapter_compliance(suite) == []

    (wrapper_backend / "nullbridge_adapter.py").write_text('body = {"payload": payload}\n', encoding="utf-8")
    (wrapper_frontend / "App.tsx").write_text('fetch("/bridge/requests", { headers: { Authorization: "Bearer token" } })\n', encoding="utf-8")
    (nullbridge / "backend" / "infra" / "nullbridge" / "inbox" / "queued.json").write_text("{}", encoding="utf-8")
    subprocess.run(["git", "add", "backend/infra/nullbridge/inbox/queued.json"], cwd=nullbridge, check=True)

    errors = validate_suite_adapter_compliance(suite)
    assert "wrapper:acting_user:missing" in errors
    assert "wrapper:frontend:App.tsx:service_credential_reference" in errors
    assert "wrapper:frontend:App.tsx:direct_privileged_nullbridge_route" in errors
    assert "nullbridge:runtime_artifact_tracked:backend/infra/nullbridge/inbox/queued.json" in errors
