from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import yaml

from tests.conftest import ROOT
from training.build_v1_3_6_shared_contract_repair import (
    build_v1_3_6_shared_contract_repair,
)


DATA_DIR = ROOT / "data" / "sft_shared_contract_v1_3_6"
REPORTS_DIR = ROOT / "reports" / "training"
BLIND_HOLDOUT_DIR = ROOT / "evals" / "holdout" / "blind_v1_3"
BLIND_PROBE_DIR = ROOT / "evals" / "dpo_probes" / "blind_v1_3"
BLIND_PROBE_CONTRACTFIX_DIR = ROOT / "evals" / "dpo_probes" / "blind_v1_3_contractfix_v1_3_5"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def suite_hashes(directory: Path) -> dict[str, str]:
    return {path.name: sha256(path) for path in sorted(directory.glob("*.yaml"))}


def blind_prompt_texts() -> set[str]:
    prompt_values: set[str] = set()
    for folder in [BLIND_HOLDOUT_DIR, BLIND_PROBE_DIR, BLIND_PROBE_CONTRACTFIX_DIR]:
        for yaml_path in sorted(folder.glob("*.yaml")):
            payload = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
            prompt_values.add(payload["prompt"])
    return prompt_values


def test_build_v1_3_6_shared_contract_repair_generates_expected_outputs_without_mutation(tmp_path):
    scoring_path = ROOT / "evals" / "scoring.py"
    run_eval_path = ROOT / "evals" / "run_eval.py"
    blind_holdout_hashes_before = suite_hashes(BLIND_HOLDOUT_DIR)
    blind_probe_hashes_before = suite_hashes(BLIND_PROBE_DIR)
    blind_probe_contractfix_hashes_before = suite_hashes(BLIND_PROBE_CONTRACTFIX_DIR)
    scoring_hash_before = sha256(scoring_path)
    run_eval_hash_before = sha256(run_eval_path)

    output_dir = tmp_path / "sft_shared_contract_v1_3_6"
    summary = build_v1_3_6_shared_contract_repair(
        output_dir=output_dir,
        plan_report_path=tmp_path / "plan.md",
        data_review_path=tmp_path / "data_review.md",
    )

    assert summary["accepted_count"] == 12
    assert summary["traceable_count"] == 12
    assert summary["prepared_count"] == 12
    assert summary["repair_count"] == 6
    assert summary["retention_count"] == 6
    assert summary["exact_copies"] == 0
    assert summary["hard_fail_near_duplicate_count"] == 0

    source_traceable = read_jsonl(output_dir / "source_traceable_records.jsonl")
    messages = read_jsonl(output_dir / "sft_messages.jsonl")
    prepared = read_jsonl(output_dir / "sft_train_ready.jsonl")
    similarity_report = json.loads(
        (output_dir / "prompt_similarity_report.json").read_text(encoding="utf-8")
    )

    assert len(source_traceable) == 12
    assert len(messages) == 12
    assert len(prepared) == 12
    assert similarity_report["exact_copies"] == 0
    assert similarity_report["hard_fail_near_duplicate_count"] == 0

    roles = [record["metadata"]["repair_role"] for record in source_traceable]
    assert roles[:6] == ["shared_contract_repair"] * 6
    assert roles[6:] == ["retention_guard"] * 6
    assert Counter(roles) == {
        "shared_contract_repair": 6,
        "retention_guard": 6,
    }

    prompts = {record["messages"][0]["content"] for record in messages}
    assert prompts.isdisjoint(blind_prompt_texts())
    for record in messages:
        assistant = record["messages"][1]["content"]
        assert "policy_rationale:" in assistant
        assert "\n\nresponse:\n" in assistant

    assert suite_hashes(BLIND_HOLDOUT_DIR) == blind_holdout_hashes_before
    assert suite_hashes(BLIND_PROBE_DIR) == blind_probe_hashes_before
    assert suite_hashes(BLIND_PROBE_CONTRACTFIX_DIR) == blind_probe_contractfix_hashes_before
    assert sha256(scoring_path) == scoring_hash_before
    assert sha256(run_eval_path) == run_eval_hash_before


def test_v1_3_6_repo_artifacts_exist_and_match_expected_dataset_shape():
    required = [
        ROOT / "training" / "build_v1_3_6_shared_contract_repair.py",
        ROOT / "training" / "qlora_shared_contract_config_v1_3_6.yaml",
        DATA_DIR / "sft_messages.jsonl",
        DATA_DIR / "sft_train_ready.jsonl",
        DATA_DIR / "source_traceable_records.jsonl",
        DATA_DIR / "prompt_similarity_report.json",
        DATA_DIR / "MANIFEST.md",
        REPORTS_DIR / "V1_3_6_SHARED_CONTRACT_REPAIR_PLAN.md",
        REPORTS_DIR / "V1_3_6_SHARED_CONTRACT_REPAIR_DATA_REVIEW.md",
    ]
    for path in required:
        assert path.exists(), f"Missing v1.3.6 builder artifact: {path}"

    config = yaml.safe_load(
        (ROOT / "training" / "qlora_shared_contract_config_v1_3_6.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert config["starting_adapter"] == "models/adapters/lv7_sft_smoke_v1_0_5/"
    assert config["dataset"] == "data/sft_shared_contract_v1_3_6/sft_messages.jsonl"
    assert config["prepared_dataset"] == "data/sft_shared_contract_v1_3_6/sft_train_ready.jsonl"
    assert config["output_dir"] == "models/adapters/lv7_sft_shared_contract_v1_3_6/"

    source_traceable = read_jsonl(DATA_DIR / "source_traceable_records.jsonl")
    messages = read_jsonl(DATA_DIR / "sft_messages.jsonl")
    prepared = read_jsonl(DATA_DIR / "sft_train_ready.jsonl")
    similarity_report = json.loads(
        (DATA_DIR / "prompt_similarity_report.json").read_text(encoding="utf-8")
    )

    assert len(source_traceable) == 12
    assert len(messages) == 12
    assert len(prepared) == 12
    assert similarity_report["exact_copies"] == 0
    assert similarity_report["hard_fail_near_duplicate_count"] == 0

    roles = Counter(record["metadata"]["repair_role"] for record in source_traceable)
    assert roles == {
        "shared_contract_repair": 6,
        "retention_guard": 6,
    }
