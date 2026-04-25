from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import yaml

from tests.conftest import ROOT
from training.build_v1_3_2_dpo_expansion import (
    APPROVED_STATUSES,
    STATUS_READY,
    build_v1_3_2_dpo_expansion,
)
from training.plan_dpo_smoke_v1_1 import audit_pair


REPORTS_DIR = ROOT / "reports" / "training"
EXPANSION_DIR = ROOT / "data" / "dpo_expansion_v1_3_2"
SELECTED_DATASET = ROOT / "data" / "dpo_smoke_v1_1" / "dpo_pairs_selected.jsonl"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def last_nonempty_line(path: Path) -> str:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ][-1]


def blind_prompt_texts() -> set[str]:
    prompt_values: set[str] = set()
    for folder in [
        ROOT / "evals" / "holdout" / "blind_v1_3",
        ROOT / "evals" / "dpo_probes" / "blind_v1_3",
    ]:
        for yaml_path in sorted(folder.glob("*.yaml")):
            payload = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
            prompt_values.add(payload["prompt"])
    return prompt_values


def test_build_v1_3_2_dpo_expansion_generates_expected_outputs_without_mutation(tmp_path):
    run_eval_path = ROOT / "evals" / "run_eval.py"
    selected_hash_before = sha256(SELECTED_DATASET)
    run_eval_hash_before = sha256(run_eval_path)

    temp_expansion_dir = tmp_path / "dpo_expansion_v1_3_2"
    summary = build_v1_3_2_dpo_expansion(
        selected_dpo_path=SELECTED_DATASET,
        expansion_dir=temp_expansion_dir,
        plan_report_path=tmp_path / "plan.md",
        audit_report_path=tmp_path / "audit.md",
        decision_report_path=tmp_path / "decision.md",
        config_path=tmp_path / "dpo_smoke_config_v1_3_2.yaml",
    )

    assert summary["status"] == STATUS_READY
    assert summary["status"] in APPROVED_STATUSES
    assert summary["accepted_count"] == 12
    assert summary["rejected_count"] == 0
    assert summary["combined_count"] == 40
    assert summary["exact_copies"] == 0
    assert summary["hard_fail_near_duplicate_count"] == 0
    assert summary["selected_hash_before"] == summary["selected_hash_after"]
    assert not summary["aggregate_issues_found"]

    accepted = read_jsonl(temp_expansion_dir / "dpo_pairs_expansion.jsonl")
    combined = read_jsonl(temp_expansion_dir / "dpo_pairs_selected_plus_expansion.jsonl")
    similarity_report = json.loads(
        (temp_expansion_dir / "prompt_similarity_report.json").read_text(encoding="utf-8")
    )

    assert len(accepted) == 12
    assert len(combined) == 40
    assert similarity_report["exact_copies"] == 0
    assert similarity_report["hard_fail_near_duplicate_count"] == 0

    counts = Counter(audit_pair(record).primary_category for record in accepted)
    assert counts == {
        "overrefusal_vs_bounded_execute": 2,
        "unnecessary_escalation_vs_low_risk_execute": 2,
        "audit_evasion_vs_audit_preservation": 4,
        "unsafe_compliance_vs_safe_challenge": 4,
    }

    assert all(record["metadata"]["scenario_name"] != "Ambiguous Goal" for record in accepted)
    assert {record["prompt"] for record in accepted}.isdisjoint(blind_prompt_texts())

    config = yaml.safe_load((tmp_path / "dpo_smoke_config_v1_3_2.yaml").read_text(encoding="utf-8"))
    assert config["starting_adapter"] == "models/adapters/lv7_sft_smoke_v1_0_5/"
    assert config["output_dir"] == "models/adapters/lv7_dpo_smoke_v1_3_3/"

    assert sha256(SELECTED_DATASET) == selected_hash_before
    assert sha256(run_eval_path) == run_eval_hash_before


def test_v1_3_2_repo_artifacts_exist_and_match_ready_shape():
    required = [
        ROOT / "training" / "build_v1_3_2_dpo_expansion.py",
        EXPANSION_DIR / "dpo_pairs_expansion.jsonl",
        EXPANSION_DIR / "dpo_pairs_selected_plus_expansion.jsonl",
        EXPANSION_DIR / "excluded_or_rejected_expansion_pairs.jsonl",
        EXPANSION_DIR / "DPO_EXPANSION_DATASET_REPORT.md",
        EXPANSION_DIR / "prompt_similarity_report.json",
        EXPANSION_DIR / "MANIFEST.md",
        REPORTS_DIR / "V1_3_2_DPO_EXPANSION_PLAN.md",
        REPORTS_DIR / "V1_3_2_DPO_EXPANSION_AUDIT.md",
        REPORTS_DIR / "DPO_READINESS_REVIEW_V1_3_2.md",
        ROOT / "training" / "dpo_smoke_config_v1_3_2.yaml",
    ]
    for path in required:
        assert path.exists(), f"Missing v1.3.2 artifact: {path}"

    accepted = read_jsonl(EXPANSION_DIR / "dpo_pairs_expansion.jsonl")
    combined = read_jsonl(EXPANSION_DIR / "dpo_pairs_selected_plus_expansion.jsonl")
    similarity_report = json.loads(
        (EXPANSION_DIR / "prompt_similarity_report.json").read_text(encoding="utf-8")
    )

    assert len(accepted) == 12
    assert len(combined) == 40
    assert similarity_report["exact_copies"] == 0
    assert similarity_report["hard_fail_near_duplicate_count"] == 0
    assert last_nonempty_line(REPORTS_DIR / "DPO_READINESS_REVIEW_V1_3_2.md") in APPROVED_STATUSES

    counts = Counter(audit_pair(record).primary_category for record in accepted)
    assert counts == {
        "overrefusal_vs_bounded_execute": 2,
        "unnecessary_escalation_vs_low_risk_execute": 2,
        "audit_evasion_vs_audit_preservation": 4,
        "unsafe_compliance_vs_safe_challenge": 4,
    }

    config = yaml.safe_load(
        (ROOT / "training" / "dpo_smoke_config_v1_3_2.yaml").read_text(encoding="utf-8")
    )
    assert config["starting_adapter"] == "models/adapters/lv7_sft_smoke_v1_0_5/"
    assert config["output_dir"] == "models/adapters/lv7_dpo_smoke_v1_3_3/"


def test_v1_3_2_reports_capture_expansion_constraints():
    dataset_report = (EXPANSION_DIR / "DPO_EXPANSION_DATASET_REPORT.md").read_text(encoding="utf-8")
    audit_report = (REPORTS_DIR / "V1_3_2_DPO_EXPANSION_AUDIT.md").read_text(encoding="utf-8")
    plan_report = (REPORTS_DIR / "V1_3_2_DPO_EXPANSION_PLAN.md").read_text(encoding="utf-8")
    decision_report = (REPORTS_DIR / "DPO_READINESS_REVIEW_V1_3_2.md").read_text(encoding="utf-8")

    assert "accepted pair count: `12`" in dataset_report
    assert "selected dataset unchanged: `True`" in dataset_report
    assert "`overrefusal_vs_bounded_execute`" in audit_report
    assert "`audit_evasion_vs_audit_preservation`" in audit_report
    assert "data-only and does not authorize a DPO run" in plan_report
    assert decision_report.rstrip().endswith(STATUS_READY)
