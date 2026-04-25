from __future__ import annotations

import json

from aibenchie.release_report import (
    assert_public_safe,
    build_release_report,
    decrypt_full_report,
    write_release_report,
)
from tests.conftest import ROOT


def test_build_release_report_emits_public_safe_summary_and_encrypted_full_report():
    summary, encrypted, key = build_release_report(ROOT, run_trust_smoke=False)

    assert summary["verdict"] == "ship_candidate"
    assert summary["tracks"]["privacy"] == "pass"
    assert summary["tracks"]["e2ee_storage"] == "pass"
    assert summary["trust_smoke"]["ok"] == "skipped"
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
    key_text = (tmp_path / "full-report.key.local").read_text(encoding="utf-8")

    assert summary["verdict"] == "ship_candidate"
    assert encrypted["aad"]["kind"] == "aibenchie_full_report"
    assert "Generated per-run report key" in key_text
    assert "ciphertext" in encrypted


def test_public_summary_rejects_secret_like_markers():
    try:
        assert_public_safe({"authorization": "Bearer secret"})
    except ValueError as exc:
        assert "secret-like markers" in str(exc)
    else:
        raise AssertionError("expected secret marker rejection")
