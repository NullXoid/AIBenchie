from __future__ import annotations

import json
from pathlib import Path

from training import router_r08_boundary_dataset as builder


def write_focused_result(path: Path) -> None:
    payload = {
        "gate": "router_console_semantics_350",
        "results": [
            {
                "rows": [
                    {
                        "id": "bad_run",
                        "text": "Explain run command safety.",
                        "expected_output": "R01",
                        "expected_route": "answer.question",
                        "actual_route": "console.run_command",
                        "category": "answer_question",
                        "action_family": "none",
                    },
                    {
                        "id": "true_run",
                        "text": "Run pytest now.",
                        "expected_output": "R08",
                        "expected_route": "console.run_command",
                        "actual_route": "console.run_command",
                        "category": "console_run_command",
                        "action_family": "run_command",
                    },
                ]
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_parse_ollama_show_captures_quantized_qwen_metadata():
    parsed = builder.parse_ollama_show(
        """
Model
  architecture        qwen3
  parameters          751.63M
  quantization        Q4_K_M

Capabilities
  completion
  thinking
"""
    )

    assert parsed["architecture"] == "qwen3"
    assert parsed["parameter_count"] == "751.63M"
    assert parsed["quantization"] == "Q4_K_M"
    assert parsed["capabilities"] == ["completion", "thinking"]


def test_serving_parity_preflight_blocks_quantized_ollama_promotion():
    preflight = builder.build_serving_parity_preflight(
        "Model\n  quantization        Q4_K_M\n",
        training_base="Qwen/Qwen3-0.6B",
        production_model="qwen3:0.6b",
    )

    assert preflight["promotion_eligible"] is False
    assert "production_model_is_quantized" in preflight["parity_blockers"]
    assert "merged_or_adapter_serving_parity_not_proven" in preflight["parity_blockers"]


def test_build_router_r08_boundary_dataset_outputs_balanced_artifacts(tmp_path: Path):
    focused = tmp_path / "focused.json"
    output_dir = tmp_path / "router_r08_boundary_v1"
    write_focused_result(focused)

    summary = builder.build_router_r08_boundary_dataset(
        focused_result_path=focused,
        output_dir=output_dir,
        ollama_show_text="Model\n  quantization        Q4_K_M\n",
    )

    train = read_jsonl(output_dir / "router_lora_train_v1.jsonl")
    dev = read_jsonl(output_dir / "router_lora_dev_console_semantics_v1.jsonl")
    dpo = read_jsonl(output_dir / "router_lora_dpo_pairs_v1.jsonl")
    holdout = read_jsonl(output_dir / "router_holdout_1000_v2.jsonl")

    assert summary["false_r08_count"] == 1
    assert summary["balanced_positive_count"] == 600
    assert len(train) == 601
    assert len(dev) == 350
    assert len(dpo) == 601
    assert len(holdout) == 1000
    assert train[0]["messages"][-1]["content"] == "R01"
    assert dpo[0]["chosen"] == "R01"
    assert dpo[0]["rejected"] == "R08"
    assert summary["chosen_route_counts"]["console.run_command"] == 100
