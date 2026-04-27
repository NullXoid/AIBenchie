from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


SOURCE_JSONL = ROOT / "data" / "lv7_traceable_batches_001R_002" / "combined" / "all_training_records_v1_1.jsonl"
SOURCE_JSONL_V1_2 = ROOT / "data" / "lv7_traceable_batches_003" / "combined" / "all_training_records_v1_2.jsonl"
SOURCE_JSONL_V1_3 = ROOT / "data" / "lv7_traceable_batches_004" / "combined" / "all_training_records_v1_3.jsonl"
SOURCE_JSONL_V1_4 = ROOT / "data" / "lv7_traceable_batches_005" / "combined" / "all_training_records_v1_4.jsonl"
SOURCE_JSONL_V1_5 = ROOT / "data" / "lv7_traceable_batches_006" / "combined" / "all_training_records_v1_5.jsonl"
SOURCE_JSONL_V1_6 = ROOT / "data" / "lv7_traceable_batches_007" / "combined" / "all_training_records_v1_6.jsonl"
SOURCE_JSONL_V1_7 = ROOT / "data" / "lv7_traceable_batches_008" / "combined" / "all_training_records_v1_7.jsonl"
SOURCE_JSONL_V1_8 = ROOT / "data" / "lv7_traceable_batches_009" / "combined" / "all_training_records_v1_8.jsonl"
SOURCE_JSONL_V1_9 = ROOT / "data" / "lv7_traceable_batches_010" / "combined" / "all_training_records_v1_9.jsonl"
SCENARIOS_DIR = ROOT / "evals" / "scenarios"
HOLDOUT_PARAPHRASE_DIR = ROOT / "evals" / "holdout" / "paraphrase_v0"
SFT_MESSAGES_V1_2 = ROOT / "data" / "pilot_v1_2" / "sft_messages.jsonl"
SFT_TRAIN_READY_V1_2 = ROOT / "data" / "pilot_v1_2" / "sft_train_ready.jsonl"
PILOT_V1_3_DIR = ROOT / "data" / "pilot_v1_3"
SFT_MESSAGES_V1_3 = ROOT / "data" / "pilot_v1_3" / "sft_messages.jsonl"
SFT_TRAIN_READY_V1_3 = ROOT / "data" / "pilot_v1_3" / "sft_train_ready.jsonl"
PILOT_V1_4_DIR = ROOT / "data" / "pilot_v1_4"
SFT_MESSAGES_V1_4 = ROOT / "data" / "pilot_v1_4" / "sft_messages.jsonl"
SFT_TRAIN_READY_V1_4 = ROOT / "data" / "pilot_v1_4" / "sft_train_ready.jsonl"
PILOT_V1_5_DIR = ROOT / "data" / "pilot_v1_5"
SFT_MESSAGES_V1_5 = ROOT / "data" / "pilot_v1_5" / "sft_messages.jsonl"
SFT_TRAIN_READY_V1_5 = ROOT / "data" / "pilot_v1_5" / "sft_train_ready.jsonl"
PILOT_V1_6_DIR = ROOT / "data" / "pilot_v1_6"
SFT_MESSAGES_V1_6 = ROOT / "data" / "pilot_v1_6" / "sft_messages.jsonl"
SFT_TRAIN_READY_V1_6 = ROOT / "data" / "pilot_v1_6" / "sft_train_ready.jsonl"
PILOT_V1_7_DIR = ROOT / "data" / "pilot_v1_7"
SFT_MESSAGES_V1_7 = ROOT / "data" / "pilot_v1_7" / "sft_messages.jsonl"
SFT_TRAIN_READY_V1_7 = ROOT / "data" / "pilot_v1_7" / "sft_train_ready.jsonl"
PILOT_V1_8_DIR = ROOT / "data" / "pilot_v1_8"
SFT_MESSAGES_V1_8 = ROOT / "data" / "pilot_v1_8" / "sft_messages.jsonl"
SFT_TRAIN_READY_V1_8 = ROOT / "data" / "pilot_v1_8" / "sft_train_ready.jsonl"
PILOT_V1_9_DIR = ROOT / "data" / "pilot_v1_9"
SFT_MESSAGES_V1_9 = ROOT / "data" / "pilot_v1_9" / "sft_messages.jsonl"
SFT_TRAIN_READY_V1_9 = ROOT / "data" / "pilot_v1_9" / "sft_train_ready.jsonl"


RUN_ARCHIVAL_ENV = "AIBENCHIE_RUN_ARCHIVAL_TESTS"
ARCHIVAL_TEST_FILES = frozenset(
    {
        "test_analyze_v1_4_1_external_m6_runtime_eval.py",
        "test_analyze_v1_4_2_runtime_scenario_eval_plan.py",
        "test_analyze_v1_4_3_runtime_scenario_results.py",
        "test_analyze_v1_4_3a_runtime_backend_identity_update.py",
        "test_analyze_v1_4_4_runtime_model_failure_diagnosis.py",
        "test_analyze_v1_4_5_policy_rationale_contract_fix.py",
        "test_analyze_v1_4_6_policy_rationale_contract_fix_implementation.py",
        "test_analyze_v1_4_7_mode_selection_fix_spec.py",
        "test_analyze_v1_4_8_mode_selection_contract_implementation.py",
        "test_analyze_v1_4_9_runtime_model_repair_investigation.py",
        "test_analyze_v1_5_0_narrow_runtime_model_repair_planning.py",
        "test_analyze_v1_5_1_narrow_runtime_sft_repair_implementation.py",
        "test_analyze_v1_5_2_narrow_runtime_sft_training_run.py",
        "test_analyze_v1_5_3_candidate_runtime_recheck_bridge.py",
        "test_analyze_v1_5_4_candidate_runtime_scenario_results.py",
        "test_analyze_v1_5_5_candidate_runtime_failure_diagnosis.py",
        "test_analyze_v1_5_6_candidate_runtime_repair_spec.py",
        "test_analyze_v1_5_9_candidate_runtime_repair_acceptance.py",
        "test_analyze_v1_5_10_accepted_runtime_repair_promotion.py",
        "test_analyze_v1_5_11_post_promotion_identity_sync.py",
        "test_analyze_v1_5_12_promoted_runtime_release_readiness.py",
        "test_dpo_smoke_v1_2_4.py",
    }
)


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _is_archival_test_file(path: str | Path) -> bool:
    return Path(path).name in ARCHIVAL_TEST_FILES


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-archival",
        action="store_true",
        default=False,
        help=(
            "Run historical AIBenchie milestone tests that require frozen local model "
            "artifacts or mutate tracked runtime reports."
        ),
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "archival: historical milestone tests that need frozen local artifacts and are opt-in by default",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    run_archival = bool(config.getoption("--run-archival")) or _truthy(os.getenv(RUN_ARCHIVAL_ENV))
    skip_archival = pytest.mark.skip(
        reason=(
            "archival artifact-dependent test; run with --run-archival or "
            f"{RUN_ARCHIVAL_ENV}=1 when frozen fixtures are available"
        )
    )

    for item in items:
        if not _is_archival_test_file(getattr(item, "path", getattr(item, "fspath", ""))):
            continue
        item.add_marker(pytest.mark.archival)
        if not run_archival:
            item.add_marker(skip_archival)
