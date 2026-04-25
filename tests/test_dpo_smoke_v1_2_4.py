from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tests.conftest import ROOT
from training import run_dpo_smoke


REPORTS_DIR = ROOT / "reports" / "training"
DPO_DATA_DIR = ROOT / "data" / "dpo_smoke_v1_1"
CONFIG_PATH = ROOT / "training" / "dpo_smoke_config_v1_2_4.yaml"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_v1_2_4_artifacts_exist():
    required = [
        ROOT / "training" / "dpo_smoke_config_v1_2_4.yaml",
        REPORTS_DIR / "V1_2_4_DPO_PREFLIGHT.md",
        REPORTS_DIR / "v1_2_4_ambiguous_goal_precheck.json",
        REPORTS_DIR / "v1_2_4_ambiguous_goal_postcheck.json",
        REPORTS_DIR / "V1_2_4_DPO_SMOKE_ANALYSIS.md",
        REPORTS_DIR / "DPO_READINESS_REVIEW_V1_2_4.md",
        REPORTS_DIR / "v1_2_4_dpo_exact_eval_outputs.jsonl",
        REPORTS_DIR / "v1_2_4_dpo_exact_eval_results.jsonl",
        REPORTS_DIR / "v1_2_4_dpo_holdout_eval_outputs.jsonl",
        REPORTS_DIR / "v1_2_4_dpo_holdout_eval_results.jsonl",
        REPORTS_DIR / "v1_2_4_dpo_probe_outputs.jsonl",
        REPORTS_DIR / "v1_2_4_dpo_probe_results.jsonl",
    ]
    for path in required:
        assert path.exists(), f"Missing v1.2.4 artifact: {path}"


def test_v1_2_4_config_is_fixed_to_smaller_retry_settings():
    config = run_dpo_smoke.load_config(CONFIG_PATH)

    assert config["starting_adapter"] == "models/adapters/lv7_sft_smoke_v1_0_5/"
    assert config["output_dir"] == "models/adapters/lv7_dpo_smoke_v1_2_4/"
    assert config["dataset"] == "data/dpo_smoke_v1_1/dpo_pairs_selected.jsonl"
    assert config["train_ready_dataset"] == "data/dpo_smoke_v1_1/dpo_train_ready.jsonl"
    assert config["max_steps"] == 12
    assert config["beta"] == 0.05
    assert config["learning_rate"] == 3.0e-6
    assert config["per_device_train_batch_size"] == 1
    assert config["gradient_accumulation_steps"] == 4
    assert config["save_adapter_only"] is True
    assert config["adapter_run_type"] == "v1_2_4_dpo_smoke"


def test_gitignore_covers_v1_2_4_adapter_path():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "models/adapters/lv7_dpo_smoke_v1_2_4/" in gitignore


def test_prepare_data_does_not_mutate_selected_dataset():
    config = run_dpo_smoke.load_config(CONFIG_PATH)
    selected_path = ROOT / config["dataset"]
    before = sha256(selected_path)
    audit = run_dpo_smoke.audit_selected_dataset(selected_path)

    result = run_dpo_smoke.run_prepare_data(config, audit)

    assert result.ok is True
    assert result.summary["count"] == 28
    assert sha256(selected_path) == before


def test_v1_2_4_ambiguous_goal_check_artifacts_cover_all_required_cases():
    required_cases = {
        "ambiguous_goal_001",
        "ambiguous_goal_001_holdout_001",
        "ambiguous_goal_001_holdout_002",
        "ambiguous_goal_001_holdout_003",
    }
    for name in ("v1_2_4_ambiguous_goal_precheck.json", "v1_2_4_ambiguous_goal_postcheck.json"):
        payload = read_json(REPORTS_DIR / name)
        observed = {entry["case_id"] for entry in payload["cases"]}
        assert observed == required_cases
        assert isinstance(payload["all_clarify"], bool)
        assert isinstance(payload["all_pass"], bool)
        assert sorted(payload["mode_regressions"]) == sorted(
            case["case_id"]
            for case in payload["cases"]
            if case["observed_mode"] != "clarify"
        )


def test_v1_2_4_output_path_is_new_and_adapter_exists():
    config = run_dpo_smoke.load_config(CONFIG_PATH)
    assert config["output_dir"] != "models/adapters/lv7_dpo_smoke_v1_2/"
    assert (ROOT / config["output_dir"]).exists()


def test_v1_2_4_eval_outputs_and_results_exist():
    for suffix in (
        "exact_eval_outputs.jsonl",
        "exact_eval_results.jsonl",
        "holdout_eval_outputs.jsonl",
        "holdout_eval_results.jsonl",
        "probe_outputs.jsonl",
        "probe_results.jsonl",
    ):
        assert (REPORTS_DIR / f"v1_2_4_dpo_{suffix}").exists()


def test_v1_2_4_final_status_is_from_approved_set():
    lines = [
        line.strip()
        for line in (REPORTS_DIR / "DPO_READINESS_REVIEW_V1_2_4.md").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert lines[-1] in run_dpo_smoke.ALLOWED_FINAL_STATUSES


def test_v1_2_4_train_ready_dataset_still_has_28_records():
    train_ready = read_jsonl(DPO_DATA_DIR / "dpo_train_ready.jsonl")
    assert len(train_ready) == 28
    for record in train_ready:
        assert record["primary_category"] in run_dpo_smoke.PRIMARY_CATEGORIES
        assert record["chosen"].startswith("policy_rationale:\n")
        assert record["rejected"].strip()
