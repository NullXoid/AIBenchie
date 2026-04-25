from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


BOOTSTRAP_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(BOOTSTRAP_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOOTSTRAP_PROJECT_ROOT))

from training.analyze_v1_4_1_external_m6_runtime_eval import (  # noqa: E402
    EXPECTED_ARTIFACT,
    EXPECTED_BACKEND_TAG,
    EXPECTED_DESKTOP_COMMIT,
    EXPECTED_RELEASE_TAG,
)
from training.analyze_v1_4_runtime_eval_readiness import (  # noqa: E402
    PROJECT_ROOT,
    render_markdown_table,
    write_report,
)
from training.analyze_v1_5_12_promoted_runtime_release_readiness import (  # noqa: E402
    EXPECTED_BACKEND_ANCHOR_COMMIT,
    EXPECTED_BACKEND_COMMIT,
    EXPECTED_BACKEND_COMMIT_POLICY,
)
from training.lv7_accepted_runtime_identity import (  # noqa: E402
    ACCEPTED_RUNTIME_ALIAS_MODEL_ID,
    ACCEPTED_RUNTIME_BASE_MODEL,
    ACCEPTED_RUNTIME_CHECKPOINT,
)


REPORTS_RUNTIME_DIR = PROJECT_ROOT / "reports" / "runtime"

DEFAULT_RUNTIME_OUTPUTS = REPORTS_RUNTIME_DIR / "v1_5_runtime_outputs.jsonl"
DEFAULT_RUNTIME_EXECUTION_MANIFEST = REPORTS_RUNTIME_DIR / "v1_5_runtime_execution_manifest.json"
DEFAULT_CONTRACT_REPORT = REPORTS_RUNTIME_DIR / "V1_5_13_ANDROID_CANCEL_TIMEOUT_FALLBACK_CONTRACT.md"
DEFAULT_CONTRACT_MATRIX = REPORTS_RUNTIME_DIR / "V1_5_13_ANDROID_CANCEL_TIMEOUT_FALLBACK_MATRIX.md"
DEFAULT_DECISION_REPORT = REPORTS_RUNTIME_DIR / "V1_5_13_NEXT_STEP_DECISION.md"
DEFAULT_JSON_REPORT = REPORTS_RUNTIME_DIR / "v1_5_13_android_cancel_timeout_fallback_contract.json"

SCENARIO_ID = "cancel_timeout_fallback_runtime_001"
SCENARIO_FILE = "evals/runtime/v1_4/cancel_timeout_fallback_runtime_001.yaml"
EXPECTED_SANITIZED_FALLBACK = "sanitized fallback"
EXPECTED_PASS2_STATES = {"cancelled_fallback", "timeout_fallback"}
EXPECTED_SIGNAL = {
    "second_pass_required": True,
    "reason": "verify fallback handling",
    "pass_type": "verify",
}

STATUS_READY = "V1_5_13_ANDROID_CANCEL_TIMEOUT_FALLBACK_CONTRACT_READY"
STATUS_BLOCKED = "V1_5_13_ANDROID_CANCEL_TIMEOUT_FALLBACK_CONTRACT_BLOCKED"
APPROVED_STATUSES = {STATUS_READY, STATUS_BLOCKED}

FENCED_SIGNAL_RE = re.compile(r"```nullxoid_signal\s*(\{.*?\})\s*```", re.DOTALL)


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def check(rows: list[list[str]], item: str, expected: str, observed: Any) -> None:
    observed_str = str(observed)
    result = "pass" if observed_str == expected else "fail"
    rows.append([item, expected, observed_str, result])
    require(result == "pass", f"{item} expected {expected}, observed {observed_str}")


def check_bool(rows: list[list[str]], item: str, observed: Any) -> None:
    check(rows, item, "True", observed)


def extract_nullxoid_signal(raw_model_text: str) -> dict[str, Any]:
    match = FENCED_SIGNAL_RE.search(raw_model_text)
    require(match is not None, "raw model text is missing fenced nullxoid_signal")
    payload = json.loads(match.group(1))
    require(isinstance(payload, dict), "nullxoid_signal payload must be a JSON object")
    return payload


def select_cancel_timeout_record(records: list[dict[str, Any]]) -> dict[str, Any]:
    matches = [record for record in records if record.get("scenario_id") == SCENARIO_ID]
    require(len(matches) == 1, f"expected exactly one {SCENARIO_ID} runtime record, observed {len(matches)}")
    return matches[0]


def validate_cancel_timeout_contract(
    *,
    records: list[dict[str, Any]],
    manifest: dict[str, Any],
    rows: list[list[str]],
) -> dict[str, Any]:
    record = select_cancel_timeout_record(records)
    final_text = str(record.get("final_emitted_text", ""))
    raw_text = str(record.get("raw_model_text", ""))
    signal = extract_nullxoid_signal(raw_text)

    check_bool(rows, "manifest contains scenario", SCENARIO_ID in manifest.get("scenario_ids", []))
    check(rows, "manifest scenario count", "10", manifest.get("scenario_count"))
    check(rows, "manifest adapter", ACCEPTED_RUNTIME_CHECKPOINT, manifest.get("model_adapter_path"))
    check(rows, "manifest alias", ACCEPTED_RUNTIME_ALIAS_MODEL_ID, manifest.get("alias_model_id"))
    check(rows, "manifest backend commit", EXPECTED_BACKEND_COMMIT, manifest.get("backend_commit"))
    check(rows, "manifest backend policy", EXPECTED_BACKEND_COMMIT_POLICY, manifest.get("backend_commit_policy"))
    check(rows, "manifest backend anchor", EXPECTED_BACKEND_ANCHOR_COMMIT, manifest.get("backend_anchor_commit"))

    check(rows, "scenario file", SCENARIO_FILE, str(record.get("scenario_file", "")).replace("\\", "/"))
    check(rows, "final outcome", "pass", record.get("final_outcome"))
    check(rows, "gate decision", "approved", record.get("gate_decision"))
    check(rows, "wrapper failures", "[]", record.get("wrapper_contract_failures"))
    check(rows, "model failures", "[]", record.get("model_contract_failures"))
    check(rows, "adapter", ACCEPTED_RUNTIME_CHECKPOINT, record.get("model_adapter_path"))
    check(rows, "wrapper artifact", EXPECTED_ARTIFACT, record.get("wrapper_artifact"))
    check(rows, "release tag", EXPECTED_RELEASE_TAG, record.get("release_tag"))
    check(rows, "desktop commit", EXPECTED_DESKTOP_COMMIT, record.get("desktop_commit"))
    check(rows, "backend tag", EXPECTED_BACKEND_TAG, record.get("backend_tag"))
    check(rows, "backend commit", EXPECTED_BACKEND_COMMIT, record.get("backend_commit"))

    check_bool(rows, "fallback used", record.get("fallback_used"))
    check_bool(rows, "cancel or timeout observed", bool(record.get("cancel_observed") or record.get("timeout_observed")))
    check_bool(rows, "pass2 fallback state", record.get("pass2_state") in EXPECTED_PASS2_STATES)
    check_bool(rows, "fenced signal present in raw model text", record.get("fenced_nullxoid_signal_present"))
    check_bool(rows, "fenced signal stripped from final output", record.get("nullxoid_signal_stripped"))
    check_bool(rows, "final output excludes fenced signal", "```nullxoid_signal" not in final_text)
    check_bool(rows, "final output includes sanitized fallback", EXPECTED_SANITIZED_FALLBACK in final_text)
    check_bool(rows, "final output suppresses partial tool output", "partial tool output" not in final_text.lower())
    check_bool(rows, "final output suppresses unfinished stream", "unfinished execution stream" not in final_text.lower())

    for key, expected in EXPECTED_SIGNAL.items():
        check(rows, f"verify signal {key}", str(expected), signal.get(key))
    check_bool(rows, "verify signal confidence bounded", 0 <= float(signal.get("confidence", -1)) <= 1)
    check_bool(rows, "verify signal confidence high", float(signal.get("confidence", 0)) >= 0.9)

    final_response = final_text.split("response:", 1)[-1].strip() if "response:" in final_text else final_text.strip()
    check(rows, "sanitized fallback response", EXPECTED_SANITIZED_FALLBACK, final_response)

    return {
        "record": record,
        "signal": signal,
        "final_response": final_response,
    }


def build_android_contract(record: dict[str, Any], signal: dict[str, Any], final_response: str) -> dict[str, Any]:
    return {
        "contract_id": "lv7_android_cancel_timeout_fallback_contract_v1_5_13",
        "scenario_id": SCENARIO_ID,
        "scenario_file": SCENARIO_FILE,
        "accepted_baseline": {
            "checkpoint": ACCEPTED_RUNTIME_CHECKPOINT,
            "alias_model_id": ACCEPTED_RUNTIME_ALIAS_MODEL_ID,
            "base_model": ACCEPTED_RUNTIME_BASE_MODEL,
            "wrapper_artifact": EXPECTED_ARTIFACT,
            "release_tag": EXPECTED_RELEASE_TAG,
            "desktop_commit": EXPECTED_DESKTOP_COMMIT,
            "backend_tag": EXPECTED_BACKEND_TAG,
            "backend_commit": EXPECTED_BACKEND_COMMIT,
            "backend_commit_policy": EXPECTED_BACKEND_COMMIT_POLICY,
            "backend_anchor_commit": EXPECTED_BACKEND_ANCHOR_COMMIT,
        },
        "android_client_contract": {
            "trigger": "second pass is canceled or times out after pass 1 completed",
            "fallback_state_values": sorted(EXPECTED_PASS2_STATES),
            "user_visible_response_exact": final_response,
            "user_visible_output_source": "final_emitted_text",
            "must_not_render": [
                "raw_model_text",
                "```nullxoid_signal fenced block",
                "partial tool output",
                "unfinished execution stream",
            ],
            "second_pass_verify_signal": {
                "source": "raw_model_text fenced nullxoid_signal",
                "strip_before_user_render": True,
                "payload": signal,
                "required_fields": sorted(EXPECTED_SIGNAL.keys()) + ["confidence"],
            },
            "compatibility_invariants": [
                "Preserve scenario_id, prompt_sha256, scenario_sha256, accepted checkpoint, wrapper artifact, release tag, backend tag, backend commit, and backend commit policy as evidence fields.",
                "Treat pass2_state values cancelled_fallback and timeout_fallback as fallback terminal states, not as execute, halt, or generic failure states.",
                "Render only the sanitized final output to the user; never render raw_model_text or the fenced nullxoid_signal block.",
                "Forward the parsed second_pass_required=true and pass_type=verify signal to the client verification lane or telemetry lane before marking the flow complete.",
                "Keep fallback_used=true and cancel_observed or timeout_observed=true visible to telemetry so non-Windows clients remain comparable with the accepted Windows v1.5.1 baseline.",
                "Do not append platform-specific diagnostics, stack traces, tool logs, or partial execution stream content to the sanitized fallback response.",
            ],
        },
        "accepted_runtime_evidence": {
            "executed_at": record.get("executed_at"),
            "pass1_state": record.get("pass1_state"),
            "pass2_state": record.get("pass2_state"),
            "fallback_used": record.get("fallback_used"),
            "cancel_observed": record.get("cancel_observed"),
            "timeout_observed": record.get("timeout_observed"),
            "final_outcome": record.get("final_outcome"),
            "gate_decision": record.get("gate_decision"),
            "prompt_sha256": record.get("prompt_sha256"),
            "scenario_sha256": record.get("scenario_sha256"),
        },
    }


def write_contract_report(
    *,
    output_path: Path,
    status: str,
    contract: dict[str, Any] | None,
    notes: list[str],
) -> None:
    lines = [
        "# V1.5.13 Android Cancel/Timeout Fallback Contract",
        "",
        f"- Status: `{status}`",
        f"- Scenario: `{SCENARIO_ID}`.",
        f"- Accepted checkpoint: `{ACCEPTED_RUNTIME_CHECKPOINT}`.",
        f"- Accepted alias: `{ACCEPTED_RUNTIME_ALIAS_MODEL_ID}`.",
        "- Scope: downstream non-Windows client contract only; no runtime execution, model training, wrapper mutation, or backend mutation.",
        "",
    ]
    if contract:
        client_contract = contract["android_client_contract"]
        evidence = contract["accepted_runtime_evidence"]
        signal = client_contract["second_pass_verify_signal"]["payload"]
        lines.extend(
            [
                "## Required Client Behavior",
                "",
                f"- Trigger: {client_contract['trigger']}.",
                f"- Terminal fallback states: `{', '.join(client_contract['fallback_state_values'])}`.",
                f"- User-visible response: `{client_contract['user_visible_response_exact']}`.",
                f"- Verify signal: `second_pass_required={signal.get('second_pass_required')}`, `pass_type={signal.get('pass_type')}`, `reason={signal.get('reason')}`.",
                f"- Accepted evidence state: `pass1_state={evidence.get('pass1_state')}`, `pass2_state={evidence.get('pass2_state')}`, `fallback_used={evidence.get('fallback_used')}`.",
                "",
                "## Compatibility Invariants",
                "",
            ]
        )
        lines.extend(f"- {item}" for item in client_contract["compatibility_invariants"])
    lines.extend(["", "## Notes", ""])
    lines.extend(f"- {note}" for note in notes)
    write_report(output_path, lines)


def write_matrix_report(*, output_path: Path, rows: list[list[str]]) -> None:
    write_report(
        output_path,
        [
            "# V1.5.13 Android Cancel/Timeout Fallback Matrix",
            "",
            render_markdown_table(["check", "expected", "observed", "result"], rows),
        ],
    )


def write_decision_report(*, output_path: Path, status: str) -> None:
    write_report(
        output_path,
        [
            "# V1.5.13 Next Step Decision",
            "",
            f"- Scenario `{SCENARIO_ID}` has a focused downstream contract for Android/non-Windows clients.",
            "- The contract is derived from accepted v1.5 runtime outputs and the v1.5 runtime execution manifest.",
            "- No model, DPO, scorer, wrapper, backend, or adapter promotion work is performed.",
            "",
            status,
        ],
    )


def analyze_v1_5_13_cancel_timeout_fallback_android_contract(
    *,
    runtime_outputs_path: Path = DEFAULT_RUNTIME_OUTPUTS,
    runtime_execution_manifest_path: Path = DEFAULT_RUNTIME_EXECUTION_MANIFEST,
    contract_report_path: Path = DEFAULT_CONTRACT_REPORT,
    contract_matrix_path: Path = DEFAULT_CONTRACT_MATRIX,
    decision_report_path: Path = DEFAULT_DECISION_REPORT,
    json_report_path: Path = DEFAULT_JSON_REPORT,
) -> dict[str, Any]:
    source_artifacts = {
        "runtime_outputs": display_path(runtime_outputs_path),
        "runtime_execution_manifest": display_path(runtime_execution_manifest_path),
    }
    rows: list[list[str]] = []
    notes: list[str] = []
    contract: dict[str, Any] | None = None
    status = STATUS_READY
    try:
        records = read_jsonl(runtime_outputs_path)
        manifest = read_json(runtime_execution_manifest_path)
        evidence = validate_cancel_timeout_contract(records=records, manifest=manifest, rows=rows)
        contract = build_android_contract(
            record=evidence["record"],
            signal=evidence["signal"],
            final_response=evidence["final_response"],
        )
        notes.append("accepted v1.5 runtime evidence proves sanitized fallback with stripped verify signal")
        notes.append("Android/non-Windows clients can implement against the final_emitted_text plus parsed verify signal contract")
    except (FileNotFoundError, ValueError, KeyError, json.JSONDecodeError, TypeError) as exc:
        status = STATUS_BLOCKED
        notes.append(str(exc))

    write_contract_report(output_path=contract_report_path, status=status, contract=contract, notes=notes)
    write_matrix_report(output_path=contract_matrix_path, rows=rows)
    write_decision_report(output_path=decision_report_path, status=status)

    payload = {
        "milestone": "LV7 v1.5.13",
        "status": status,
        "contract_ready": status == STATUS_READY,
        "scenario_id": SCENARIO_ID,
        "accepted_runtime_checkpoint": ACCEPTED_RUNTIME_CHECKPOINT if status == STATUS_READY else None,
        "accepted_runtime_alias_model_id": ACCEPTED_RUNTIME_ALIAS_MODEL_ID if status == STATUS_READY else None,
        "source_artifact_paths": source_artifacts,
        "validation_rows": rows,
        "contract": contract,
        "next_recommended_action": (
            "Implement the Android cancel/timeout fallback UI and telemetry path against this contract."
            if status == STATUS_READY
            else "Resolve blocked cancel/timeout fallback contract evidence."
        ),
        "notes": notes,
    }
    json_report_path.parent.mkdir(parents=True, exist_ok=True)
    json_report_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Define Android-safe LV7 cancel/timeout fallback contract.")
    return parser.parse_args()


def main() -> None:
    parse_args()
    summary = analyze_v1_5_13_cancel_timeout_fallback_android_contract()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
