from __future__ import annotations

import json
from pathlib import Path

from training import router_stage0_hard_positive_dataset as dataset


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_build_stage0_hard_positive_dataset_includes_misses_frontier_and_pairs(tmp_path):
    miss_audit = tmp_path / "miss_audit.json"
    frontier = tmp_path / "frontier.json"
    output_dir = tmp_path / "out"
    write_json(
        miss_audit,
        {
            "rows": [
                {
                    "id": "miss_run",
                    "text": "Run tests now.",
                    "expected_route": "console.run_command",
                    "miss_reason": "clear_direct_action_no_context",
                    "template_family": "miss:run",
                },
                {
                    "id": "miss_subtype",
                    "text": "Edit this image.",
                    "expected_route": "vision.edit_image",
                    "miss_reason": "subtype_only_confusion",
                    "template_family": "miss:image",
                },
            ]
        },
    )
    write_json(
        frontier,
        {
            "frontier": {
                "threshold_at_first_false_positive": {
                    "g03_confidence": 0.5,
                    "g03_margin": 0.0,
                    "g04_confidence": 0.9,
                    "g04_margin": 0.0,
                }
            },
            "results": [
                {
                    "thresholds": {
                        "g03_confidence": 0.5,
                        "g03_margin": 0.0,
                        "g04_confidence": 0.9,
                        "g04_margin": 0.0,
                    },
                    "rows": [
                        {
                            "id": "fp_chat",
                            "text": "Talk about running tests.",
                            "expected_route": "chat.no_action",
                            "expected_stage0_gate": "G00",
                            "stage0_gate": "G04",
                            "template_family": "frontier:chat",
                        }
                    ],
                }
            ],
        },
    )

    summary = dataset.build_stage0_hard_positive_dataset(
        miss_audit_path=miss_audit,
        frontier_paths=[frontier],
        output_dir=output_dir,
        split_id="test_split",
    )

    frontier_records = read_jsonl(output_dir / "router_stage0_frontier_hard_negatives_v1.jsonl")
    train_records = read_jsonl(output_dir / "router_stage0_hard_positive_train_v1.jsonl")
    dev_records = read_jsonl(output_dir / "router_stage0_hard_positive_dev_v1.jsonl")
    all_records = train_records + dev_records

    assert summary["clear_direct_action_miss_count"] == 1
    assert summary["frontier_first_false_positive_count"] == 1
    assert frontier_records[0]["must_not_emit_g04"] is True
    assert frontier_records[0]["training_role"] == "hard_negative"
    assert any(record["id"] == "stage0_miss_miss_run" and record["code"] == "R08" for record in all_records)
    assert {"R05", "R07", "R08", "R10", "R13"} <= set(summary["route_counts"])


def test_context_flags_for_code_uses_unknown_default_and_explicit_overrides():
    flags = dataset.context_flags_for_code("R05", {"ACTIVE_FILE": True})

    assert flags["HAS_IMAGE"] == "true"
    assert flags["ACTIVE_FILE"] == "true"
    assert flags["LAST_ASSISTANT_OFFERED_PATCH"] == "unknown"
