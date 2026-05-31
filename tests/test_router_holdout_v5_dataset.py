from __future__ import annotations

import json
from pathlib import Path

from evals import router_gate, router_hybrid_gate
from training import router_holdout_v5_dataset as holdout_v5


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_holdout_v5_builder_outputs_unique_clean_1000_cases(tmp_path: Path):
    manifest = holdout_v5.build_holdout_v5_dataset(output_dir=tmp_path)
    cases = read_jsonl(tmp_path / "router_holdout_1000_v5.jsonl")

    assert manifest["dataset"] == "router_holdout_1000_v5"
    assert len(cases) == 1000
    assert len({case["id"] for case in cases}) == 1000
    assert len({case["text"] for case in cases}) == 1000
    assert all(str(case["template_family"]).startswith("holdout_v5:") for case in cases)
    assert all(case["template_family"] != "legacy_unknown_family" for case in cases)
    assert manifest["category_counts"] == router_gate.SPLIT_1000
    assert manifest["route_counts"]["console.run_command"] > 0
    assert manifest["route_counts"]["memory.save_preference"] > 0
    assert Path(manifest["manifest"]).exists()


def test_hybrid_gate_can_load_holdout_v5_from_default_path(monkeypatch, tmp_path: Path):
    holdout_v5.build_holdout_v5_dataset(output_dir=tmp_path)
    monkeypatch.setattr(router_gate, "ROUTER_HOLDOUT_1000_V5_DEFAULT", tmp_path / "router_holdout_1000_v5.jsonl")

    cases = router_hybrid_gate.build_cases_for_hybrid_gate("router_holdout_1000_v5")

    assert len(cases) == 1000
    assert cases[0]["id"].startswith("v5_")
