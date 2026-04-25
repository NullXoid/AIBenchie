from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tests.conftest import ROOT
from training import run_dpo_smoke
from training.analyze_v1_3_3_expanded_dpo_results import APPROVED_STATUSES


REPORTS_DIR = ROOT / "reports" / "training"
EXPANSION_DIR = ROOT / "data" / "dpo_expansion_v1_3_2"
SELECTED_DATASET = ROOT / "data" / "dpo_smoke_v1_1" / "dpo_pairs_selected.jsonl"
CONFIG_PATH = ROOT / "training" / "dpo_smoke_config_v1_3_3.yaml"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def last_nonempty_line(path: Path) -> str:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()][-1]


def test_v1_3_3_config_points_to_expanded_execution_targets():
    config = run_dpo_smoke.load_config(CONFIG_PATH)

    assert config["starting_adapter"] == "models/adapters/lv7_sft_smoke_v1_0_5/"
    assert config["dataset"] == "data/dpo_expansion_v1_3_2/dpo_pairs_selected_plus_expansion.jsonl"
    assert config["train_ready_dataset"] == "data/dpo_expansion_v1_3_2/dpo_train_ready.jsonl"
    assert config["output_dir"] == "models/adapters/lv7_dpo_smoke_v1_3_3/"
    assert config["max_steps"] == 12
    assert config["beta"] == 0.05
    assert config["learning_rate"] == 3.0e-6
    assert config["per_device_train_batch_size"] == 1
    assert config["gradient_accumulation_steps"] == 4
    assert config["decision_profile"] == run_dpo_smoke.DECISION_PROFILE_EXPANDED_V1_3_3
    assert config["dataset_profile"] == run_dpo_smoke.DATASET_PROFILE_EXPANDED_40


def test_v1_3_3_preflight_dataset_and_frozen_artifact_validation_are_ready():
    config = run_dpo_smoke.load_config(CONFIG_PATH)
    dataset_audit = run_dpo_smoke.audit_dataset_for_config(ROOT / config["dataset"], config)
    comparison_summary, comparison_blockers = run_dpo_smoke.validate_frozen_comparison_artifacts(config)
    comparison_summary["blockers"] = comparison_blockers
    status, blockers = run_dpo_smoke.determine_preflight_status(
        config,
        dataset_audit,
        run_dpo_smoke.probe_runtime_stack(config),
        comparison_summary,
    )

    assert dataset_audit["count"] == 40
    assert dataset_audit["prefix_matches"] is True
    assert dataset_audit["tail_count"] == 12
    assert dataset_audit["tail_category_counts"] == {
        "audit_evasion_vs_audit_preservation": 4,
        "overrefusal_vs_bounded_execute": 2,
        "unnecessary_escalation_vs_low_risk_execute": 2,
        "unsafe_compliance_vs_safe_challenge": 4,
    }
    assert not dataset_audit["ambiguous_selected"]
    assert not dataset_audit["lexical_selected"]
    assert not comparison_blockers
    assert comparison_summary["sft"]["blind_holdout"]["count"] == 33
    assert comparison_summary["sft"]["blind_probe"]["count"] == 14
    assert comparison_summary["dpo_v1_2_4"]["blind_holdout"]["count"] == 33
    assert comparison_summary["dpo_v1_2_4"]["blind_probe"]["count"] == 14
    assert status == run_dpo_smoke.DPO_PREFLIGHT_READY, blockers


def test_v1_3_3_prepare_data_writes_40_record_derivative_without_mutating_frozen_inputs():
    config = run_dpo_smoke.load_config(CONFIG_PATH)
    dataset_audit = run_dpo_smoke.audit_dataset_for_config(ROOT / config["dataset"], config)
    preexisting_hashes = {
        path.name: sha256(path)
        for path in EXPANSION_DIR.iterdir()
        if path.is_file() and path.name != "dpo_train_ready.jsonl"
    }
    selected_hash_before = sha256(SELECTED_DATASET)

    result = run_dpo_smoke.run_prepare_data(config, dataset_audit)

    assert result.ok is True
    assert result.summary["count"] == 40
    train_ready = read_jsonl(EXPANSION_DIR / "dpo_train_ready.jsonl")
    assert len(train_ready) == 40
    assert [record["id"] for record in train_ready[:28]] == [
        record["id"] for record in dataset_audit["pairs"][:28]
    ]
    assert [record["id"] for record in train_ready[28:]] == [
        record["id"] for record in dataset_audit["pairs"][28:]
    ]
    assert sha256(SELECTED_DATASET) == selected_hash_before
    for name, digest in preexisting_hashes.items():
        assert sha256(EXPANSION_DIR / name) == digest


def test_v1_3_3_repo_artifacts_exist_and_status_is_approved():
    required = [
        ROOT / "training" / "dpo_smoke_config_v1_3_3.yaml",
        ROOT / "training" / "analyze_v1_3_3_expanded_dpo_results.py",
        REPORTS_DIR / "V1_3_3_DPO_PREFLIGHT.md",
        REPORTS_DIR / "v1_3_3_dpo_run_config.json",
        REPORTS_DIR / "v1_3_3_dpo_train_log.jsonl",
        REPORTS_DIR / "v1_3_3_dpo_exact_eval_outputs.jsonl",
        REPORTS_DIR / "v1_3_3_dpo_exact_eval_results.jsonl",
        REPORTS_DIR / "v1_3_3_dpo_holdout_eval_outputs.jsonl",
        REPORTS_DIR / "v1_3_3_dpo_holdout_eval_results.jsonl",
        REPORTS_DIR / "v1_3_3_dpo_blind_holdout_outputs.jsonl",
        REPORTS_DIR / "v1_3_3_dpo_blind_holdout_results.jsonl",
        REPORTS_DIR / "v1_3_3_dpo_blind_probe_outputs.jsonl",
        REPORTS_DIR / "v1_3_3_dpo_blind_probe_results.jsonl",
        REPORTS_DIR / "V1_3_3_EXPANDED_DPO_SMOKE_ANALYSIS.md",
        REPORTS_DIR / "DPO_READINESS_REVIEW_V1_3_3.md",
    ]
    for path in required:
        assert path.exists(), f"Missing v1.3.3 artifact: {path}"

    assert last_nonempty_line(REPORTS_DIR / "DPO_READINESS_REVIEW_V1_3_3.md") in APPROVED_STATUSES


def test_gitignore_covers_v1_3_3_adapter_path():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "models/adapters/lv7_dpo_smoke_v1_3_3/" in gitignore
