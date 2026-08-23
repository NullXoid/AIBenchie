from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from aibenchie import audit_authority


NOW = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)


def catalog(tmp_path):
    path = tmp_path / "audit_catalog.json"
    path.write_text(
        json.dumps(
            {
                "schema": audit_authority.CATALOG_SCHEMA,
                "schema_version": "1.0",
                "catalog_version": "test",
                "audits": [
                    {
                        "id": "nullxoid.audit_freshness",
                        "version": "1.0.0",
                        "title": "Freshness",
                        "component": "NullXoid",
                        "scope": "repository",
                        "runner": "audit_freshness",
                        "mutates_target": False,
                        "release_blocking": True,
                        "default_ttl_seconds": 3600,
                        "timeout_seconds": 10,
                    },
                    {
                        "id": "nullxoid.runtime_processes",
                        "version": "1.0.0",
                        "title": "Processes",
                        "component": "NullXoid",
                        "scope": "runtime",
                        "runner": "runtime_processes",
                        "mutates_target": False,
                        "release_blocking": False,
                        "default_ttl_seconds": 900,
                        "timeout_seconds": 10,
                        "config": {
                            "runtimes": [
                                {
                                    "id": "current",
                                    "port": 8188,
                                    "desired_state": "running",
                                    "health_contract": "comfyui",
                                    "command_markers": ["ComfyUI", "main.py"],
                                    "tunnel_required": True,
                                },
                                {
                                    "id": "legacy",
                                    "port": 8196,
                                    "desired_state": "retired",
                                    "health_contract": "comfyui",
                                    "command_markers": ["ComfyUI", "main.py", "8196"],
                                    "tunnel_required": False,
                                },
                            ]
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def make_repo(tmp_path):
    root = tmp_path / "NullXoid"
    (root / "docs").mkdir(parents=True)
    (root / "backend").mkdir()
    (root / "docs" / "SITE_WIDE_TRUTH_AUDIT.md").write_text(
        "# Current Truth Audit\n\n- Audit date: 2026-08-01.\n- Source baseline: `1234567`.\n",
        encoding="utf-8",
    )
    (root / "backend" / "repo_audit.py").write_text(
        "from pathlib import Path\n"
        "REPO_ROOT = Path(__file__).resolve().parents[2]\n"
        'DEFAULT_ALLOWLIST = ["NullXoid", "src"]\n'
        "# De-dup and keep only existing dirs/files\n",
        encoding="utf-8",
    )
    return root


def test_catalog_rejects_duplicate_ids(tmp_path):
    path = catalog(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["audits"].append(dict(payload["audits"][0]))
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(audit_authority.AuditContractError, match="duplicate"):
        audit_authority.load_catalog(path)


def test_real_catalog_includes_aibenchie_self_audit():
    loaded = audit_authority.load_catalog()
    definitions = {item["id"]: item for item in loaded["audits"]}

    assert definitions["aibenchie.repository_health"]["runner"] == "repository_health"
    assert definitions["aibenchie.repository_health"]["release_blocking"] is True


def test_repository_health_runner_maps_live_blockers_to_release_findings(tmp_path):
    class FakeHealth:
        def as_dict(self):
            return {
                "generated_at": NOW.isoformat(),
                "collected_tests": 867,
                "collection_ok": True,
                "release_status": "stale",
                "release_ok": False,
                "generated_output_ok": False,
                "distribution_ok": True,
                "distribution_files_scanned": 1052,
                "critical_blockers": 2,
                "publish_mode": "Blocked",
                "blockers": ["Public suite status is stale.", "Generated-output policy failed."],
                "warnings": [],
            }

    findings, evidence = audit_authority.run_repository_health(tmp_path, health_builder=lambda _root: FakeHealth())

    assert [item["severity"] for item in findings] == ["high", "high"]
    assert [item["code"] for item in findings] == [
        "repository.health.blocker.1",
        "repository.health.blocker.2",
    ]
    assert evidence["collected_tests"] == 867
    assert evidence["publish_mode"] == "Blocked"


def test_execute_self_audit_uses_catalog_component_as_target_label(tmp_path, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        audit_authority,
        "target_identity",
        lambda _root, label="": captured.setdefault(
            "target", {"label": label, "source_commit": "abc1234", "working_tree_dirty": False}
        ),
    )
    monkeypatch.setattr(
        audit_authority,
        "run_repository_health",
        lambda _root: ([], {"collected_tests": 1, "publish_mode": "Eligible"}),
    )

    result, _evidence = audit_authority.execute_audit(
        "aibenchie.repository_health",
        target_root=tmp_path,
        now=NOW,
    )

    assert result["target"]["label"] == "AIBenchie"


def test_meta_audit_finds_stale_documents_and_broken_repo_audit(tmp_path, monkeypatch):
    root = make_repo(tmp_path)
    monkeypatch.setattr(
        audit_authority,
        "target_identity",
        lambda *_args, **_kwargs: {"label": "NullXoid", "source_commit": "abcdef123456", "working_tree_dirty": False},
    )

    findings, evidence = audit_authority.run_audit_freshness(root, now=NOW, max_current_age_days=7)
    codes = {item["code"] for item in findings}

    assert "audit_document.current_claim_expired" in codes
    assert "audit_document.source_commit_mismatch" in codes
    assert "repo_audit.root_outside_repository" in codes
    assert "repo_audit.allowlist_missing" in codes
    assert evidence["documents"][0]["path"] == "docs/SITE_WIDE_TRUTH_AUDIT.md"


def test_meta_audit_accepts_combined_existence_guard_and_header_scoped_history(tmp_path, monkeypatch):
    root = tmp_path / "NullXoid"
    (root / "backend").mkdir(parents=True)
    (root / "frontend").mkdir()
    (root / "docs").mkdir()
    (root / "backend" / "repo_audit.py").write_text(
        "from pathlib import Path\n"
        "REPO_ROOT = Path(__file__).resolve().parents[1]\n"
        'DEFAULT_ALLOWLIST = ["backend", "frontend"]\n'
        "# De-dup and keep only existing dirs/files\n"
        "for root in roots:\n"
        "    if root in seen or not root.exists():\n"
        "        continue\n",
        encoding="utf-8",
    )
    (root / "docs" / "REPAIR_TODO.md").write_text(
        "# Repair ledger\n\nA later row references historical evidence but this ledger is not frozen.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        audit_authority,
        "target_identity",
        lambda *_args, **_kwargs: {"label": "NullXoid", "source_commit": "abcdef123456", "working_tree_dirty": True},
    )

    findings, evidence = audit_authority.run_audit_freshness(root, now=NOW)

    assert not {item["code"] for item in findings} & {
        "repo_audit.allowlist_missing",
        "repo_audit.existence_contract_mismatch",
        "audit_document.frozen_baseline_modified",
    }
    repair = next(item for item in evidence["documents"] if item["path"] == "docs/REPAIR_TODO.md")
    assert repair["historical"] is False


def test_process_audit_classifies_expected_and_probable_orphan():
    config = {
        "runtimes": [
            {
                "id": "current",
                "port": 8188,
                "desired_state": "running",
                "health_contract": "comfyui",
                "command_markers": ["ComfyUI", "main.py"],
                "tunnel_required": True,
            },
            {
                "id": "legacy",
                "port": 8196,
                "desired_state": "retired",
                "health_contract": "comfyui",
                "command_markers": ["ComfyUI", "main.py", "8196"],
                "tunnel_required": False,
            },
        ]
    }
    snapshot = {
        "available": True,
        "listeners": {
            8188: {"pid": 10, "process_name": "python", "command": "python ComfyUI/main.py", "created_at_epoch": NOW.timestamp()},
            8196: {"pid": 11, "process_name": "python", "command": "python ComfyUI/main.py --port 8196", "created_at_epoch": NOW.timestamp()},
        },
        "tunnels": ["ssh -R 127.0.0.1:8188:127.0.0.1:8188 host"],
    }

    findings, evidence = audit_authority.run_runtime_processes(
        config,
        snapshot=snapshot,
        health_probe=lambda _port: {"healthy": True, "running": 0, "pending": 0, "version": "test"},
        now=NOW,
    )

    states = {item["id"]: item["classification"] for item in evidence["runtimes"]}
    assert states == {"current": "expected_idle", "legacy": "probable_orphan"}
    assert [item["code"] for item in findings] == ["runtime.probable_orphan"]
    assert all("command" not in item for item in evidence["runtimes"])
    assert all(item["command_fingerprint"] for item in evidence["runtimes"])


def test_immutable_result_detects_tampering_and_expiration(tmp_path):
    result = {
        "schema": audit_authority.RESULT_SCHEMA,
        "schema_version": "1.0",
        "audit_id": "nullxoid.audit_freshness",
        "generated_at": NOW.isoformat(),
        "expires_at": (NOW + timedelta(minutes=5)).isoformat(),
        "verdict": "pass",
        "title": "Freshness",
        "component": "NullXoid",
        "target": {"label": "NullXoid", "source_commit": "abc", "working_tree_dirty": False},
        "summary": {"finding_count": 0, "counts": {}},
        "findings": [],
    }
    evidence = {
        "schema": audit_authority.EVIDENCE_SCHEMA,
        "schema_version": "1.0",
        "audit_id": "nullxoid.audit_freshness",
        "generated_at": NOW.isoformat(),
        "evidence": {},
    }
    stored = audit_authority.write_immutable_result(
        result, evidence, result_root=tmp_path, run_id="20260823T120000Z-test", signing_key="secret"
    )

    current = audit_authority.read_latest_result(
        "nullxoid.audit_freshness", result_root=tmp_path, now=NOW, signing_key="secret"
    )
    assert current["state"] == "current"
    expired = audit_authority.read_latest_result(
        "nullxoid.audit_freshness",
        result_root=tmp_path,
        now=NOW + timedelta(minutes=6),
        signing_key="secret",
    )
    assert expired["state"] == "stale"

    result_path = tmp_path / "nullxoid.audit_freshness" / stored["run_id"] / "result.json"
    result_path.write_text("{}", encoding="utf-8")
    with pytest.raises(audit_authority.AuditContractError, match="artifact_hash_mismatch"):
        audit_authority.read_latest_result(
            "nullxoid.audit_freshness", result_root=tmp_path, now=NOW, signing_key="secret"
        )


def test_public_summary_redacts_internal_evidence():
    validated = {
        "state": "current",
        "reasons": [],
        "manifest": {"integrity": "hash_only"},
        "result": {
            "audit_id": "nullxoid.runtime_processes",
            "run_id": "run-test",
            "title": "Processes",
            "component": "NullXoid",
            "verdict": "blocked",
            "generated_at": NOW.isoformat(),
            "expires_at": (NOW + timedelta(minutes=5)).isoformat(),
            "target": {"label": "NullXoid", "source_commit": "abc", "working_tree_dirty": False},
            "summary": {"finding_count": 1},
            "findings": [
                {
                    "code": "runtime.probable_orphan",
                    "severity": "high",
                    "message": "Review runtime.",
                    "subject": "legacy",
                    "private_path": "C:/secret/path",
                    "command": "python secret.py",
                }
            ],
        },
    }

    summary = audit_authority.public_result_summary(validated)
    rendered = json.dumps(summary)
    assert "private_path" not in rendered
    assert "secret.py" not in rendered
    assert summary["mutates_target"] is False
