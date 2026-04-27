from __future__ import annotations

import json

from aibenchie.public_scoreboard import build_public_scoreboard, write_public_scoreboard


def write_report(root, name: str, payload: dict) -> None:
    path = root / "reports" / "runtime" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_public_scoreboard_keeps_latest_valid_report_per_class(tmp_path):
    write_report(
        tmp_path,
        "v1_5_1_chat_stream.json",
        {"milestone": "LV7 v1.5.1", "status": "READY", "runtime_record_count": 10, "runtime_pass_count": 10},
    )
    write_report(
        tmp_path,
        "v1_5_2_chat_stream.json",
        {"milestone": "LV7 v1.5.2", "status": "BLOCKED", "runtime_record_count": 10, "runtime_pass_count": 7},
    )
    write_report(
        tmp_path,
        "v1_5_3_resource_budget.json",
        {"milestone": "LV7 v1.5.3", "status": "READY", "record_count": 4, "pass_count": 3},
    )

    scoreboard, included, skipped = build_public_scoreboard(tmp_path)

    assert included == 3
    assert skipped == 0
    assert [item["key"] for item in scoreboard["classes"]] == ["chat_stream", "resource_budget"]
    chat = next(item for item in scoreboard["classes"] if item["key"] == "chat_stream")
    resource = next(item for item in scoreboard["classes"] if item["key"] == "resource_budget")
    assert chat["version"] == "v1_5_2"
    assert chat["result"] == "blocked"
    assert chat["score"] == 70
    assert resource["score"] == 75
    assert scoreboard["overall"]["class_count"] == 2
    assert scoreboard["overall"]["blocked_count"] == 1
    assert scoreboard["policy"]["raw_reports_published"] is False


def test_public_scoreboard_skips_non_result_reports(tmp_path):
    write_report(tmp_path, "v1_5_runtime_execution_manifest.json", {"suite_id": "runtime", "scenario_count": 2})
    write_report(tmp_path, "not_a_versioned_report.json", {"milestone": "LV7", "status": "READY"})

    scoreboard, included, skipped = build_public_scoreboard(tmp_path)

    assert included == 0
    assert skipped == 2
    assert scoreboard["classes"] == []
    assert scoreboard["overall"]["grade"] == "blocked"


def test_public_scoreboard_does_not_publish_secret_like_report(tmp_path):
    write_report(
        tmp_path,
        "v1_5_1_secret_leak_check.json",
        {"milestone": "LV7 v1.5.1", "status": "TOKEN_READY", "record_count": 1, "pass_count": 1},
    )

    scoreboard, included, skipped = build_public_scoreboard(tmp_path)

    assert included == 0
    assert skipped == 1
    assert scoreboard["classes"] == []


def test_write_public_scoreboard_creates_compact_export(tmp_path):
    write_report(
        tmp_path,
        "v1_5_1_release_readiness.json",
        {"milestone": "LV7 v1.5.1", "status": "READY", "release_baseline_ready": True},
    )
    output = tmp_path / "public_export" / "aibenchie-scoreboard.json"

    result = write_public_scoreboard(root=tmp_path, output=output)

    assert result.ok is True
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["overall"]["score"] == 100
    assert data["classes"][0]["source"] == "reports/runtime/v1_5_1_release_readiness.json"
