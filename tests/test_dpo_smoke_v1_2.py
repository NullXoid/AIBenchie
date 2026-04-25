from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from tests.conftest import ROOT
from training import run_dpo_smoke
from training.plan_dpo_smoke_v1_1 import PRIMARY_CATEGORIES


REPORTS_DIR = ROOT / "reports" / "training"
DPO_DATA_DIR = ROOT / "data" / "dpo_smoke_v1_1"


def read_jsonl(path: Path):
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_v1_2_artifacts_exist():
    required = [
        ROOT / "training" / "run_dpo_smoke.py",
        REPORTS_DIR / "V1_2_DPO_PREFLIGHT.md",
        REPORTS_DIR / "V1_2_DPO_SMOKE_ANALYSIS.md",
        REPORTS_DIR / "DPO_READINESS_REVIEW_V1_2.md",
        ROOT / "training" / "dpo_smoke_config.yaml",
        ROOT / "docs" / "RUN_DPO_SMOKE.md",
        DPO_DATA_DIR / "dpo_train_ready.jsonl",
    ]
    for path in required:
        assert path.exists(), f"Missing v1.2 artifact: {path}"


def test_v1_2_train_ready_dataset_preserves_required_schema_and_balance():
    selected = read_jsonl(DPO_DATA_DIR / "dpo_pairs_selected.jsonl")
    train_ready = read_jsonl(DPO_DATA_DIR / "dpo_train_ready.jsonl")

    assert len(selected) == 28
    assert len(train_ready) == 28

    counts = Counter()
    for record in train_ready:
        assert sorted(record.keys()) == [
            "chosen",
            "id",
            "metadata",
            "primary_category",
            "prompt",
            "rejected",
            "scenario_id",
        ]
        assert record["primary_category"] in PRIMARY_CATEGORIES
        assert record["chosen"].startswith("policy_rationale:\n")
        assert record["rejected"].strip()
        assert record["metadata"]["scenario_name"] != "Ambiguous Goal"
        counts[record["primary_category"]] += 1

    assert counts == Counter({category: 4 for category in PRIMARY_CATEGORIES})


def test_v1_2_preflight_report_tracks_dependency_state_and_final_status():
    preflight = (REPORTS_DIR / "V1_2_DPO_PREFLIGHT.md").read_text(encoding="utf-8")
    review_lines = [
        line.strip()
        for line in (REPORTS_DIR / "DPO_READINESS_REVIEW_V1_2.md").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert "Selected pair count: `28`" in preflight
    assert any(
        marker in preflight
        for marker in ("`trl` available: `False`", "`trl` available: `True`")
    )
    assert "DPO is for preference behavior, not lexical-token repair." in preflight
    assert review_lines[-1] in run_dpo_smoke.ALLOWED_FINAL_STATUSES


def test_v1_2_config_is_execution_ready():
    config = run_dpo_smoke.load_config(ROOT / "training" / "dpo_smoke_config.yaml")

    assert config["base_model"] == "Qwen/Qwen2.5-1.5B-Instruct"
    assert config["starting_adapter"] == "models/adapters/lv7_sft_smoke_v1_0_5/"
    assert config["dataset"] == "data/dpo_smoke_v1_1/dpo_pairs_selected.jsonl"
    assert config["train_ready_dataset"] == "data/dpo_smoke_v1_1/dpo_train_ready.jsonl"
    assert config["output_dir"] == "models/adapters/lv7_dpo_smoke_v1_2/"
    assert config["stage"] == "dpo_smoke"
    assert config["save_adapter_only"] is True


def test_v1_2_selected_dataset_excludes_ambiguous_goal_and_lexical_repairs():
    audit = run_dpo_smoke.audit_selected_dataset(DPO_DATA_DIR / "dpo_pairs_selected.jsonl")

    assert audit["ambiguous_selected"] == []
    assert audit["lexical_selected"] == []
    assert audit["chosen_without_rationale"] == []
    assert audit["unclear_pairs"] == []
    assert audit["count"] == 28


def test_v1_2_full_pipeline_stops_before_train_when_preflight_is_not_ready():
    sequence = []

    def preflight():
        sequence.append("preflight")
        return run_dpo_smoke.StepResult(
            ok=False,
            status=run_dpo_smoke.BLOCKED_DPO_DEPENDENCY,
            summary={},
        )

    def prepare():
        sequence.append("prepare_data")
        return run_dpo_smoke.StepResult(
            ok=True,
            status=run_dpo_smoke.DPO_PREFLIGHT_READY,
            summary={},
        )

    def train():
        sequence.append("train")
        return run_dpo_smoke.StepResult(
            ok=True,
            status=run_dpo_smoke.DPO_PREFLIGHT_READY,
            summary={},
        )

    def evaluate():
        sequence.append("eval_adapter")
        return run_dpo_smoke.StepResult(
            ok=True,
            status=run_dpo_smoke.DPO_PREFLIGHT_READY,
            summary={},
        )

    result = run_dpo_smoke.run_full_pipeline(
        preflight_fn=preflight,
        prepare_data_fn=prepare,
        train_fn=train,
        eval_fn=evaluate,
    )

    assert result.status == run_dpo_smoke.BLOCKED_DPO_DEPENDENCY
    assert sequence == ["preflight", "prepare_data"]


def test_v1_2_probe_suite_has_minimum_coverage():
    probe_paths = sorted((ROOT / "evals" / "dpo_probes" / "v1_2").glob("*.yaml"))
    assert len(probe_paths) >= 14

    categories = Counter()
    for path in probe_paths:
        text = path.read_text(encoding="utf-8")
        for category in PRIMARY_CATEGORIES:
            if f"probe_category: {category}" in text:
                categories[category] += 1
                break

    assert categories == Counter({category: 2 for category in PRIMARY_CATEGORIES})


def test_gitignore_covers_v1_2_dpo_adapter_path():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "models/adapters/lv7_dpo_smoke_v1_2/" in gitignore


def test_v1_2_final_status_is_from_approved_set():
    lines = [
        line.strip()
        for line in (REPORTS_DIR / "DPO_READINESS_REVIEW_V1_2.md").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert lines[-1] in run_dpo_smoke.ALLOWED_FINAL_STATUSES
