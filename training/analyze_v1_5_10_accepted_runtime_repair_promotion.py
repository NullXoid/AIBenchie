from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


BOOTSTRAP_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(BOOTSTRAP_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOOTSTRAP_PROJECT_ROOT))

from training.analyze_v1_4_1_external_m6_runtime_eval import (  # noqa: E402
    ACCEPTED_CHECKPOINT as PREVIOUS_ACCEPTED_CHECKPOINT,
    EVIDENCE_ONLY_SFT_ADAPTERS,
    EXPECTED_ARTIFACT,
    EXPECTED_BACKEND_TAG,
    EXPECTED_DESKTOP_COMMIT,
    EXPECTED_RELEASE_TAG,
    PARKED_DPO_ADAPTERS,
)
from training.analyze_v1_4_runtime_eval_readiness import (  # noqa: E402
    PROJECT_ROOT,
    last_nonempty_line,
    render_markdown_table,
    write_report,
)
from training.analyze_v1_5_3_candidate_runtime_recheck_bridge import (  # noqa: E402
    CANDIDATE_ALIAS_MODEL_ID,
    CANDIDATE_CHECKPOINT,
    EXPECTED_BASE_MODEL,
)
from training.analyze_v1_5_4_candidate_runtime_scenario_results import (  # noqa: E402
    STATUS_PASSED as STATUS_V1_5_4_PASSED,
    read_json,
)
from training.analyze_v1_5_5_candidate_runtime_failure_diagnosis import (  # noqa: E402
    STATUS_COMPLETE as STATUS_V1_5_5_COMPLETE,
)
from training.analyze_v1_5_9_candidate_runtime_repair_acceptance import (  # noqa: E402
    EXPECTED_BACKEND_ANCHOR_COMMIT,
    EXPECTED_BACKEND_COMMIT,
    EXPECTED_BACKEND_COMMIT_POLICY,
    STATUS_ACCEPTED as STATUS_V1_5_9_ACCEPTED,
)
from training.lv7_accepted_runtime_identity import (  # noqa: E402
    ACCEPTED_RUNTIME_ALIAS_MODEL_ID,
    ACCEPTED_RUNTIME_BASE_MODEL,
    ACCEPTED_RUNTIME_CHECKPOINT,
    PROMOTION_STATUS,
)


REPORTS_RUNTIME_DIR = PROJECT_ROOT / "reports" / "runtime"

DEFAULT_V1_5_4_DECISION_REPORT = REPORTS_RUNTIME_DIR / "V1_5_4_NEXT_STEP_DECISION.md"
DEFAULT_V1_5_4_JSON_REPORT = REPORTS_RUNTIME_DIR / "v1_5_4_candidate_runtime_results_ingestion.json"
DEFAULT_V1_5_5_DECISION_REPORT = REPORTS_RUNTIME_DIR / "V1_5_5_NEXT_STEP_DECISION.md"
DEFAULT_V1_5_5_JSON_REPORT = REPORTS_RUNTIME_DIR / "v1_5_5_candidate_runtime_failure_diagnosis.json"
DEFAULT_V1_5_8_JSON_REPORT = REPORTS_RUNTIME_DIR / "v1_5_8_targeted_repair_attempt_loop.json"
DEFAULT_V1_5_9_DECISION_REPORT = REPORTS_RUNTIME_DIR / "V1_5_9_NEXT_STEP_DECISION.md"
DEFAULT_V1_5_9_JSON_REPORT = REPORTS_RUNTIME_DIR / "v1_5_9_candidate_runtime_repair_acceptance.json"
DEFAULT_RUNTIME_EXECUTION_MANIFEST = REPORTS_RUNTIME_DIR / "v1_5_runtime_execution_manifest.json"

DEFAULT_PROMOTION_REPORT = REPORTS_RUNTIME_DIR / "V1_5_10_ACCEPTED_RUNTIME_REPAIR_PROMOTION.md"
DEFAULT_PROMOTION_MATRIX = REPORTS_RUNTIME_DIR / "V1_5_10_PROMOTION_MATRIX.md"
DEFAULT_DECISION_REPORT = REPORTS_RUNTIME_DIR / "V1_5_10_NEXT_STEP_DECISION.md"
DEFAULT_JSON_REPORT = REPORTS_RUNTIME_DIR / "v1_5_10_accepted_runtime_repair_promotion.json"

STATUS_COMPLETE = PROMOTION_STATUS
STATUS_BLOCKED = "V1_5_10_PROMOTION_BLOCKED"
APPROVED_STATUSES = {STATUS_COMPLETE, STATUS_BLOCKED}

NEXT_RECOMMENDED_ACTION = "Use models/adapters/lv7_sft_runtime_repair_v1_5_1/ as the accepted LV7 runtime checkpoint."


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def check_value(rows: list[list[str]], item: str, expected: str, observed: Any) -> None:
    observed_str = str(observed)
    result = "pass" if observed_str == expected else "fail"
    rows.append([item, expected, observed_str, result])
    require(result == "pass", f"{item} expected {expected}, observed {observed_str}")


def validate_promotion_evidence(
    *,
    v1_5_4_decision_report_path: Path,
    v1_5_4_json_report_path: Path,
    v1_5_5_decision_report_path: Path,
    v1_5_5_json_report_path: Path,
    v1_5_8_json_report_path: Path,
    v1_5_9_decision_report_path: Path,
    v1_5_9_json_report_path: Path,
    runtime_execution_manifest_path: Path,
) -> dict[str, Any]:
    rows: list[list[str]] = []
    required_paths = [
        v1_5_4_decision_report_path,
        v1_5_4_json_report_path,
        v1_5_5_decision_report_path,
        v1_5_5_json_report_path,
        v1_5_8_json_report_path,
        v1_5_9_decision_report_path,
        v1_5_9_json_report_path,
        runtime_execution_manifest_path,
        PROJECT_ROOT / PREVIOUS_ACCEPTED_CHECKPOINT,
        PROJECT_ROOT / CANDIDATE_CHECKPOINT,
    ]
    missing = [display_path(path) for path in required_paths if not path.exists()]
    require(not missing, "missing required promotion evidence: " + ", ".join(missing))

    check_value(
        rows,
        "v1.5.4 decision",
        STATUS_V1_5_4_PASSED,
        last_nonempty_line(v1_5_4_decision_report_path),
    )
    check_value(
        rows,
        "v1.5.5 decision",
        STATUS_V1_5_5_COMPLETE,
        last_nonempty_line(v1_5_5_decision_report_path),
    )
    check_value(
        rows,
        "v1.5.9 decision",
        STATUS_V1_5_9_ACCEPTED,
        last_nonempty_line(v1_5_9_decision_report_path),
    )

    v1_5_4_payload = read_json(v1_5_4_json_report_path)
    v1_5_5_payload = read_json(v1_5_5_json_report_path)
    v1_5_8_payload = read_json(v1_5_8_json_report_path)
    v1_5_9_payload = read_json(v1_5_9_json_report_path)
    manifest = read_json(runtime_execution_manifest_path)

    check_value(rows, "v1.5.4 JSON status", STATUS_V1_5_4_PASSED, v1_5_4_payload.get("status"))
    check_value(rows, "v1.5.5 JSON status", STATUS_V1_5_5_COMPLETE, v1_5_5_payload.get("status"))
    check_value(rows, "v1.5.8 repair loop status", "V1_5_8_TARGETED_REPAIR_COMPLETE", v1_5_8_payload.get("status"))
    check_value(
        rows,
        "v1.5.8 final runtime status",
        STATUS_V1_5_4_PASSED,
        v1_5_8_payload.get("final_candidate_runtime_status"),
    )
    check_value(rows, "v1.5.9 JSON status", STATUS_V1_5_9_ACCEPTED, v1_5_9_payload.get("status"))
    check_value(rows, "v1.5.9 previous accepted checkpoint", PREVIOUS_ACCEPTED_CHECKPOINT, v1_5_9_payload.get("accepted_checkpoint"))
    check_value(rows, "v1.5.9 candidate checkpoint", CANDIDATE_CHECKPOINT, v1_5_9_payload.get("candidate_checkpoint"))
    check_value(rows, "v1.5.9 candidate alias", CANDIDATE_ALIAS_MODEL_ID, v1_5_9_payload.get("candidate_alias_model_id"))

    check_value(rows, "candidate runtime record count", "10", v1_5_9_payload.get("trusted_record_count"))
    check_value(rows, "candidate pass count", "10", v1_5_9_payload.get("pass_count"))
    check_value(rows, "candidate fail count", "0", v1_5_9_payload.get("fail_count"))
    check_value(rows, "candidate promotion recommended", "True", v1_5_9_payload.get("promotion_recommended"))
    check_value(rows, "candidate not previously promoted", "False", v1_5_9_payload.get("promoted_by_this_milestone"))

    check_value(rows, "manifest model adapter path", CANDIDATE_CHECKPOINT, manifest.get("model_adapter_path"))
    check_value(rows, "manifest alias model id", CANDIDATE_ALIAS_MODEL_ID, manifest.get("alias_model_id"))
    check_value(rows, "manifest backend commit", EXPECTED_BACKEND_COMMIT, manifest.get("backend_commit"))
    check_value(rows, "manifest backend policy", EXPECTED_BACKEND_COMMIT_POLICY, manifest.get("backend_commit_policy"))
    check_value(rows, "manifest backend anchor", EXPECTED_BACKEND_ANCHOR_COMMIT, manifest.get("backend_anchor_commit"))

    require(ACCEPTED_RUNTIME_CHECKPOINT == CANDIDATE_CHECKPOINT, "current identity module does not promote candidate checkpoint")
    require(ACCEPTED_RUNTIME_ALIAS_MODEL_ID == CANDIDATE_ALIAS_MODEL_ID, "current identity module has wrong alias")
    require(ACCEPTED_RUNTIME_BASE_MODEL == EXPECTED_BASE_MODEL, "current identity module has wrong base model")

    return {
        "matrix_rows": rows,
        "v1_5_9_payload": v1_5_9_payload,
        "runtime_manifest": manifest,
    }


def write_promotion_report(
    *,
    output_path: Path,
    status: str,
    matrix_rows: list[list[str]],
    notes: list[str],
) -> None:
    lines = [
        "# V1.5.10 Accepted Runtime Repair Promotion",
        "",
        f"- Status: `{status}`",
        f"- Previous accepted checkpoint: `{PREVIOUS_ACCEPTED_CHECKPOINT}`.",
        f"- Promoted accepted runtime checkpoint: `{ACCEPTED_RUNTIME_CHECKPOINT}`.",
        f"- Promoted runtime alias: `{ACCEPTED_RUNTIME_ALIAS_MODEL_ID}`.",
        f"- Base model: `{ACCEPTED_RUNTIME_BASE_MODEL}`.",
        f"- Wrapper artifact remains `{EXPECTED_ARTIFACT}`.",
        f"- Release tag remains `{EXPECTED_RELEASE_TAG}`.",
        f"- Desktop commit remains `{EXPECTED_DESKTOP_COMMIT}`.",
        f"- Backend tag remains `{EXPECTED_BACKEND_TAG}`.",
        f"- Backend commit policy remains `{EXPECTED_BACKEND_COMMIT_POLICY}` with executing backend `{EXPECTED_BACKEND_COMMIT}`.",
        f"- Frozen backend anchor remains `{EXPECTED_BACKEND_ANCHOR_COMMIT}` as traceability evidence.",
        "",
        "## Boundary",
        "",
        "- This milestone promotes by identity and evidence manifest only.",
        "- It does not delete or overwrite the previous v1.0.5 adapter.",
        "- It does not reopen SFT, DPO, blind suites, scorers, wrapper packaging, or backend identity work.",
        f"- Evidence-only SFT adapters remain `{EVIDENCE_ONLY_SFT_ADAPTERS[0]}` and `{EVIDENCE_ONLY_SFT_ADAPTERS[1]}`.",
        f"- Parked DPO adapters remain `{PARKED_DPO_ADAPTERS[0]}` and `{PARKED_DPO_ADAPTERS[1]}`.",
        "",
        "## Promotion Evidence",
        "",
        render_markdown_table(["check", "expected", "observed", "result"], matrix_rows),
        "",
        "## Notes",
        "",
    ]
    lines.extend(f"- {note}" for note in notes)
    if status == STATUS_COMPLETE:
        lines.extend(
            [
                "",
                "## Result",
                "",
                f"The candidate checkpoint is now the accepted LV7 runtime checkpoint: `{ACCEPTED_RUNTIME_CHECKPOINT}`.",
            ]
        )
    write_report(output_path, lines)


def write_matrix_report(*, output_path: Path, matrix_rows: list[list[str]]) -> None:
    write_report(
        output_path,
        [
            "# V1.5.10 Promotion Matrix",
            "",
            render_markdown_table(["check", "expected", "observed", "result"], matrix_rows),
        ],
    )


def write_decision_report(*, output_path: Path, status: str) -> None:
    write_report(
        output_path,
        [
            "# V1.5.10 Next Step Decision",
            "",
            f"- Previous accepted checkpoint: `{PREVIOUS_ACCEPTED_CHECKPOINT}`.",
            f"- Current accepted runtime checkpoint: `{ACCEPTED_RUNTIME_CHECKPOINT}`.",
            f"- Current accepted runtime alias: `{ACCEPTED_RUNTIME_ALIAS_MODEL_ID}`.",
            "- Promotion is evidence-backed by v1.5.4, v1.5.5, v1.5.8, and v1.5.9.",
            "- No SFT, DPO, scorer, blind-suite, wrapper, or backend work is performed by this milestone.",
            "",
            status,
        ],
    )


def analyze_v1_5_10_accepted_runtime_repair_promotion(
    *,
    v1_5_4_decision_report_path: Path = DEFAULT_V1_5_4_DECISION_REPORT,
    v1_5_4_json_report_path: Path = DEFAULT_V1_5_4_JSON_REPORT,
    v1_5_5_decision_report_path: Path = DEFAULT_V1_5_5_DECISION_REPORT,
    v1_5_5_json_report_path: Path = DEFAULT_V1_5_5_JSON_REPORT,
    v1_5_8_json_report_path: Path = DEFAULT_V1_5_8_JSON_REPORT,
    v1_5_9_decision_report_path: Path = DEFAULT_V1_5_9_DECISION_REPORT,
    v1_5_9_json_report_path: Path = DEFAULT_V1_5_9_JSON_REPORT,
    runtime_execution_manifest_path: Path = DEFAULT_RUNTIME_EXECUTION_MANIFEST,
    promotion_report_path: Path = DEFAULT_PROMOTION_REPORT,
    promotion_matrix_path: Path = DEFAULT_PROMOTION_MATRIX,
    decision_report_path: Path = DEFAULT_DECISION_REPORT,
    json_report_path: Path = DEFAULT_JSON_REPORT,
) -> dict[str, Any]:
    source_artifacts = {
        "v1_5_4_decision_report": display_path(v1_5_4_decision_report_path),
        "v1_5_4_json_report": display_path(v1_5_4_json_report_path),
        "v1_5_5_decision_report": display_path(v1_5_5_decision_report_path),
        "v1_5_5_json_report": display_path(v1_5_5_json_report_path),
        "v1_5_8_repair_loop_json": display_path(v1_5_8_json_report_path),
        "v1_5_9_decision_report": display_path(v1_5_9_decision_report_path),
        "v1_5_9_json_report": display_path(v1_5_9_json_report_path),
        "runtime_execution_manifest": display_path(runtime_execution_manifest_path),
    }
    status = STATUS_COMPLETE
    matrix_rows: list[list[str]] = []
    notes: list[str] = []
    try:
        evidence = validate_promotion_evidence(
            v1_5_4_decision_report_path=v1_5_4_decision_report_path,
            v1_5_4_json_report_path=v1_5_4_json_report_path,
            v1_5_5_decision_report_path=v1_5_5_decision_report_path,
            v1_5_5_json_report_path=v1_5_5_json_report_path,
            v1_5_8_json_report_path=v1_5_8_json_report_path,
            v1_5_9_decision_report_path=v1_5_9_decision_report_path,
            v1_5_9_json_report_path=v1_5_9_json_report_path,
            runtime_execution_manifest_path=runtime_execution_manifest_path,
        )
        matrix_rows = evidence["matrix_rows"]
        notes.append("candidate runtime repair passed all ten pinned scenarios and was accepted for promotion")
        notes.append("current accepted runtime identity now points to the v1.5.1 repair adapter")
    except (FileNotFoundError, ValueError, KeyError, json.JSONDecodeError) as exc:
        status = STATUS_BLOCKED
        notes.append(str(exc))

    write_promotion_report(
        output_path=promotion_report_path,
        status=status,
        matrix_rows=matrix_rows,
        notes=notes,
    )
    write_matrix_report(output_path=promotion_matrix_path, matrix_rows=matrix_rows)
    write_decision_report(output_path=decision_report_path, status=status)

    payload = {
        "milestone": "LV7 v1.5.10",
        "status": status,
        "promotion_complete": status == STATUS_COMPLETE,
        "previous_accepted_checkpoint": PREVIOUS_ACCEPTED_CHECKPOINT,
        "accepted_checkpoint": ACCEPTED_RUNTIME_CHECKPOINT if status == STATUS_COMPLETE else PREVIOUS_ACCEPTED_CHECKPOINT,
        "accepted_alias_model_id": ACCEPTED_RUNTIME_ALIAS_MODEL_ID if status == STATUS_COMPLETE else None,
        "accepted_base_model": ACCEPTED_RUNTIME_BASE_MODEL if status == STATUS_COMPLETE else None,
        "wrapper_artifact": EXPECTED_ARTIFACT,
        "release_tag": EXPECTED_RELEASE_TAG,
        "desktop_commit": EXPECTED_DESKTOP_COMMIT,
        "backend_tag": EXPECTED_BACKEND_TAG,
        "backend_commit": EXPECTED_BACKEND_COMMIT,
        "backend_commit_policy": EXPECTED_BACKEND_COMMIT_POLICY,
        "backend_anchor_commit": EXPECTED_BACKEND_ANCHOR_COMMIT,
        "evidence_only_sft_adapters": list(EVIDENCE_ONLY_SFT_ADAPTERS),
        "parked_dpo_adapters": list(PARKED_DPO_ADAPTERS),
        "source_artifact_paths": source_artifacts,
        "promotion_matrix": matrix_rows,
        "next_recommended_action": NEXT_RECOMMENDED_ACTION if status == STATUS_COMPLETE else "resolve blocked promotion evidence",
        "notes": notes,
    }
    json_report_path.parent.mkdir(parents=True, exist_ok=True)
    json_report_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Promote the accepted LV7 runtime repair adapter after v1.5.9 acceptance.")
    return parser.parse_args()


def main() -> None:
    parse_args()
    summary = analyze_v1_5_10_accepted_runtime_repair_promotion()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
