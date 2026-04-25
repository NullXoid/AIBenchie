from __future__ import annotations

import json
from pathlib import Path

from tests.conftest import ROOT
from training.freeze_v1_2_4_artifacts import freeze_v1_2_4_artifacts


REPORTS_DIR = ROOT / "reports" / "training"


def test_freeze_v1_2_4_manifest_writes_required_fields(tmp_path):
    reports_dir = tmp_path / "reports" / "training"
    reports_dir.mkdir(parents=True)
    exact_results = reports_dir / "v1_2_4_dpo_exact_eval_results.jsonl"
    holdout_results = reports_dir / "v1_2_4_dpo_holdout_eval_results.jsonl"
    probe_results = reports_dir / "v1_2_4_dpo_probe_results.jsonl"
    exact_results.write_text(
        '{"pass": true, "score": {"policy_rationale_present": true, "mode_match": true}}\n',
        encoding="utf-8",
    )
    holdout_results.write_text(
        '{"pass": true, "score": {"policy_rationale_present": true, "mode_match": true}}\n'
        '{"pass": false, "score": {"policy_rationale_present": true, "mode_match": false}}\n',
        encoding="utf-8",
    )
    probe_results.write_text(
        '{"pass": true}\n{"pass": true}\n{"pass": false}\n',
        encoding="utf-8",
    )
    (reports_dir / "v1_2_4_ambiguous_goal_precheck.json").write_text(
        json.dumps({"cases": []}) + "\n",
        encoding="utf-8",
    )
    ambiguous_postcheck = reports_dir / "v1_2_4_ambiguous_goal_postcheck.json"
    ambiguous_postcheck.write_text(
        json.dumps(
            {
                "cases": [
                    {"observed_mode": "clarify"},
                    {"observed_mode": "clarify"},
                    {"observed_mode": "clarify"},
                    {"observed_mode": "clarify"},
                ],
                "all_clarify": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (reports_dir / "V1_2_4_DPO_SMOKE_ANALYSIS.md").write_text("# analysis\n", encoding="utf-8")
    (reports_dir / "DPO_READINESS_REVIEW_V1_2_4.md").write_text("# review\n", encoding="utf-8")
    (reports_dir / "v1_2_4_dpo_run_config.json").write_text("{}\n", encoding="utf-8")
    (reports_dir / "v1_2_4_dpo_train_log.jsonl").write_text('{"loss": 1.0}\n', encoding="utf-8")

    training_dir = tmp_path / "training"
    training_dir.mkdir(parents=True)
    config_path = training_dir / "dpo_smoke_config_v1_2_4.yaml"
    config_path.write_text("seed: 42\n", encoding="utf-8")

    data_dir = tmp_path / "data" / "dpo_smoke_v1_1"
    data_dir.mkdir(parents=True)
    selected_dpo = data_dir / "dpo_pairs_selected.jsonl"
    selected_dpo.write_text('{"id":"pair_001","prompt":"x"}\n', encoding="utf-8")

    adapter_dir = tmp_path / "models" / "adapters" / "lv7_dpo_smoke_v1_2_4"
    adapter_dir.mkdir(parents=True)
    (adapter_dir / "adapter_config.json").write_text('{"r":16}\n', encoding="utf-8")

    from training import freeze_v1_2_4_artifacts as module

    original_root = module.PROJECT_ROOT
    original_required = module.REQUIRED_TRACKED_FILES
    try:
        module.PROJECT_ROOT = tmp_path
        module.REQUIRED_TRACKED_FILES = [
            exact_results.relative_to(tmp_path),
            holdout_results.relative_to(tmp_path),
            probe_results.relative_to(tmp_path),
            (reports_dir / "v1_2_4_ambiguous_goal_precheck.json").relative_to(tmp_path),
            ambiguous_postcheck.relative_to(tmp_path),
            (reports_dir / "V1_2_4_DPO_SMOKE_ANALYSIS.md").relative_to(tmp_path),
            (reports_dir / "DPO_READINESS_REVIEW_V1_2_4.md").relative_to(tmp_path),
            (reports_dir / "v1_2_4_dpo_run_config.json").relative_to(tmp_path),
            (reports_dir / "v1_2_4_dpo_train_log.jsonl").relative_to(tmp_path),
            config_path.relative_to(tmp_path),
            selected_dpo.relative_to(tmp_path),
        ]
        markdown_path = reports_dir / "V1_2_4_FREEZE.md"
        manifest_path = reports_dir / "v1_2_4_artifact_manifest.json"
        summary = freeze_v1_2_4_artifacts(
            exact_results_path=exact_results,
            holdout_results_path=holdout_results,
            probe_results_path=probe_results,
            ambiguous_postcheck_path=ambiguous_postcheck,
            config_path=config_path,
            selected_dpo_path=selected_dpo,
            accepted_adapter_dir=adapter_dir,
            markdown_path=markdown_path,
            manifest_path=manifest_path,
        )
    finally:
        module.PROJECT_ROOT = original_root
        module.REQUIRED_TRACKED_FILES = original_required

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert summary["exact_suite"] == {"passed": 1, "total": 1}
    assert summary["development_holdout"] == {"passed": 1, "total": 2}
    assert summary["dpo_probes"] == {"passed": 2, "total": 3}
    assert manifest["accepted_dpo_adapter"] == "models/adapters/lv7_dpo_smoke_v1_2_4/"
    assert manifest["blocked_dpo_adapter"] == "models/adapters/lv7_dpo_smoke_v1_2/"
    assert manifest["ambiguous_goal_checks"]["clarify_count"] == 4
    assert manifest["policy_rationale_present"] == "2/2"
    assert manifest["mode_match"] == "1/2"
    assert "adapter_config.json" in manifest["adapter_files"]
    assert "## Tracked Files" in markdown_path.read_text(encoding="utf-8")


def test_v1_2_4_freeze_repo_artifacts_exist_and_have_checksums():
    markdown_path = REPORTS_DIR / "V1_2_4_FREEZE.md"
    manifest_path = REPORTS_DIR / "v1_2_4_artifact_manifest.json"
    assert markdown_path.exists()
    assert manifest_path.exists()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["exact_suite"] == {"passed": 11, "total": 11}
    assert manifest["development_holdout"] == {"passed": 31, "total": 33}
    assert manifest["dpo_probes"] == {"passed": 13, "total": 14}
    assert manifest["ambiguous_goal_checks"]["clarify_count"] == 4
    assert manifest["pytest_result"] == "141 passed"
    assert manifest["tracked_files"]
    assert manifest["adapter_files"]
    for entry in manifest["tracked_files"].values():
        assert len(entry["sha256"]) == 64
