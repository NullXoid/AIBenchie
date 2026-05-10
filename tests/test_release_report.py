from __future__ import annotations

import json

from aibenchie.release_report import (
    assert_public_safe,
    build_release_details,
    build_release_report,
    decrypt_full_report,
    load_artifact_attestation_manifest,
    render_release_details_markdown,
    write_release_report,
)
from tests.conftest import ROOT


def test_build_release_report_emits_public_safe_summary_and_encrypted_full_report():
    summary, encrypted, key = build_release_report(ROOT, run_trust_smoke=False)

    assert summary["verdict"] == "ship_candidate"
    assert summary["tracks"]["privacy"] == "pass"
    assert summary["tracks"]["e2ee_storage"] == "pass"
    assert summary["trust_smoke"]["ok"] == "skipped"
    assert summary["notification_smoke"]["ok"] == "skipped"
    assert "ciphertext" in encrypted
    assert "summary" not in encrypted
    assert_public_safe(summary)

    full = decrypt_full_report(key, encrypted)
    assert full["summary"]["source_commit"] == summary["source_commit"]
    assert full["privacy_proof"]["wrong_key_rejected"] is True


def test_build_release_report_surfaces_public_safe_deploy_plan_summary(tmp_path):
    plan = {
        "schema": "aibenchie.deploy-plan.v1",
        "dry_run": True,
        "provider": {
            "type": "forgejo",
            "base_url": "https://git.example.test",
            "repository": "EchoLabs/NullXoid",
        },
        "release": {
            "tag": "v1.2.3",
            "name": "EchoLabs Suite v1.2.3",
            "prerelease": True,
        },
        "assets": [
            {"kind": "wrapper", "name": "wrapper", "path": "wrapper.zip", "sha256": "a" * 64},
            {"kind": "android", "name": "android", "path": "app.apk", "sha256": "b" * 64},
            {"kind": "public", "name": "public", "path": "site.zip", "sha256": "c" * 64},
        ],
        "requires": [
            "passing_suite_verdict",
            "verified_release_artifact_attestation",
            "runtime_provider_token",
        ],
    }
    plan_path = tmp_path / "deploy-plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    summary, _, _ = build_release_report(ROOT, run_trust_smoke=False, env={"AIBENCHIE_DEPLOY_PLAN": str(plan_path)})

    assert summary["deploy_addon"] == {
        "ok": True,
        "status": "pass",
        "dry_run": True,
        "provider": "forgejo",
        "release_tag": "v1.2.3",
        "checks_total": 7,
        "failed_checks": 0,
        "asset_count": 3,
    }
    assert "runtime_provider_token" not in json.dumps(summary)
    assert_public_safe(summary)


def test_write_release_report_writes_summary_and_encrypted_full_report(tmp_path):
    result = write_release_report(ROOT, tmp_path, run_trust_smoke=False)

    assert result["ok"] is True
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    encrypted = json.loads((tmp_path / "full-report.json.encrypted").read_text(encoding="utf-8"))
    details = json.loads((tmp_path / "release-details.json").read_text(encoding="utf-8"))
    details_markdown = (tmp_path / "release-details.md").read_text(encoding="utf-8")
    key_text = (tmp_path / "full-report.key.local").read_text(encoding="utf-8")

    assert summary["verdict"] == "ship_candidate"
    assert encrypted["aad"]["kind"] == "aibenchie_full_report"
    assert details["aibenchie_verdict"]["suite_verdict"] == "ship_candidate"
    assert details["aibenchie_verdict"]["summary_path"] == "summary.json"
    assert details["aibenchie_verdict"]["full_report_path"] == "full-report.json.encrypted"
    assert details["release_package_attestation"]["status"] == "incomplete"
    assert details["release_package_attestation"]["artifact_count"] == 2
    assert details["artifacts"][0]["digest"]["algorithm"] == "sha256"
    assert len(details["artifacts"][0]["digest"]["value"]) == 64
    assert details["security_and_privacy"]["full_report_encrypted"] is True
    assert "## AIBenchie Verdict" in details_markdown
    assert "## Release Package Attestation" in details_markdown
    assert "| summary.json | sha256:" in details_markdown
    assert result["release_details"].endswith("release-details.json")
    assert result["release_details_markdown"].endswith("release-details.md")
    assert "Generated per-run report key" in key_text
    assert "ciphertext" in encrypted
    assert_public_safe(details)


def test_release_details_support_reconstructed_entries():
    summary, _, _ = build_release_report(ROOT, run_trust_smoke=False)
    details = build_release_details(
        ROOT,
        summary,
        release_id="retro-2026-04-27-aibenchie",
        release_type="reconstructed",
        scope="Reconstructed release evidence for earlier suite work.",
        retroactive=True,
        confidence="medium",
        operator="release-owner",
        reviewer="review-owner",
        evidence=["git log output", "AIBenchie summary"],
        unknowns=["artifact digest was not recorded at the original publish time"],
    )
    markdown = render_release_details_markdown(details)

    assert details["release_type"] == "reconstructed"
    assert details["retroactive"] is True
    assert details["confidence"] == "medium"
    assert details["evidence"] == ["git log output", "AIBenchie summary"]
    assert details["unknowns"] == ["artifact digest was not recorded at the original publish time"]
    assert "release_type: reconstructed" in markdown
    assert "- artifact digest was not recorded at the original publish time" in markdown
    assert_public_safe(details)


def test_release_details_support_fully_attestable_artifacts():
    summary, _, _ = build_release_report(ROOT, run_trust_smoke=False)
    details = build_release_details(
        ROOT,
        summary,
        artifacts=[
            {
                "name": "nullxoid-wrapper.zip",
                "path": "dist/nullxoid-wrapper.zip",
                "sha256": "a" * 64,
                "sbom": {"path": "dist/nullxoid-wrapper.spdx.json", "sha256": "b" * 64},
                "signature": {
                    "path": "dist/nullxoid-wrapper.zip.sig",
                    "sha256": "c" * 64,
                    "algorithm": "ssh-signature",
                    "key_id": "release_hardware_key",
                },
                "manifest": {"path": "dist/release-manifest.json", "sha256": "d" * 64},
            }
        ],
    )
    markdown = render_release_details_markdown(details)

    assert details["release_package_attestation"]["status"] == "fully_attestable"
    assert details["artifacts"][0]["attestation_status"] == "fully_attestable"
    assert details["release_package_attestation"]["missing_by_artifact"] == {}
    assert "fully_attestable" in markdown
    assert "dist/nullxoid-wrapper.spdx.json" in markdown
    assert "algorithm=ssh-signature" in markdown
    assert_public_safe(details)


def test_write_release_report_accepts_artifact_attestation_manifest(tmp_path):
    artifacts = [
        {
            "name": "nullxoid-companion.apk",
            "path": "dist/nullxoid-companion.apk",
            "sha256": "1" * 64,
            "sbom": {"path": "dist/nullxoid-companion.spdx.json", "sha256": "2" * 64},
            "signature": {
                "path": "dist/nullxoid-companion.apk.sig",
                "sha256": "3" * 64,
                "algorithm": "cosign",
                "key_id": "android_release_key",
            },
            "manifest": {"path": "dist/release-manifest.json", "sha256": "4" * 64},
        }
    ]
    manifest_path = tmp_path / "artifacts.json"
    manifest_path.write_text(json.dumps({"artifacts": artifacts}), encoding="utf-8")

    loaded_artifacts = load_artifact_attestation_manifest(manifest_path)
    result = write_release_report(ROOT, tmp_path / "release", run_trust_smoke=False, artifacts=loaded_artifacts)
    details = json.loads((tmp_path / "release" / "release-details.json").read_text(encoding="utf-8"))
    details_markdown = (tmp_path / "release" / "release-details.md").read_text(encoding="utf-8")

    assert result["ok"] is True
    assert details["release_package_attestation"]["status"] == "fully_attestable"
    assert details["release_package_attestation"]["artifact_count"] == 1
    assert details["artifacts"][0]["name"] == "nullxoid-companion.apk"
    assert details["artifacts"][0]["attestation_status"] == "fully_attestable"
    assert "nullxoid-companion.apk.sig" in details_markdown
    assert_public_safe(details)


def test_release_details_normalize_legacy_artifact_fields_as_incomplete_attestation():
    summary, _, _ = build_release_report(ROOT, run_trust_smoke=False)
    details = build_release_details(
        ROOT,
        summary,
        artifacts=[
            {
                "name": "legacy-package.zip",
                "digest": "sha256:" + "a" * 64,
                "sbom": "legacy-package.spdx.json",
                "manifest": "release-manifest.json",
            }
        ],
    )
    artifact = details["artifacts"][0]

    assert artifact["digest"]["value"] == "a" * 64
    assert artifact["sbom"]["path"] == "legacy-package.spdx.json"
    assert artifact["manifest"]["path"] == "release-manifest.json"
    assert artifact["attestation_status"] == "incomplete"
    assert details["release_package_attestation"]["status"] == "incomplete"
    assert "signature.reference" in artifact["missing_attestation_fields"]
    assert "sbom.sha256" in artifact["missing_attestation_fields"]
    assert_public_safe(details)


def test_public_summary_rejects_secret_like_markers():
    try:
        assert_public_safe({"authorization": "Bearer secret"})
    except ValueError as exc:
        assert "secret-like markers" in str(exc)
    else:
        raise AssertionError("expected secret marker rejection")

    try:
        assert_public_safe({"note": "private prompt text"})
    except ValueError as exc:
        assert "secret-like markers" in str(exc)
    else:
        raise AssertionError("expected prompt marker rejection")
