from __future__ import annotations

import json
from pathlib import Path

from training import router_granite_diagnostic_export as exporter


def write_result(path: Path) -> None:
    payload = {
        "results": [
            {
                "gate": "router_direct_action_boundaries_500",
                "model": "ibm-granite/granite-4.0-micro",
                "backend": "hf_transformers",
                "protocol": "route_code",
                "promotion_ready": False,
                "promotion_blockers": ["false_direct_actions_total"],
                "metrics": {
                    "protocol_validity": 1.0,
                    "semantic_route_accuracy": 0.87,
                    "false_direct_actions_total": 25,
                    "false_job_starts": 10,
                    "false_memory_writes": 15,
                },
                "diagnostics": {
                    "first_50_false_job_starts": [
                        {
                            "id": "job",
                            "category": "ambiguous",
                            "expected_route": "ask_clarifying_question",
                            "actual_route": "agent.start_job",
                            "raw": "R10",
                            "text": "Handle the risky part.",
                        }
                    ],
                    "first_50_false_memory_writes": [
                        {
                            "id": "mem",
                            "category": "hard_negative",
                            "expected_route": "chat.no_action",
                            "actual_route": "memory.save_preference",
                            "raw": "R13",
                            "text": "I prefer short answers, but do not remember that.",
                        }
                    ],
                },
            }
        ]
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_granite_diagnostic_archive_marks_candidate_not_promotable(tmp_path: Path):
    result = tmp_path / "granite.json"
    write_result(result)

    archive = exporter.build_granite_diagnostic_archive([result])

    assert archive["candidate"] == "granite_4_0_micro"
    assert archive["promotable"] is False
    assert archive["shadow_mode_eligible"] is False
    assert archive["dpo_cleanup_recommended"] is False
    assert archive["results"][0]["false_direct_actions_total"] == 25
    assert archive["training_candidates"]["false_job_start_examples"][0]["actual_route"] == "agent.start_job"
    assert archive["training_candidates"]["false_memory_write_examples"][0]["actual_route"] == "memory.save_preference"
