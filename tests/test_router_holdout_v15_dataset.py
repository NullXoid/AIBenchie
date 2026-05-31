from __future__ import annotations

import json
from pathlib import Path

from evals import router_gate, router_hybrid_gate
from training import router_holdout_v15_dataset as holdout_v15


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_holdout_v15_builder_outputs_unique_clean_1000_cases_with_intent_method_metadata(tmp_path: Path):
    manifest = holdout_v15.build_holdout_v15_dataset(output_dir=tmp_path)
    cases = read_jsonl(tmp_path / "router_holdout_1000_v15.jsonl")

    assert manifest["dataset"] == "router_holdout_1000_v15"
    assert len(cases) == 1000
    assert len({case["id"] for case in cases}) == 1000
    assert len({case["text"] for case in cases}) == 1000
    assert all(str(case["template_family"]).startswith("holdout_v15:") for case in cases)
    assert manifest["category_counts"] == router_gate.SPLIT_1000
    hard_negatives = [case for case in cases if case["category"] == "hard_negative"]
    assert {case["expected_route"] for case in hard_negatives} == {"answer.question", "chat.no_action"}
    assert all(case["expected_intent"] for case in cases)
    assert all(case["allowed_methods"] for case in cases)
    assert all(case["preferred_method"] for case in cases)
    assert Path(manifest["manifest"]).exists()


def test_hybrid_gate_can_load_holdout_v15_from_default_path(monkeypatch, tmp_path: Path):
    holdout_v15.build_holdout_v15_dataset(output_dir=tmp_path)
    monkeypatch.setattr(router_gate, "ROUTER_HOLDOUT_1000_V15_DEFAULT", tmp_path / "router_holdout_1000_v15.jsonl")

    cases = router_hybrid_gate.build_cases_for_hybrid_gate("router_holdout_1000_v15")

    assert len(cases) == 1000
    assert cases[0]["id"].startswith("v15_")
