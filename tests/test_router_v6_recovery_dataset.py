from __future__ import annotations

import json
from pathlib import Path

from training import router_v6_recovery_dataset as recovery


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def result_path(path: Path) -> Path:
    write_json(
        path,
        {
            "results": [
                {
                    "rows": [
                        {
                            "id": "pref_fp",
                            "text": "My preference is short diagnostics for this chat only.",
                            "category": "memory_preference",
                            "expected_route": "chat.no_action",
                            "actual_route": "memory.save_preference",
                            "expected_stage0_gate": "G00",
                            "stage0_gate": "G04",
                            "action_family": "none",
                        },
                        {
                            "id": "miss_image",
                            "text": "Blur the username in the attached screenshot.",
                            "category": "media_route",
                            "expected_route": "vision.edit_image",
                            "actual_route": "vision.ocr_image",
                            "expected_stage0_gate": "G04",
                            "stage0_gate": "G03",
                            "action_family": "media_edit",
                            "context_flags": {"HAS_IMAGE": True},
                            "required_context_flags": ["HAS_IMAGE"],
                        },
                    ]
                }
            ]
        },
    )
    return path


def test_extract_stage0_recovery_records_captures_v6_false_memory_and_image_edit_miss(tmp_path: Path):
    rows = recovery.extract_stage0_recovery_records([result_path(tmp_path / "result.json")])

    by_id = {row["id"]: row for row in rows}
    false_memory = by_id["stage0_v6_false_risky_0001_pref_fp"]
    missed_image = by_id["stage0_v6_missed_risky_0002_miss_image"]

    assert false_memory["route"] == "chat.no_action"
    assert false_memory["must_not_emit_g04"] is True
    assert false_memory["rejected_route"] == "memory.save_preference"
    assert false_memory["template_family"].startswith("stage0_v6_recovery:preference_talk_not_memory")
    assert missed_image["route"] == "vision.edit_image"
    assert missed_image["stage0_label"] == "G04"
    assert missed_image["context_flags"]["HAS_IMAGE"] is True
    assert any(row["source"] == "stage0_v6_recovery_generated" for row in rows)
    assert any(row["route"] == "vision.ocr_image" for row in rows)
    assert any(row["template_family"].startswith("stage0_v6_recovery:generated:apply_that_unknown_context_negative") for row in rows)
    assert any(row["route"] == "console.edit_file" and row["context_flags"].get("LAST_ASSISTANT_OFFERED_PATCH") == "true" for row in rows)


def test_build_v6_recovery_dataset_writes_manifest_and_rows(tmp_path: Path):
    result = result_path(tmp_path / "result.json")
    output = tmp_path / "stage0.jsonl"

    manifest = recovery.build_stage0_recovery_dataset([result], output_path=output)
    rows = read_jsonl(output)

    assert manifest["dataset"] == "router_stage0_v6_recovery"
    assert manifest["must_not_emit_g04_count"] >= 1
    assert manifest["stage0_label_counts"]["G04"] >= 1
    assert manifest["route_counts"]["vision.edit_image"] >= 1
    assert rows
    assert Path(manifest["manifest"]).exists()
