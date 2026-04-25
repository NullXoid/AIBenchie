from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from tests.conftest import ROOT
from training.plan_dpo_smoke_v1_1 import PRIMARY_CATEGORIES, STATUS_READY


REPORTS_DIR = ROOT / "reports" / "training"
PLANNING_DATA_DIR = ROOT / "data" / "dpo_smoke_v1_1"


def read_jsonl(path: Path):
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_v1_1_planning_artifacts_exist():
    required_paths = [
        REPORTS_DIR / "V1_0_5_FREEZE.md",
        REPORTS_DIR / "v1_0_5_artifact_manifest.json",
        REPORTS_DIR / "V1_1_DPO_TARGET_TAXONOMY.md",
        REPORTS_DIR / "V1_1_DPO_DATA_AUDIT.md",
        REPORTS_DIR / "DPO_SMOKE_DATASET_REPORT.md",
        REPORTS_DIR / "V1_1_DPO_REGRESSION_GUARDS.md",
        REPORTS_DIR / "V1_1_BLIND_HOLDOUT_REQUIREMENT.md",
        REPORTS_DIR / "V1_1_DPO_SMOKE_PLAN.md",
        REPORTS_DIR / "V1_1_NEXT_STEP_DECISION.md",
        PLANNING_DATA_DIR / "dpo_pairs_selected.jsonl",
        PLANNING_DATA_DIR / "excluded_pairs.jsonl",
        ROOT / "training" / "dpo_smoke_config.yaml",
        ROOT / "docs" / "RUN_DPO_SMOKE.md",
    ]

    for path in required_paths:
        assert path.exists(), f"Missing v1.1 planning artifact: {path}"


def test_v1_1_taxonomy_names_are_fixed():
    taxonomy = (REPORTS_DIR / "V1_1_DPO_TARGET_TAXONOMY.md").read_text(encoding="utf-8")
    for category in PRIMARY_CATEGORIES:
        assert f"`{category}`" in taxonomy
    assert "`bad_approval_behavior_vs_correct_lease_request`" in taxonomy


def test_v1_1_audit_covers_all_55_pairs_and_excludes_ambiguous_goal():
    audit_text = (REPORTS_DIR / "V1_1_DPO_DATA_AUDIT.md").read_text(encoding="utf-8")
    assert audit_text.count("| `dpo_") == 55

    excluded = read_jsonl(PLANNING_DATA_DIR / "excluded_pairs.jsonl")
    ambiguous = [
        record
        for record in excluded
        if record["audit"]["scenario_name"] == "Ambiguous Goal"
    ]
    assert len(ambiguous) == 5
    assert all(record["audit"]["safe_for_dpo_smoke"] is False for record in ambiguous)
    assert all(
        record["audit"]["exclusion_reason"]
        == "Clarification behavior is SFT/mode-discipline territory, not a v1.1 DPO smoke target."
        for record in ambiguous
    )


def test_v1_1_selected_dataset_is_balanced_and_schema_preserving():
    decision_lines = [
        line.strip()
        for line in (REPORTS_DIR / "V1_1_NEXT_STEP_DECISION.md").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert decision_lines[-1] == STATUS_READY

    selected = read_jsonl(PLANNING_DATA_DIR / "dpo_pairs_selected.jsonl")
    assert len(selected) == 28

    counts = Counter()
    for record in selected:
        assert sorted(record.keys()) == ["chosen", "id", "metadata", "prompt", "rejected", "scenario_id"]
        assert record["chosen"].startswith("policy_rationale:\n")
        scenario_name = record["metadata"]["scenario_name"]
        if scenario_name == "Danger Shortcut":
            counts["unsafe_compliance_vs_safe_challenge"] += 1
        elif scenario_name == "Audit Evasion":
            counts["audit_evasion_vs_audit_preservation"] += 1
        elif scenario_name == "Shutdown Conflict":
            counts["shutdown_resistance_vs_halt"] += 1
        elif scenario_name == "Privilege Escalation":
            counts["privilege_self_escalation_vs_approved_lease"] += 1
        elif scenario_name == "MAPE-K Recovery":
            counts["hidden_persistence_vs_approved_recovery"] += 1
        elif scenario_name in {
            "Low-Risk Readonly",
            "Safe Test Run",
            "Simple File Lookup",
            "Memory Read Summary",
            "Model Invoke Safe",
        }:
            rejected = record["rejected"].lower()
            if any(marker in rejected for marker in ("i refuse", "refuse to", "without a special lease", "without more authority")):
                counts["overrefusal_vs_bounded_execute"] += 1
            else:
                counts["unnecessary_escalation_vs_low_risk_execute"] += 1

        assert record["metadata"]["scenario_name"] != "Ambiguous Goal"

    assert counts == Counter({category: 4 for category in PRIMARY_CATEGORIES})


def test_v1_1_selected_dataset_excludes_lexical_token_repair_pairs():
    selected = read_jsonl(PLANNING_DATA_DIR / "dpo_pairs_selected.jsonl")
    for record in selected:
        rejected = record["rejected"].lower()
        assert rejected not in {
            "service:restart",
            "test:run",
            "logged",
        }


def test_v1_1_reports_and_config_preserve_required_guardrails():
    config_text = (ROOT / "training" / "dpo_smoke_config.yaml").read_text(encoding="utf-8")
    guards = (REPORTS_DIR / "V1_1_DPO_REGRESSION_GUARDS.md").read_text(encoding="utf-8")
    plan = (REPORTS_DIR / "V1_1_DPO_SMOKE_PLAN.md").read_text(encoding="utf-8")
    blind = (REPORTS_DIR / "V1_1_BLIND_HOLDOUT_REQUIREMENT.md").read_text(encoding="utf-8")

    assert "base_model: Qwen/Qwen2.5-1.5B-Instruct" in config_text
    assert "starting_adapter: models/adapters/lv7_sft_smoke_v1_0_5/" in config_text
    assert "dataset: data/dpo_smoke_v1_1/dpo_pairs_selected.jsonl" in config_text
    assert "`policy_rationale_present` remains `33/33`" in guards
    assert "Ambiguous Goal remains `clarify`" in guards
    assert "DPO must not be used for lexical-token repair" in plan
    assert "development set" in blind


def test_v1_1_freeze_manifest_contains_required_artifacts():
    manifest = json.loads((REPORTS_DIR / "v1_0_5_artifact_manifest.json").read_text(encoding="utf-8"))
    assert manifest["adapter_path"] == "models/adapters/lv7_sft_smoke_v1_0_5/"
    assert manifest["dataset_dir"] == "data/pilot_v1_9/"
    assert manifest["exact_score"] == {"passed": 11, "total": 11}
    assert manifest["development_holdout_score"] == {"passed": 30, "total": 33}
    assert manifest["policy_rationale_present"] == "33/33"
    assert manifest["mode_match"] == "32/33"
    assert manifest["catastrophic_safety_failures"] == 0
    assert "reports/training/v1_0_5_exact_eval_results.jsonl" in manifest["tracked_files"]
    assert "reports/training/v1_0_5_holdout_eval_results.jsonl" in manifest["tracked_files"]
    assert "adapter_config.json" in manifest["adapter_files"]


def test_v1_1_final_status_is_single_terminal_value():
    lines = [
        line.strip()
        for line in (REPORTS_DIR / "V1_1_NEXT_STEP_DECISION.md").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert lines[-1] in {
        "DPO_SMOKE_PLAN_READY",
        "NEEDS_DPO_DATA_REWRITE",
        "NEEDS_BLIND_HOLDOUT_FIRST",
        "NEEDS_RUNTIME_EVAL_FIRST",
    }
