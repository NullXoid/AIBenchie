from __future__ import annotations

import json

from training.freeze_v1_0_5_artifacts import freeze_v1_0_5_artifacts


def test_freeze_v1_0_5_manifest_writes_required_fields(tmp_path):
    dataset_dir = tmp_path / "data" / "pilot_v1_9"
    dataset_dir.mkdir(parents=True)
    sft_messages = dataset_dir / "sft_messages.jsonl"
    sft_train_ready = dataset_dir / "sft_train_ready.jsonl"
    dpo_pairs = dataset_dir / "dpo_pairs.jsonl"
    sft_messages.write_text('{"id":"a"}\n', encoding="utf-8")
    sft_train_ready.write_text('{"id":"a","text":"x"}\n', encoding="utf-8")
    dpo_pairs.write_text('{"id":"p","chosen":"x"}\n', encoding="utf-8")

    reports_dir = tmp_path / "reports" / "training"
    reports_dir.mkdir(parents=True)
    exact_results = reports_dir / "v1_0_5_exact_eval_results.jsonl"
    holdout_results = reports_dir / "v1_0_5_holdout_eval_results.jsonl"
    exact_results.write_text('{"pass": true, "score": {"policy_rationale_present": true, "mode_match": true}}\n', encoding="utf-8")
    holdout_results.write_text(
        '{"pass": true, "score": {"policy_rationale_present": true, "mode_match": true}}\n'
        '{"pass": false, "score": {"policy_rationale_present": true, "mode_match": false}}\n',
        encoding="utf-8",
    )

    training_dir = tmp_path / "training"
    training_dir.mkdir(parents=True)
    config_path = training_dir / "qlora_smoke_config.yaml"
    config_path.write_text("seed: 42\n", encoding="utf-8")

    adapter_dir = tmp_path / "models" / "adapters" / "lv7_sft_smoke_v1_0_5"
    adapter_dir.mkdir(parents=True)
    (adapter_dir / "adapter_config.json").write_text('{"r":16}\n', encoding="utf-8")

    from training import freeze_v1_0_5_artifacts as module

    original_root = module.PROJECT_ROOT
    original_required = module.REQUIRED_TRACKED_FILES
    try:
        module.PROJECT_ROOT = tmp_path
        module.REQUIRED_TRACKED_FILES = [
            sft_messages.relative_to(tmp_path),
            sft_train_ready.relative_to(tmp_path),
            dpo_pairs.relative_to(tmp_path),
            exact_results.relative_to(tmp_path),
            holdout_results.relative_to(tmp_path),
            config_path.relative_to(tmp_path),
        ]
        markdown_path = reports_dir / "V1_0_5_FREEZE.md"
        manifest_path = reports_dir / "v1_0_5_artifact_manifest.json"
        summary = freeze_v1_0_5_artifacts(
            exact_results_path=exact_results,
            holdout_results_path=holdout_results,
            config_path=config_path,
            dataset_dir=dataset_dir,
            adapter_dir=adapter_dir,
            markdown_path=markdown_path,
            manifest_path=manifest_path,
        )
    finally:
        module.PROJECT_ROOT = original_root
        module.REQUIRED_TRACKED_FILES = original_required

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert summary["exact_score"] == {"passed": 1, "total": 1}
    assert summary["development_holdout_score"] == {"passed": 1, "total": 2}
    assert manifest["base_model"] == "Qwen/Qwen2.5-1.5B-Instruct"
    assert manifest["policy_rationale_present"] == "2/2"
    assert manifest["mode_match"] == "1/2"
    assert manifest["tracked_files"]["data/pilot_v1_9/dpo_pairs.jsonl"]["line_count"] == 1
    assert "adapter_config.json" in manifest["adapter_files"]
    assert len(manifest["tracked_files"]["training/qlora_smoke_config.yaml"]["sha256"]) == 64
    assert "## Tracked Files" in markdown_path.read_text(encoding="utf-8")
