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
    validate_aibenchie_gates,
    validate_aibenchie_summary,
    validate_breakglass_grant,
    validate_policy_tree,
    validate_publisher_inputs,
    validate_release_manifest,
    validate_release_policy,
    validate_resource_policy,
    validate_runner_policy,
    validate_workflow_text,
)


def valid_manifest(digest: str = "a" * 64) -> dict:
    return {
        "product": "NullXoid",
        "version": "1.4.2",
        "source_commit": "abc1234",
        "forgejo_repo": "forgejo.example.invalid/YOUR_ORG/NullXoid",
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
    assert validate_runner_policy(load_json(POLICIES_ROOT / "runner-policy.json")) == []
    assert validate_actions_policy(load_json(POLICIES_ROOT / "actions-policy.json")) == []
    assert validate_aibenchie_gates(load_json(POLICIES_ROOT / "aibenchie-gates.json")) == []
    assert validate_resource_policy(load_json(POLICIES_ROOT / "resource-policy.json")) == []


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
    broken["signed_by"] = "ci_runner"
    errors = validate_release_manifest(broken)
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
