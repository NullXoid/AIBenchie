from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from aibenchie import gui_health


def _write_status(root, *, expires_delta: timedelta) -> None:
    now = datetime.now(timezone.utc)
    path = root / "public_export" / "suite-status.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "build_id": "test-build",
                "suite_version": "test",
                "generated_at": now.isoformat(),
                "expires_at": (now + expires_delta).isoformat(),
                "status": "passing",
                "aibenchie_verdict": "pass",
                "source_commits": {},
            }
        ),
        encoding="utf-8",
    )


def test_collect_pytest_health_reports_real_collection_count(tmp_path, monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="864 tests collected in 1.0s\n", stderr=""),
    )

    count, ok, failure = gui_health.collect_pytest_health(tmp_path)

    assert (count, ok, failure) == (864, True, "")


def test_repository_health_blocks_stale_status_and_live_policy_failures(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    _write_status(tmp_path, expires_delta=timedelta(days=-1))
    monkeypatch.setattr(gui_health, "collect_pytest_health", lambda *_args, **_kwargs: (864, True, ""))
    monkeypatch.setattr(
        gui_health,
        "run_generated_output_policy_check",
        lambda *_args, **_kwargs: SimpleNamespace(
            ok=False,
            budgets=[SimpleNamespace(ok=False, failure="file_count_exceeded")],
            forbidden_files=[],
            dirty_tracked_files=[SimpleNamespace(path="reports/runtime/test.md")],
        ),
    )
    monkeypatch.setattr(
        gui_health,
        "run_distribution_hygiene_check",
        lambda **_kwargs: SimpleNamespace(ok=True, findings=[], scanned_files=42),
    )

    health = gui_health.build_repository_health(tmp_path)

    assert health.collected_tests == 864
    assert health.collection_ok is True
    assert health.release_status == "stale"
    assert health.release_ok is False
    assert health.generated_output_ok is False
    assert health.distribution_ok is True
    assert health.critical_blockers == 2
    assert health.publish_mode == "Blocked"
    assert any("status_stale" in item for item in health.blockers)
    assert any("file_count_exceeded" in item for item in health.blockers)


def test_repository_health_is_eligible_only_when_every_live_gate_passes(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    _write_status(tmp_path, expires_delta=timedelta(days=1))
    monkeypatch.setattr(gui_health, "collect_pytest_health", lambda *_args, **_kwargs: (864, True, ""))
    monkeypatch.setattr(
        gui_health,
        "run_generated_output_policy_check",
        lambda *_args, **_kwargs: SimpleNamespace(ok=True, budgets=[], forbidden_files=[], dirty_tracked_files=[]),
    )
    monkeypatch.setattr(
        gui_health,
        "run_distribution_hygiene_check",
        lambda **_kwargs: SimpleNamespace(ok=True, findings=[], scanned_files=42),
    )

    health = gui_health.build_repository_health(tmp_path)

    assert health.critical_blockers == 0
    assert health.publish_mode == "Eligible"
    assert health.release_status == "passing"
