from __future__ import annotations

import yaml

from evals.run_eval import load_scenarios
from tests.conftest import HOLDOUT_PARAPHRASE_DIR, SCENARIOS_DIR


def test_holdout_suite_has_33_yaml_files_and_unique_ids():
    scenarios = load_scenarios(HOLDOUT_PARAPHRASE_DIR)

    assert len(scenarios) == 33
    assert all(scenario["eval_suite_id"] == "lv7_holdout_paraphrase_v0" for scenario in scenarios)
    ids = [scenario["id"] for scenario in scenarios]
    scenario_ids = [scenario["scenario_id"] for scenario in scenarios]
    assert len(ids) == len(set(ids))
    assert len(scenario_ids) == len(set(scenario_ids))


def test_holdout_suite_preserves_base_rubric_fields():
    base_scenarios = {
        scenario["id"]: scenario
        for scenario in load_scenarios(SCENARIOS_DIR)
    }

    for holdout_path in sorted(HOLDOUT_PARAPHRASE_DIR.glob("*.yaml")):
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
        if "risk_level" in base:
            assert holdout["risk_level"] == base["risk_level"]
        if "approval_required" in base:
            assert holdout["approval_required"] == base["approval_required"]
        if "required_scopes" in base:
            assert holdout["required_scopes"] == base["required_scopes"]
        assert holdout["original_scenario_id"] == base["scenario_id"]
