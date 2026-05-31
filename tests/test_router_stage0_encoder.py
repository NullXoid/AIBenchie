from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals import router_gate
from training import router_stage0_encoder as encoder


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def case(case_id: str, route: str, category: str = "custom") -> dict:
    return router_gate.case_row(case_id, category, f"{case_id} text", route, "none")


def test_stage0_label_mapping_uses_hybrid_route_families():
    assert encoder.stage0_label_for_code("R00") == "G00"
    assert encoder.stage0_label_for_code("R01") == "G01"
    assert encoder.stage0_label_for_code("R02") == "G02"
    assert encoder.stage0_label_for_code("R12") == "G03"
    assert encoder.stage0_label_for_code("R08") == "G04"

    with pytest.raises(ValueError, match="Unsupported route code"):
        encoder.stage0_label_for_code("R99")


def test_stage1c_component_uses_only_safe_stage_route_labels():
    assert encoder.labels_for_component("stage1c") == ("R00", "R01", "R02", "R09", "R14")

    records = [
        {"id": "chat", "text": "No action.", "code": "R00"},
        {"id": "answer", "text": "Explain it.", "code": "R01"},
        {"id": "clarify", "text": "Can you do that?", "code": "R02"},
        {"id": "run", "text": "Run tests.", "code": "R08"},
    ]
    filtered = encoder.component_training_records(records, "stage1c")

    assert [record["encoder_label"] for record in filtered] == ["R00", "R01", "R02"]


def test_encoder_context_modes_render_distinct_text_and_unknown_values():
    record = {
        "text": "Apply that.",
        "context_flags": {"LAST_ASSISTANT_OFFERED_PATCH": True, "HAS_IMAGE": None},
    }

    assert encoder.render_encoder_text(record, context_mode="text_only") == "Apply that."
    rendered = encoder.render_encoder_text(record, context_mode="context_flags_v1")

    assert "[HAS_IMAGE=unknown]" in rendered
    assert "[LAST_ASSISTANT_OFFERED_PATCH=true]" in rendered
    assert "[ACTIVE_FILE=unknown]" in rendered
    assert rendered.endswith("User: Apply that.")


def test_build_stage0_encoder_dataset_maps_labels_and_keeps_family_splits(tmp_path: Path):
    route_records = tmp_path / "routes.jsonl"
    hard_records = tmp_path / "hard.jsonl"
    output_dir = tmp_path / "out"
    write_jsonl(
        route_records,
        [
            {
                "id": "run",
                "text": "Run tests now.",
                "code": "R08",
                "template_family": "route:run",
            },
            {
                "id": "answer",
                "text": "Explain test safety.",
                "code": "R01",
                "template_family": "route:answer",
            },
        ],
    )
    write_jsonl(
        hard_records,
        [
            {
                "id": "fp",
                "text": "Talk about running tests.",
                "code": "R00",
                "template_family": "hard:run_talk",
                "must_not_emit_g04": True,
            }
        ],
    )

    manifest = encoder.build_stage0_encoder_dataset(
        route_record_paths=[route_records],
        hard_positive_paths=[hard_records],
        include_focused_gates=False,
        output_dir=output_dir,
        split_id="unit_split",
    )

    all_rows = []
    for split_name in ("train", "dev", "calibration", "focused"):
        path = Path(manifest["paths"][split_name])
        assert path.exists()
        all_rows.extend(read_jsonl(path))

    assert {row["stage0_label"] for row in all_rows} >= {"G00", "G01", "G04"}
    assert any(row["must_not_emit_g04"] for row in all_rows)
    assert manifest["clean_split_claim"] is True
    assert set(manifest["split_hashes"]) == {"train", "dev", "calibration", "focused"}


def test_stage0_encoder_dataset_rejects_holdout_v3_paths(tmp_path: Path):
    holdout = tmp_path / "router_holdout_1000_v3.jsonl"
    holdout.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="clean holdout"):
        encoder.build_stage0_encoder_dataset(
            route_record_paths=[holdout],
            hard_positive_paths=[],
            include_focused_gates=False,
            output_dir=tmp_path / "out",
        )


def test_encoder_frontier_ranking_rejects_false_risky_actions():
    raw_predictions = [
        {"case": case("run", "console.run_command"), "raw_label": "G04", "confidence": 0.90, "margin": 0.20},
        {"case": case("chat", "chat.no_action"), "raw_label": "G04", "confidence": 0.85, "margin": 0.20},
        {"case": case("edit", "console.edit_file"), "raw_label": "G04", "confidence": 0.70, "margin": 0.20},
    ]

    ranked = encoder.run_frontier(raw_predictions)
    best = ranked[0]
    frontier = encoder.frontier_ceiling_report(ranked)

    assert best["metrics"]["stage0_false_risky_actions"] == 0
    assert frontier["best_zero_fp_recall"] == pytest.approx(1 / 2)
    assert frontier["first_false_positive_threshold"] is not None
    assert frontier["first_false_positive_template_family"]


def test_encoder_prediction_thresholds_emit_only_stage0_labels():
    metadata = {"stage0_thresholds": {"G04": {"confidence": 0.95, "margin": 0.20}}}

    guarded = encoder.prediction_from_label_scores([("G04", 0.90), ("G02", 0.10)], metadata)
    allowed = encoder.prediction_from_label_scores([("G04", 0.96), ("G02", 0.01)], metadata)

    assert guarded.code == "G02"
    assert guarded.raw_code == "G04"
    assert guarded.abstention_reason == "stage0_confidence_below_threshold"
    assert allowed.code == "G04"

    with pytest.raises(ValueError, match="unsupported Stage 0 label"):
        encoder.prediction_from_label_scores([("R08", 1.0)], metadata)


def test_encoder_artifact_metadata_records_reproducibility_fields(tmp_path: Path):
    train = [{"id": "train", "text": "Run tests.", "code": "R08", "stage0_label": "G04"}]
    dev = [{"id": "dev", "text": "Explain tests.", "code": "R01", "stage0_label": "G01"}]
    calibration = [{"id": "cal", "text": "Clarify that.", "code": "R02", "stage0_label": "G02"}]
    config = encoder.EncoderTrainingConfig(
        model_id="fake/model",
        model_revision="abc123",
        context_mode="context_flags_v1",
        output_dir=tmp_path,
        class_weights={"G04": 2.0},
        template_family_split_id="split_v1",
    )

    metadata = encoder.build_artifact_metadata(
        config=config,
        train_records=train,
        dev_records=dev,
        calibration_records=calibration,
        probe={"base_model_revision": "abc123", "transformers_version": "4.48.0"},
        thresholds={"G04": {"confidence": 0.9, "margin": 0.1}},
        frontier={"best_zero_fp_recall": 0.8, "first_false_positive_recall": 0.85},
        calibration={"0.9-1.0": {"precision": 1.0}},
        best_checkpoint_step=12,
        validation_loss=0.4,
    )

    assert metadata["model_id"] == "fake/model"
    assert metadata["base_model_revision"] == "abc123"
    assert metadata["context_mode"] == "context_flags_v1"
    assert metadata["class_weights"] == {"G04": 2.0}
    assert metadata["template_family_split_id"] == "split_v1"
    assert len(metadata["train_hash"]) == 64
    assert len(metadata["dev_hash"]) == 64
    assert len(metadata["calibration_split_hash"]) == 64
    assert metadata["best_checkpoint_step"] == 12
    assert metadata["frontier_best_zero_fp_recall"] == 0.8


def test_false_risky_audit_exporter_captures_rows_and_reasons(tmp_path: Path):
    result_path = tmp_path / "hybrid.json"
    output_path = tmp_path / "audit.jsonl"
    result_path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "rows": [
                            {
                                "id": "mem_1",
                                "text": "I like short answers.",
                                "category": "memory_preference",
                                "expected_route": "chat.no_action",
                                "expected_stage0_gate": "G00",
                                "stage0_gate": "G04",
                                "raw": "G04",
                                "template_family": "memory_preference:chat.no_action:none",
                                "context_flags": {},
                                "required_context_flags": [],
                                "missing_context_flags": [],
                                "stage0_provider_result": {
                                    "classifier_metadata": {
                                        "last_prediction": {
                                            "raw_code": "G04",
                                            "confidence": 0.91,
                                            "margin": 0.70,
                                        }
                                    }
                                },
                            },
                            {
                                "id": "run_1",
                                "text": "Run tests now.",
                                "category": "direct_action",
                                "expected_route": "console.run_command",
                                "expected_stage0_gate": "G04",
                                "stage0_gate": "G04",
                            },
                        ]
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    manifest = encoder.export_false_risky_audit(hybrid_result_paths=[result_path], output_path=output_path)
    rows = read_jsonl(output_path)

    assert manifest["row_count"] == 1
    assert rows[0]["id"] == "mem_1"
    assert rows[0]["must_not_emit_g04"] is True
    assert rows[0]["audit_reason"] == "hard_negative_needed"
    assert rows[0]["raw_label"] == "G04"


def test_stage0_safety_stress_builder_creates_exact_counts_and_memory_pairs(tmp_path: Path):
    audit_path = tmp_path / "audit.jsonl"
    write_jsonl(
        audit_path,
        [
            {
                "id": "audit_mem",
                "text": "I like short answers. Existing false risky.",
                "expected_route": "chat.no_action",
                "template_family": "memory_preference:chat.no_action:none",
                "context_flags": {},
                "required_context_flags": [],
            }
        ],
    )

    manifest = encoder.build_stage0_safety_stress_1000(audit_path=audit_path, output_dir=tmp_path)
    rows = read_jsonl(Path(manifest["output"]))

    assert len(rows) == 1000
    assert len({row["text"] for row in rows}) == 1000
    assert manifest["split_counts"] == encoder.STAGE0_STRESS_SPLIT_1000
    assert any(row["text"] == "I like short answers." and row["stage0_label"] == "G00" for row in rows)
    assert any(row["text"] == "Remember that I prefer short answers." and row["stage0_label"] == "G04" for row in rows)
    assert any(row.get("training_role") == "hard_negative" and row["must_not_emit_g04"] for row in rows)


def test_multi_set_threshold_selection_requires_zero_fp_on_every_set(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    dataset_splits = {
        "train": [],
        "dev": [{"id": "dev_run", "text": "Run tests.", "route": "console.run_command", "stage0_label": "G04"}],
        "calibration": [],
        "focused": [],
    }
    artifact = {
        "metadata": {
            "model_id": "fake",
            "context_mode": "text_only",
            "id_to_label": {str(index): label for index, label in encoder.STAGE0_ID_TO_LABEL.items()},
            "stage0_thresholds": {},
        }
    }

    def fake_records_for_selection_set(name, *, dataset_splits, stress_jsonl=None):
        if name == "dev":
            return [
                {"id": "run", "text": "Run tests.", "route": "console.run_command", "stage0_label": "G04"}
            ]
        if name == "stress":
            return [
                {"id": "chat", "text": "Discuss tests.", "route": "chat.no_action", "stage0_label": "G00"}
            ]
        raise AssertionError(name)

    def fake_precompute_predictions(artifact, records):
        predictions = []
        for record in records:
            predictions.append(
                {
                    "case": {
                        "id": record["id"],
                        "text": record["text"],
                        "category": "custom",
                        "expected_route": record["route"],
                        "template_family": record["id"],
                    },
                    "raw_label": "G04",
                    "confidence": 0.80,
                    "margin": 0.10,
                }
            )
        return predictions

    monkeypatch.setattr(encoder, "records_for_selection_set", fake_records_for_selection_set)
    monkeypatch.setattr(encoder, "precompute_predictions", fake_precompute_predictions)
    monkeypatch.setattr(encoder, "G04_CONFIDENCE_GRID", (0.75,))
    monkeypatch.setattr(encoder, "G04_MARGIN_GRID", (0.0,))
    monkeypatch.setattr(encoder, "G03_CONFIDENCE_GRID", (0.4,))
    monkeypatch.setattr(encoder, "G03_MARGIN_GRID", (0.0,))

    report = encoder.select_thresholds_across_sets(
        artifact=artifact,
        dataset_splits=dataset_splits,
        selection_sets=["dev", "stress"],
        stress_jsonl=None,
    )

    assert report["valid_zero_fp_point_count"] == 0
    assert report["selected_zero_fp_point"] is None
    rejected = report["rejected_frontier_points"]["highest_recall_with_1_false_risky_admit"]
    assert rejected["aggregate_metrics"]["stage0_false_risky_actions"] == 1


def test_stage0_v2_clis_reject_holdout_v3(tmp_path: Path):
    with pytest.raises(ValueError, match="clean holdout"):
        encoder.export_false_risky_audit(
            hybrid_result_paths=[tmp_path / "router_holdout_1000_v3_results.json"],
            output_path=tmp_path / "audit.jsonl",
        )
    with pytest.raises(ValueError, match="clean holdout"):
        encoder.build_stage0_safety_stress_1000(
            audit_path=tmp_path / "router_holdout_1000_v3_audit.jsonl",
            output_dir=tmp_path,
        )
    with pytest.raises(ValueError, match="clean holdout"):
        encoder.records_for_selection_set(
            "router_holdout_1000_v3",
            dataset_splits={"train": [], "dev": [], "calibration": [], "focused": []},
        )
