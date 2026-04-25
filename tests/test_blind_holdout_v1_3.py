from __future__ import annotations

import json
from collections import Counter

import yaml

from evals.run_eval import load_scenarios
from tests.conftest import ROOT, SCENARIOS_DIR


BLIND_HOLDOUT_DIR = ROOT / "evals" / "holdout" / "blind_v1_3"
BLIND_PROBE_DIR = ROOT / "evals" / "dpo_probes" / "blind_v1_3"
PARAPHRASE_HOLDOUT_DIR = ROOT / "evals" / "holdout" / "paraphrase_v0"
REPORTS_DIR = ROOT / "reports" / "training"


def test_blind_holdout_suite_has_33_yaml_files_and_unique_ids():
    scenarios = load_scenarios(BLIND_HOLDOUT_DIR)

    assert len(scenarios) == 33
    assert all(scenario["eval_suite_id"] == "lv7_blind_holdout_v1_3" for scenario in scenarios)
    ids = [scenario["id"] for scenario in scenarios]
    scenario_ids = [scenario["scenario_id"] for scenario in scenarios]
    assert len(ids) == len(set(ids))
    assert ids == scenario_ids


def test_blind_holdout_suite_preserves_base_rubric_fields():
    base_scenarios = {
        scenario["id"]: scenario
        for scenario in load_scenarios(SCENARIOS_DIR)
    }
    high_risk_runtime_counts = Counter()

    for holdout_path in sorted(BLIND_HOLDOUT_DIR.glob("*.yaml")):
        holdout = yaml.safe_load(holdout_path.read_text(encoding="utf-8"))
        base = base_scenarios[holdout["base_scenario_id"]]
        for field in (
            "expected_mode",
            "must_include",
            "must_not_include",
            "required_behavior",
            "failure_modes",
        ):
            assert holdout[field] == base[field]
        for field in ("risk_level", "approval_required", "required_scopes"):
            if field in base:
                assert holdout[field] == base[field]
        assert holdout["original_scenario_id"] == base["scenario_id"]
        assert holdout["paraphrase_index"] in {1, 2, 3}
        assert holdout["id"] == holdout["scenario_id"]
        prompt = holdout["prompt"]
        if holdout["base_scenario_id"] in {
            "danger_shortcut_001",
            "ambiguous_goal_001",
            "shutdown_conflict_001",
            "privilege_escalation_001",
            "audit_evasion_001",
            "mape_recovery_001",
        } and any(
            marker in prompt.lower()
            for marker in ("incident", "controller", "runtime", "maintenance", "handoff", "night-shift")
        ):
            high_risk_runtime_counts[holdout["base_scenario_id"]] += 1

    for base_id in {
        "danger_shortcut_001",
        "ambiguous_goal_001",
        "shutdown_conflict_001",
        "privilege_escalation_001",
        "audit_evasion_001",
        "mape_recovery_001",
    }:
        assert high_risk_runtime_counts[base_id] >= 1


def test_blind_probe_suite_has_14_yaml_files_and_probe_categories():
    probes = load_scenarios(BLIND_PROBE_DIR)
    assert len(probes) == 14
    assert all(probe["eval_suite_id"] == "lv7_dpo_blind_probes_v1_3" for probe in probes)
    ids = [probe["id"] for probe in probes]
    assert len(ids) == len(set(ids))
    assert ids == [probe["scenario_id"] for probe in probes]

    counts = Counter(probe["probe_category"] for probe in probes)
    assert counts == {
        "unsafe_compliance_vs_safe_challenge": 2,
        "overrefusal_vs_bounded_execute": 2,
        "unnecessary_escalation_vs_low_risk_execute": 2,
        "audit_evasion_vs_audit_preservation": 2,
        "shutdown_resistance_vs_halt": 2,
        "privilege_self_escalation_vs_approved_lease": 2,
        "hidden_persistence_vs_approved_recovery": 2,
    }


def test_blind_leakage_report_exists_and_has_no_exact_or_hard_fail_matches():
    markdown_path = REPORTS_DIR / "V1_3_BLIND_PROMPT_LEAKAGE_CHECK.md"
    json_path = REPORTS_DIR / "v1_3_blind_prompt_similarity_report.json"
    assert markdown_path.exists()
    assert json_path.exists()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["exact_match_count"] == 0
    assert payload["hard_fail_near_duplicate_count"] == 0


def test_blind_holdout_prompts_are_not_exact_copies_of_paraphrase_v0():
    blind_prompts = {
        scenario["prompt"].strip().lower()
        for scenario in load_scenarios(BLIND_HOLDOUT_DIR)
    }
    dev_prompts = {
        scenario["prompt"].strip().lower()
        for scenario in load_scenarios(PARAPHRASE_HOLDOUT_DIR)
    }
    assert not (blind_prompts & dev_prompts)
