from __future__ import annotations

import json

from training.freeze_v0_8_artifacts import freeze_v0_8_artifacts


def test_freeze_manifest_writes_required_fields(tmp_path):
    dataset_dir = tmp_path / "data" / "pilot_v1_5"
    dataset_dir.mkdir(parents=True)
    sft_messages = dataset_dir / "sft_messages.jsonl"
    sft_train_ready = dataset_dir / "sft_train_ready.jsonl"
    sft_messages.write_text('{"id":"a"}\n', encoding="utf-8")
    sft_train_ready.write_text('{"id":"a","text":"x"}\n', encoding="utf-8")

    reports_dir = tmp_path / "reports" / "training"
    reports_dir.mkdir(parents=True)
    results_path = reports_dir / "v0_8_sft_eval_results.jsonl"
    results_path.write_text('{"pass": true}\n{"pass": true}\n', encoding="utf-8")

    training_dir = tmp_path / "training"
    training_dir.mkdir(parents=True)
    config_path = training_dir / "qlora_smoke_config.yaml"
    config_path.write_text("seed: 42\n", encoding="utf-8")

    adapter_dir = tmp_path / "models" / "adapters" / "lv7_sft_smoke_v0_8"
    adapter_dir.mkdir(parents=True)
    (adapter_dir / "adapter_config.json").write_text('{"r":16}\n', encoding="utf-8")

    from training import freeze_v0_8_artifacts as module

    original_root = module.PROJECT_ROOT
    original_required = module.REQUIRED_TRACKED_FILES
    try:
        module.PROJECT_ROOT = tmp_path
        module.REQUIRED_TRACKED_FILES = [
            sft_messages.relative_to(tmp_path),
            sft_train_ready.relative_to(tmp_path),
            results_path.relative_to(tmp_path),
            config_path.relative_to(tmp_path),
        ]
        markdown_path = reports_dir / "V0_8_FREEZE.md"
        manifest_path = reports_dir / "v0_8_artifact_manifest.json"
        summary = freeze_v0_8_artifacts(
            results_path=results_path,
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
    assert summary["strict_score"] == {"passed": 2, "total": 2}
    assert manifest["base_model"] == "Qwen/Qwen2.5-1.5B-Instruct"
    assert manifest["tracked_files"]["data/pilot_v1_5/sft_messages.jsonl"]["line_count"] == 1
    assert "adapter_config.json" in manifest["adapter_files"]
    assert len(manifest["tracked_files"]["training/qlora_smoke_config.yaml"]["sha256"]) == 64
    assert "## Tracked Files" in markdown_path.read_text(encoding="utf-8")
