from __future__ import annotations

import json
from pathlib import Path

from training.analyze_v1_5_3_candidate_runtime_recheck_bridge import (
    APPROVED_STATUSES,
    CANDIDATE_ALIAS_MODEL_ID,
    CANDIDATE_CHECKPOINT,
    EXPECTED_BASE_MODEL,
    NEXT_EXECUTABLE_MILESTONE,
    STATUS_INCOMPLETE,
    STATUS_INVALID,
    STATUS_READY,
    analyze_v1_5_3_candidate_runtime_recheck_bridge,
)


def last_nonempty_line(path: Path) -> str:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ][-1]


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )


def write_exact_eval_pair(current_path: Path, baseline_path: Path) -> None:
    rows = []
    for index in range(11):
        rows.append(
            {
                "id": f"scenario_{index:02d}",
                "pass": True,
                "parsed_policy_rationale": {"mode": "execute"},
                "score": {"notes": "ok"},
            }
        )
    write_jsonl(current_path, rows)
    write_jsonl(baseline_path, rows)


def write_bridge_inputs(tmp_path: Path) -> dict[str, Path]:
    project_root = tmp_path
    reports_runtime = project_root / "reports" / "runtime"
    reports_training = project_root / "reports" / "training"
    training_dir = project_root / "training"
    sibling_backend = tmp_path / "Felnx" / "NullXoid" / ".NullXoid" / "backend"

    write_text(reports_runtime / "V1_5_2_NEXT_STEP_DECISION.md", "# V1.5.2\n\nV1_5_2_CANDIDATE_READY_FOR_RUNTIME_BRIDGE\n")
    write_json(
        reports_runtime / "v1_5_2_narrow_runtime_sft_training_run.json",
        {
            "status": "V1_5_2_CANDIDATE_READY_FOR_RUNTIME_BRIDGE",
            "candidate_checkpoint": CANDIDATE_CHECKPOINT,
            "candidate_runtime_bridge_required": True,
        },
    )
    write_text(reports_runtime / "V1_4_3A_NEXT_STEP_DECISION.md", "# V1.4.3a\n\nRUNTIME_BACKEND_IDENTITY_POLICY_READY\n")
    write_json(
        reports_runtime / "v1_4_3a_backend_identity_policy.json",
        {
            "status": "RUNTIME_BACKEND_IDENTITY_POLICY_READY",
            "alias_model_id": "lv7_sft_smoke_v1_0_5:qwen2.5-1.5b-instruct",
            "accepted_adapter_path": "models/adapters/lv7_sft_smoke_v1_0_5/",
            "wrapper_artifact": "NullXoid-1.0.0-rc2-windows-x64",
            "release_tag": "v1.0-nullxoid-cpp-l7-release-candidate-rc2",
            "desktop_commit": "2744dd1cf9ca9b1954182275b17cecdaa0639a56",
            "backend_tag": "v0.2-nullxoid-backend-l7-ready",
        },
    )
    write_exact_eval_pair(
        reports_training / "v1_5_1_exact_eval_results.jsonl",
        reports_training / "v1_0_5_exact_eval_results.jsonl",
    )
    write_text(
        training_dir / "analyze_v1_4_3_runtime_scenario_results.py",
        "def x():\n    model_adapter_path_is_accepted('x')\n    return ACCEPTED_CHECKPOINT\n",
    )

    accepted_dir = project_root / "models" / "adapters" / "lv7_sft_smoke_v1_0_5"
    candidate_dir = project_root / "models" / "adapters" / "lv7_sft_runtime_repair_v1_5_1"
    accepted_dir.mkdir(parents=True, exist_ok=True)
    candidate_dir.mkdir(parents=True, exist_ok=True)

    write_text(
        sibling_backend / "providers" / "lv7_alias.py",
        "\n".join(
            [
                "ALIAS_SPECS = ()",
                "def binding_info(model: Optional[str] = None):",
                f"    return '{CANDIDATE_ALIAS_MODEL_ID}'",
                f"    # {CANDIDATE_CHECKPOINT}",
                f"    # {EXPECTED_BASE_MODEL}",
                "def available_bindings():",
                "    return []",
                "def warm_model(model: Optional[str] = None):",
                "    return True",
            ]
        ),
    )
    write_text(
        sibling_backend / "providers" / "ollama.py",
        "\n".join(
            [
                "if lv7_alias.is_alias_model(model):",
                "    return await lv7_alias.warm_model(model)",
                "if lv7_alias.is_alias_model(req.model):",
            ]
        ),
    )
    write_text(
        sibling_backend / "tests" / "test_lv7_model_alias.py",
        "\n".join(
            [
                "def test_binding_info_supports_candidate_alias_and_candidate_identity(): pass",
                "def test_chat_stream_accepts_candidate_alias_via_existing_model_field(): pass",
                "CANDIDATE_ALIAS_MODEL_ID = 'x'",
                CANDIDATE_CHECKPOINT,
            ]
        ),
    )

    return {
        "project_root": project_root,
        "reports_runtime": reports_runtime,
        "reports_training": reports_training,
        "training_dir": training_dir,
        "sibling_backend": sibling_backend,
    }


def test_v1_5_3_missing_bridge_inputs_is_incomplete(tmp_path):
    runtime_dir = tmp_path / "reports" / "runtime"

    summary = analyze_v1_5_3_candidate_runtime_recheck_bridge(
        v1_5_2_decision_report_path=runtime_dir / "missing.md",
        v1_5_2_json_report_path=runtime_dir / "missing.json",
        v1_4_3a_decision_report_path=runtime_dir / "missing_43a.md",
        v1_4_3a_policy_json_path=runtime_dir / "missing_43a.json",
        current_exact_results_path=tmp_path / "reports" / "training" / "missing_current.jsonl",
        baseline_exact_results_path=tmp_path / "reports" / "training" / "missing_baseline.jsonl",
        v1_4_3_analyzer_path=tmp_path / "training" / "missing_analyzer.py",
        backend_alias_provider_path=tmp_path / "backend" / "providers" / "lv7_alias.py",
        backend_ollama_provider_path=tmp_path / "backend" / "providers" / "ollama.py",
        backend_alias_test_path=tmp_path / "backend" / "tests" / "test_lv7_model_alias.py",
        implementation_report_path=runtime_dir / "V1_5_3_CANDIDATE_RUNTIME_RECHECK_BRIDGE.md",
        matrix_report_path=runtime_dir / "V1_5_3_RUNTIME_BRIDGE_MATRIX.md",
        decision_report_path=runtime_dir / "V1_5_3_NEXT_STEP_DECISION.md",
        json_report_path=runtime_dir / "v1_5_3_candidate_runtime_recheck_bridge.json",
    )

    assert summary["status"] == STATUS_INCOMPLETE
    assert last_nonempty_line(runtime_dir / "V1_5_3_NEXT_STEP_DECISION.md") == STATUS_INCOMPLETE


def test_v1_5_3_invalid_backend_alias_contract_is_invalid(tmp_path):
    paths = write_bridge_inputs(tmp_path)
    bad_provider = paths["sibling_backend"] / "providers" / "lv7_alias.py"
    write_text(bad_provider, "def binding_info(model: Optional[str] = None):\n    return 'broken'\n")

    summary = analyze_v1_5_3_candidate_runtime_recheck_bridge(
        v1_5_2_decision_report_path=paths["reports_runtime"] / "V1_5_2_NEXT_STEP_DECISION.md",
        v1_5_2_json_report_path=paths["reports_runtime"] / "v1_5_2_narrow_runtime_sft_training_run.json",
        v1_4_3a_decision_report_path=paths["reports_runtime"] / "V1_4_3A_NEXT_STEP_DECISION.md",
        v1_4_3a_policy_json_path=paths["reports_runtime"] / "v1_4_3a_backend_identity_policy.json",
        current_exact_results_path=paths["reports_training"] / "v1_5_1_exact_eval_results.jsonl",
        baseline_exact_results_path=paths["reports_training"] / "v1_0_5_exact_eval_results.jsonl",
        v1_4_3_analyzer_path=paths["training_dir"] / "analyze_v1_4_3_runtime_scenario_results.py",
        backend_alias_provider_path=bad_provider,
        backend_ollama_provider_path=paths["sibling_backend"] / "providers" / "ollama.py",
        backend_alias_test_path=paths["sibling_backend"] / "tests" / "test_lv7_model_alias.py",
        implementation_report_path=paths["reports_runtime"] / "V1_5_3_CANDIDATE_RUNTIME_RECHECK_BRIDGE.md",
        matrix_report_path=paths["reports_runtime"] / "V1_5_3_RUNTIME_BRIDGE_MATRIX.md",
        decision_report_path=paths["reports_runtime"] / "V1_5_3_NEXT_STEP_DECISION.md",
        json_report_path=paths["reports_runtime"] / "v1_5_3_candidate_runtime_recheck_bridge.json",
    )

    assert summary["status"] == STATUS_INVALID
    assert last_nonempty_line(paths["reports_runtime"] / "V1_5_3_NEXT_STEP_DECISION.md") == STATUS_INVALID


def test_v1_5_3_valid_bridge_writes_ready_status(tmp_path):
    paths = write_bridge_inputs(tmp_path)

    summary = analyze_v1_5_3_candidate_runtime_recheck_bridge(
        v1_5_2_decision_report_path=paths["reports_runtime"] / "V1_5_2_NEXT_STEP_DECISION.md",
        v1_5_2_json_report_path=paths["reports_runtime"] / "v1_5_2_narrow_runtime_sft_training_run.json",
        v1_4_3a_decision_report_path=paths["reports_runtime"] / "V1_4_3A_NEXT_STEP_DECISION.md",
        v1_4_3a_policy_json_path=paths["reports_runtime"] / "v1_4_3a_backend_identity_policy.json",
        current_exact_results_path=paths["reports_training"] / "v1_5_1_exact_eval_results.jsonl",
        baseline_exact_results_path=paths["reports_training"] / "v1_0_5_exact_eval_results.jsonl",
        v1_4_3_analyzer_path=paths["training_dir"] / "analyze_v1_4_3_runtime_scenario_results.py",
        backend_alias_provider_path=paths["sibling_backend"] / "providers" / "lv7_alias.py",
        backend_ollama_provider_path=paths["sibling_backend"] / "providers" / "ollama.py",
        backend_alias_test_path=paths["sibling_backend"] / "tests" / "test_lv7_model_alias.py",
        implementation_report_path=paths["reports_runtime"] / "V1_5_3_CANDIDATE_RUNTIME_RECHECK_BRIDGE.md",
        matrix_report_path=paths["reports_runtime"] / "V1_5_3_RUNTIME_BRIDGE_MATRIX.md",
        decision_report_path=paths["reports_runtime"] / "V1_5_3_NEXT_STEP_DECISION.md",
        json_report_path=paths["reports_runtime"] / "v1_5_3_candidate_runtime_recheck_bridge.json",
    )

    payload = json.loads(
        (paths["reports_runtime"] / "v1_5_3_candidate_runtime_recheck_bridge.json").read_text(
            encoding="utf-8"
        )
    )
    assert summary["status"] == STATUS_READY
    assert payload["status"] == STATUS_READY
    assert payload["candidate_checkpoint"] == CANDIDATE_CHECKPOINT
    assert payload["candidate_alias_model_id"] == CANDIDATE_ALIAS_MODEL_ID
    assert payload["backend_request_shape_unchanged"] is True
    assert payload["next_executable_milestone"] == NEXT_EXECUTABLE_MILESTONE
    assert last_nonempty_line(paths["reports_runtime"] / "V1_5_3_NEXT_STEP_DECISION.md") == STATUS_READY


def test_v1_5_3_analyzer_source_avoids_runtime_execution_training_and_subprocess():
    source = (
        Path(__file__).resolve().parents[1]
        / "training"
        / "analyze_v1_5_3_candidate_runtime_recheck_bridge.py"
    ).read_text(encoding="utf-8")

    banned_fragments = [
        "subprocess",
        "Popen(",
        "train_sft_qlora",
        "run_holdout_eval",
        "evals.run_eval",
        "python training",
    ]
    for fragment in banned_fragments:
        assert fragment not in source, f"Analyzer should not reference forbidden execution path: {fragment}"


def test_v1_5_3_repo_artifacts_exist_and_current_workspace_is_ready():
    required = [
        Path(__file__).resolve().parents[1] / "training" / "analyze_v1_5_3_candidate_runtime_recheck_bridge.py",
        Path(__file__).resolve().parents[1] / "reports" / "runtime" / "V1_5_3_CANDIDATE_RUNTIME_RECHECK_BRIDGE.md",
        Path(__file__).resolve().parents[1] / "reports" / "runtime" / "V1_5_3_RUNTIME_BRIDGE_MATRIX.md",
        Path(__file__).resolve().parents[1] / "reports" / "runtime" / "V1_5_3_NEXT_STEP_DECISION.md",
        Path(__file__).resolve().parents[1] / "reports" / "runtime" / "v1_5_3_candidate_runtime_recheck_bridge.json",
    ]
    for path in required:
        assert path.exists(), f"Missing v1.5.3 artifact: {path}"

    decision_path = Path(__file__).resolve().parents[1] / "reports" / "runtime" / "V1_5_3_NEXT_STEP_DECISION.md"
    assert last_nonempty_line(decision_path) in APPROVED_STATUSES

