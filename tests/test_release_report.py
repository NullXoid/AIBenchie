from __future__ import annotations

import json

from aibenchie.release_report import (
    assert_public_safe,
    build_release_details,
    build_release_report,
    decrypt_full_report,
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
    assert details["security_and_privacy"]["full_report_encrypted"] is True
    assert "## AIBenchie Verdict" in details_markdown
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
