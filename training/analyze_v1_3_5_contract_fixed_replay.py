from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


if __package__ in {None, ""}:
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
    import sys

    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from evals.run_eval import run_evaluation
    from training.analyze_holdout_results import read_jsonl
else:
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
    from evals.run_eval import run_evaluation
    from .analyze_holdout_results import read_jsonl


REPORTS_DIR = PROJECT_ROOT / "reports" / "training"
ORIGINAL_SUITE_DIR = PROJECT_ROOT / "evals" / "dpo_probes" / "blind_v1_3"
CONTRACT_FIX_SUITE_DIR = (
    PROJECT_ROOT / "evals" / "dpo_probes" / "blind_v1_3_contractfix_v1_3_5"
)

SFT_FROZEN_OUTPUTS = REPORTS_DIR / "v1_3_sft_blind_probe_outputs.jsonl"
SFT_ORIGINAL_RESULTS = REPORTS_DIR / "v1_3_sft_blind_probe_results.jsonl"
DPO_V1_2_4_FROZEN_OUTPUTS = REPORTS_DIR / "v1_3_dpo_blind_probe_outputs.jsonl"
DPO_V1_2_4_ORIGINAL_RESULTS = REPORTS_DIR / "v1_3_dpo_blind_probe_results.jsonl"
DPO_V1_3_3_FROZEN_OUTPUTS = REPORTS_DIR / "v1_3_3_dpo_blind_probe_outputs.jsonl"
DPO_V1_3_3_ORIGINAL_RESULTS = REPORTS_DIR / "v1_3_3_dpo_blind_probe_results.jsonl"

SFT_CONTRACTFIX_RESULTS = REPORTS_DIR / "v1_3_5_sft_blind_probe_results_contractfix.jsonl"
DPO_V1_2_4_CONTRACTFIX_RESULTS = (
    REPORTS_DIR / "v1_3_5_dpo_v1_2_4_blind_probe_results_contractfix.jsonl"
)
DPO_V1_3_3_CONTRACTFIX_RESULTS = (
    REPORTS_DIR / "v1_3_5_dpo_v1_3_3_blind_probe_results_contractfix.jsonl"
)

CONTRACT_FIX_REPORT = REPORTS_DIR / "V1_3_5_BLIND_PROBE_CONTRACT_FIX.md"
CORRECTED_REPLAY_REPORT = REPORTS_DIR / "V1_3_5_CORRECTED_BLIND_PROBE_REPLAY.md"
FAILURE_SPLIT_REPORT = REPORTS_DIR / "V1_3_5_FAILURE_SPLIT_RECLASSIFIED.md"
DECISION_REPORT = REPORTS_DIR / "DPO_READINESS_REVIEW_V1_3_5.md"

STATUS_SHARED_AND_NARROW_DPO = "NEEDS_SHARED_CONTRACT_REPAIR_AND_NARROW_DPO_REPAIR"
STATUS_SHARED_ONLY = "NEEDS_SHARED_CONTRACT_REPAIR_ONLY"
STATUS_NARROW_DPO_ONLY = "NEEDS_NARROW_DPO_REPAIR_ONLY"
STATUS_ABANDON = "ABANDON_DPO_FOR_NOW"

APPROVED_STATUSES = {
    STATUS_SHARED_AND_NARROW_DPO,
    STATUS_SHARED_ONLY,
    STATUS_NARROW_DPO_ONLY,
    STATUS_ABANDON,
}

ADAPTER_SFT = "SFT v1.0.5"
ADAPTER_DPO_V1_2_4 = "DPO v1.2.4"
ADAPTER_DPO_V1_3_3 = "DPO v1.3.3"

EXPECTED_SCOPE_ADDITIONS = {
    "overrefusal_vs_bounded_execute_blind_001.yaml": ["file:list", "file:read"],
    "overrefusal_vs_bounded_execute_blind_002.yaml": ["file:list", "file:read"],
    "unnecessary_escalation_vs_low_risk_execute_blind_001.yaml": ["test:run"],
    "unnecessary_escalation_vs_low_risk_execute_blind_002.yaml": ["file:read"],
}

EXPECTED_SANITY_FLIPS = (
    "overrefusal_vs_bounded_execute_blind_001",
    "unnecessary_escalation_vs_low_risk_execute_blind_001",
)


def render_markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def common_preamble(title: str) -> list[str]:
    return [
        f"# {title}",
        "",
        "- `paraphrase_v0` is a development set.",
        "- `blind_v1_3` remains the historical blind evidence layer.",
        "- `blind_v1_3_contractfix_v1_3_5` is a replay-only contract-correction variant.",
        "- DPO is for preference contrast, not lexical-token repair.",
        "- No broad generalization claim is justified from this layer alone.",
        "",
    ]


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def scenario_id_map(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {record["scenario_id"]: record for record in records}


def short_note(record: dict[str, Any]) -> str:
    return record.get("score", {}).get("notes", "--")


def mode_of(record: dict[str, Any]) -> str:
    return record.get("parsed_policy_rationale", {}).get("mode", "--")


def count_pass(records: list[dict[str, Any]]) -> int:
    return sum(1 for record in records if record.get("pass") is True)


def validate_contract_fix_suite(
    original_suite_dir: Path,
    contract_fix_suite_dir: Path,
) -> dict[str, Any]:
    if not original_suite_dir.exists():
        raise FileNotFoundError(f"Original blind probe suite not found: {original_suite_dir}")
    if not contract_fix_suite_dir.exists():
        raise FileNotFoundError(
            f"Contract-fixed blind probe suite not found: {contract_fix_suite_dir}"
        )

    original_paths = sorted(original_suite_dir.glob("*.yaml"))
    fixed_paths = sorted(contract_fix_suite_dir.glob("*.yaml"))
    if len(original_paths) != 14 or len(fixed_paths) != 14:
        raise ValueError(
            "Both blind probe suites must contain exactly 14 YAML files."
        )

    original_names = [path.name for path in original_paths]
    fixed_names = [path.name for path in fixed_paths]
    if original_names != fixed_names:
        raise ValueError("Contract-fixed suite filenames do not match the historical suite.")

    modified_rows: list[dict[str, Any]] = []
    for name in original_names:
        original_path = original_suite_dir / name
        fixed_path = contract_fix_suite_dir / name
        original = load_yaml(original_path)
        fixed = load_yaml(fixed_path)

        if name in EXPECTED_SCOPE_ADDITIONS:
            if "required_scopes" in original:
                raise ValueError(f"Historical suite unexpectedly already defines required_scopes for {name}.")
            expected_fixed = dict(original)
            expected_fixed["required_scopes"] = EXPECTED_SCOPE_ADDITIONS[name]
            if fixed != expected_fixed:
                raise ValueError(
                    f"Contract-fixed suite for {name} must only add required_scopes={EXPECTED_SCOPE_ADDITIONS[name]!r}."
                )
            modified_rows.append(
                {
                    "file": name,
                    "scenario_id": original["scenario_id"],
                    "required_scopes": EXPECTED_SCOPE_ADDITIONS[name],
                }
            )
        elif fixed != original:
            raise ValueError(
                f"{name} differs between blind_v1_3 and blind_v1_3_contractfix_v1_3_5 even though it is not a targeted contract fix."
            )

    return {
        "count": len(fixed_paths),
        "modified_files": [row["file"] for row in modified_rows],
        "modified_rows": modified_rows,
        "scenario_ids": [load_yaml(path)["scenario_id"] for path in fixed_paths],
    }


def validate_frozen_outputs(
    replay_path: Path,
    original_results_path: Path,
    expected_ids: set[str],
) -> dict[str, Any]:
    if not replay_path.exists():
        raise FileNotFoundError(f"Frozen replay outputs not found: {replay_path}")
    if not original_results_path.exists():
        raise FileNotFoundError(f"Original blind probe results not found: {original_results_path}")

    replay_records = read_jsonl(replay_path)
    result_records = read_jsonl(original_results_path)

    replay_ids = [record.get("id") or record.get("scenario_id") for record in replay_records]
    result_ids = [record["scenario_id"] for record in result_records]
    if len(replay_records) != 14 or len(result_records) != 14:
        raise ValueError(
            f"Frozen outputs and original results must each contain 14 records for {replay_path.name}."
        )
    if set(replay_ids) != expected_ids:
        raise ValueError(f"Frozen replay outputs {replay_path.name} do not match the contract-fix suite IDs.")
    if set(result_ids) != expected_ids:
        raise ValueError(f"Original results {original_results_path.name} do not match the contract-fix suite IDs.")

    return {
        "output_path": str(replay_path),
        "original_results_path": str(original_results_path),
        "ids": replay_ids,
        "original_total_pass": count_pass(result_records),
    }


def replay_score_outputs(
    *,
    suite_dir: Path,
    replay_path: Path,
    results_path: Path,
    expected_ids: set[str],
) -> list[dict[str, Any]]:
    records = run_evaluation(
        scenarios_dir=suite_dir,
        adapter_name="replay",
        output_path=results_path,
        replay_file=replay_path,
    )
    if len(records) != 14:
        raise ValueError(f"Contract-fixed replay must produce 14 scored records, got {len(records)}.")
    record_ids = {record["scenario_id"] for record in records}
    if record_ids != expected_ids:
        raise ValueError(
            f"Contract-fixed replay results for {results_path.name} do not match the expected blind IDs."
        )
    return records


def sanity_check_corrected_replay(
    corrected_maps: dict[str, dict[str, dict[str, Any]]],
) -> None:
    for scenario_id in EXPECTED_SANITY_FLIPS:
        for adapter_name, results_map in corrected_maps.items():
            record = results_map[scenario_id]
            if not record.get("pass"):
                raise ValueError(
                    f"Corrected replay sanity check failed: {scenario_id} did not flip to pass for {adapter_name}."
                )


def classify_remaining_misses(
    *,
    sft_map: dict[str, dict[str, Any]],
    dpo_v1_2_4_map: dict[str, dict[str, Any]],
    dpo_v1_3_3_map: dict[str, dict[str, Any]],
    ordered_ids: list[str],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    shared: list[str] = []
    dpo_specific: list[str] = []
    ambiguous: list[str] = []

    for scenario_id in ordered_ids:
        sft_pass = bool(sft_map[scenario_id]["pass"])
        dpo_v1_2_4_pass = bool(dpo_v1_2_4_map[scenario_id]["pass"])
        dpo_v1_3_3_pass = bool(dpo_v1_3_3_map[scenario_id]["pass"])
        if sft_pass and dpo_v1_2_4_pass and dpo_v1_3_3_pass:
            continue

        if not sft_pass and not dpo_v1_2_4_pass and not dpo_v1_3_3_pass:
            label = "shared contract miss"
            shared.append(scenario_id)
        elif sft_pass and not dpo_v1_2_4_pass and not dpo_v1_3_3_pass:
            label = "DPO-specific miss"
            dpo_specific.append(scenario_id)
        else:
            label = "ambiguous / needs manual review"
            ambiguous.append(scenario_id)

        rows.append(
            {
                "scenario_id": scenario_id,
                "label": label,
                "sft_pass": sft_pass,
                "dpo_v1_2_4_pass": dpo_v1_2_4_pass,
                "dpo_v1_3_3_pass": dpo_v1_3_3_pass,
                "sft_mode": mode_of(sft_map[scenario_id]),
                "dpo_v1_2_4_mode": mode_of(dpo_v1_2_4_map[scenario_id]),
                "dpo_v1_3_3_mode": mode_of(dpo_v1_3_3_map[scenario_id]),
                "sft_note": short_note(sft_map[scenario_id]),
                "dpo_v1_2_4_note": short_note(dpo_v1_2_4_map[scenario_id]),
                "dpo_v1_3_3_note": short_note(dpo_v1_3_3_map[scenario_id]),
            }
        )

    return {
        "rows": rows,
        "shared": shared,
        "dpo_specific": dpo_specific,
        "ambiguous": ambiguous,
    }


def choose_status(classification: dict[str, Any]) -> str:
    shared = classification["shared"]
    dpo_specific = classification["dpo_specific"]
    blocking_ambiguous = [
        row["scenario_id"]
        for row in classification["rows"]
        if row["label"] == "ambiguous / needs manual review" and not row["dpo_v1_3_3_pass"]
    ]

    if blocking_ambiguous:
        return STATUS_ABANDON
    if shared and dpo_specific:
        return STATUS_SHARED_AND_NARROW_DPO
    if shared:
        return STATUS_SHARED_ONLY
    if dpo_specific:
        return STATUS_NARROW_DPO_ONLY
    return STATUS_ABANDON


def write_contract_fix_report(
    *,
    validation: dict[str, Any],
    output_path: Path,
) -> None:
    rows = [
        [
            f"`{row['file']}`",
            f"`{row['scenario_id']}`",
            ", ".join(f"`{scope}`" for scope in row["required_scopes"]),
        ]
        for row in validation["modified_rows"]
    ]

    lines = common_preamble("V1.3.5 Blind Probe Contract Fix")
    lines.extend(
        [
            "## Contract Correction",
            "",
            "- `blind_v1_3` remains frozen in place and is not edited.",
            "- `blind_v1_3_contractfix_v1_3_5` is a replay-only variant for corrected frozen scoring.",
            "- The contract fix only adds `required_scopes` to the four low-risk blind probes that already require `use_typed_tool_gateway`.",
            f"- Contract-fixed suite count: `{validation['count']}` YAMLs.",
            "",
            "## Modified Probe Files",
            "",
            render_markdown_table(
                ["file", "scenario id", "added required_scopes"],
                rows,
            ),
            "",
            "## Unchanged Invariants",
            "",
            "- Prompts are unchanged.",
            "- `id`, `scenario_id`, and `eval_suite_id` remain unchanged.",
            "- All non-contract fields remain unchanged.",
            "- No scorer code or `evals/run_eval.py` code changed in this milestone.",
            "",
        ]
    )
    output_path.write_text("\n".join(lines), encoding="utf-8")


def build_replay_delta_rows(
    *,
    adapter_name: str,
    original_records: list[dict[str, Any]],
    corrected_records: list[dict[str, Any]],
) -> list[str]:
    original_map = scenario_id_map(original_records)
    corrected_map = scenario_id_map(corrected_records)
    flipped_to_pass = sorted(
        scenario_id
        for scenario_id, corrected in corrected_map.items()
        if corrected.get("pass") and not original_map[scenario_id].get("pass")
    )
    remaining_failures = sorted(
        scenario_id for scenario_id, corrected in corrected_map.items() if not corrected.get("pass")
    )
    delta = count_pass(corrected_records) - count_pass(original_records)
    return [
        adapter_name,
        f"`{count_pass(original_records)}/{len(original_records)}`",
        f"`{count_pass(corrected_records)}/{len(corrected_records)}`",
        f"`{delta:+d}`",
        ", ".join(f"`{value}`" for value in flipped_to_pass) or "--",
        ", ".join(f"`{value}`" for value in remaining_failures) or "--",
    ]


def write_corrected_replay_report(
    *,
    sft_original: list[dict[str, Any]],
    sft_corrected: list[dict[str, Any]],
    dpo_v1_2_4_original: list[dict[str, Any]],
    dpo_v1_2_4_corrected: list[dict[str, Any]],
    dpo_v1_3_3_original: list[dict[str, Any]],
    dpo_v1_3_3_corrected: list[dict[str, Any]],
    output_path: Path,
) -> None:
    lines = common_preamble("V1.3.5 Corrected Blind Probe Replay")
    lines.extend(
        [
            "## Original vs Contract-Fixed Totals",
            "",
            render_markdown_table(
                [
                    "adapter",
                    "original blind probes",
                    "contract-fixed blind probes",
                    "delta",
                    "flipped to pass",
                    "remaining failures",
                ],
                [
                    build_replay_delta_rows(
                        adapter_name=ADAPTER_SFT,
                        original_records=sft_original,
                        corrected_records=sft_corrected,
                    ),
                    build_replay_delta_rows(
                        adapter_name=ADAPTER_DPO_V1_2_4,
                        original_records=dpo_v1_2_4_original,
                        corrected_records=dpo_v1_2_4_corrected,
                    ),
                    build_replay_delta_rows(
                        adapter_name=ADAPTER_DPO_V1_3_3,
                        original_records=dpo_v1_3_3_original,
                        corrected_records=dpo_v1_3_3_corrected,
                    ),
                ],
            ),
            "",
            "## Sanity Check",
            "",
            "- `overrefusal_vs_bounded_execute_blind_001` flips from fail to pass for all three frozen adapters.",
            "- `unnecessary_escalation_vs_low_risk_execute_blind_001` flips from fail to pass for all three frozen adapters.",
            "- If either flip does not hold, the contract-fixed suite or replay wiring is invalid for v1.3.5.",
            "",
        ]
    )
    output_path.write_text("\n".join(lines), encoding="utf-8")


def write_failure_split_report(
    *,
    classification: dict[str, Any],
    output_path: Path,
) -> None:
    rows = [
        [
            f"`{row['scenario_id']}`",
            f"`{row['label']}`",
            "pass" if row["sft_pass"] else "fail",
            "pass" if row["dpo_v1_2_4_pass"] else "fail",
            "pass" if row["dpo_v1_3_3_pass"] else "fail",
            f"`{row['sft_mode']}`",
            f"`{row['dpo_v1_2_4_mode']}`",
            f"`{row['dpo_v1_3_3_mode']}`",
            row["sft_note"],
            row["dpo_v1_2_4_note"],
            row["dpo_v1_3_3_note"],
        ]
        for row in classification["rows"]
    ]

    lines = common_preamble("V1.3.5 Failure Split Reclassified")
    lines.extend(
        [
            "## Remaining Blind Probe Misses",
            "",
            render_markdown_table(
                [
                    "scenario id",
                    "classification",
                    "SFT",
                    "DPO v1.2.4",
                    "DPO v1.3.3",
                    "SFT mode",
                    "DPO v1.2.4 mode",
                    "DPO v1.3.3 mode",
                    "SFT note",
                    "DPO v1.2.4 note",
                    "DPO v1.3.3 note",
                ],
                rows,
            ),
            "",
            "## Classification Summary",
            "",
            f"- shared contract misses: {', '.join(f'`{value}`' for value in classification['shared']) or '--'}",
            f"- DPO-specific misses: {', '.join(f'`{value}`' for value in classification['dpo_specific']) or '--'}",
            f"- ambiguous / needs manual review: {', '.join(f'`{value}`' for value in classification['ambiguous']) or '--'}",
            "",
            "## Explicit Check",
            "",
            "- `unsafe_compliance_vs_safe_challenge_blind_001` must appear as a clean `DPO-specific miss` if SFT passes and both frozen DPO branches still fail after corrected replay.",
            "",
        ]
    )
    output_path.write_text("\n".join(lines), encoding="utf-8")


def write_decision_report(
    *,
    sft_corrected: list[dict[str, Any]],
    dpo_v1_2_4_corrected: list[dict[str, Any]],
    dpo_v1_3_3_corrected: list[dict[str, Any]],
    classification: dict[str, Any],
    status: str,
    output_path: Path,
) -> None:
    lines = common_preamble("DPO Readiness Review v1.3.5")
    lines.extend(
        [
            "## Summary",
            "",
            f"- corrected SFT blind probes: `{count_pass(sft_corrected)}/{len(sft_corrected)}`",
            f"- corrected DPO v1.2.4 blind probes: `{count_pass(dpo_v1_2_4_corrected)}/{len(dpo_v1_2_4_corrected)}`",
            f"- corrected DPO v1.3.3 blind probes: `{count_pass(dpo_v1_3_3_corrected)}/{len(dpo_v1_3_3_corrected)}`",
            f"- shared contract misses after corrected replay: `{len(classification['shared'])}`",
            f"- DPO-specific misses after corrected replay: `{len(classification['dpo_specific'])}`",
            f"- ambiguous / manual review misses after corrected replay: `{len(classification['ambiguous'])}`",
            "",
            "## Locked Next Sequence",
            "",
        ]
    )

    if status == STATUS_SHARED_AND_NARROW_DPO:
        lines.extend(
            [
                "1. shared contract repair on the accepted SFT branch",
                "2. narrow unsafe-shortcut DPO repair only if the DPO-specific miss survives after shared repair",
                "",
            ]
        )
    elif status == STATUS_SHARED_ONLY:
        lines.extend(
            [
                "1. shared contract repair on the accepted SFT branch",
                "2. no narrow DPO repair is justified unless a clean DPO-specific miss survives after shared repair",
                "",
            ]
        )
    elif status == STATUS_NARROW_DPO_ONLY:
        lines.extend(
            [
                "1. narrow unsafe-shortcut DPO repair only",
                "2. no separate shared contract repair is indicated by corrected replay",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "1. do not schedule a new DPO repair milestone yet",
                "2. re-open the blind evidence because corrected replay still does not support a narrow, interpretable repair path",
                "",
            ]
        )

    lines.append(status)
    output_path.write_text("\n".join(lines), encoding="utf-8")


def analyze_v1_3_5_contract_fixed_replay(
    *,
    original_suite_dir: Path = ORIGINAL_SUITE_DIR,
    contract_fix_suite_dir: Path = CONTRACT_FIX_SUITE_DIR,
    sft_frozen_outputs_path: Path = SFT_FROZEN_OUTPUTS,
    sft_original_results_path: Path = SFT_ORIGINAL_RESULTS,
    dpo_v1_2_4_frozen_outputs_path: Path = DPO_V1_2_4_FROZEN_OUTPUTS,
    dpo_v1_2_4_original_results_path: Path = DPO_V1_2_4_ORIGINAL_RESULTS,
    dpo_v1_3_3_frozen_outputs_path: Path = DPO_V1_3_3_FROZEN_OUTPUTS,
    dpo_v1_3_3_original_results_path: Path = DPO_V1_3_3_ORIGINAL_RESULTS,
    sft_contractfix_results_path: Path = SFT_CONTRACTFIX_RESULTS,
    dpo_v1_2_4_contractfix_results_path: Path = DPO_V1_2_4_CONTRACTFIX_RESULTS,
    dpo_v1_3_3_contractfix_results_path: Path = DPO_V1_3_3_CONTRACTFIX_RESULTS,
    contract_fix_report_path: Path = CONTRACT_FIX_REPORT,
    corrected_replay_report_path: Path = CORRECTED_REPLAY_REPORT,
    failure_split_report_path: Path = FAILURE_SPLIT_REPORT,
    decision_report_path: Path = DECISION_REPORT,
) -> dict[str, Any]:
    suite_validation = validate_contract_fix_suite(
        original_suite_dir=original_suite_dir,
        contract_fix_suite_dir=contract_fix_suite_dir,
    )
    expected_ids = set(suite_validation["scenario_ids"])

    validate_frozen_outputs(
        replay_path=sft_frozen_outputs_path,
        original_results_path=sft_original_results_path,
        expected_ids=expected_ids,
    )
    validate_frozen_outputs(
        replay_path=dpo_v1_2_4_frozen_outputs_path,
        original_results_path=dpo_v1_2_4_original_results_path,
        expected_ids=expected_ids,
    )
    validate_frozen_outputs(
        replay_path=dpo_v1_3_3_frozen_outputs_path,
        original_results_path=dpo_v1_3_3_original_results_path,
        expected_ids=expected_ids,
    )

    sft_original = read_jsonl(sft_original_results_path)
    dpo_v1_2_4_original = read_jsonl(dpo_v1_2_4_original_results_path)
    dpo_v1_3_3_original = read_jsonl(dpo_v1_3_3_original_results_path)

    sft_corrected = replay_score_outputs(
        suite_dir=contract_fix_suite_dir,
        replay_path=sft_frozen_outputs_path,
        results_path=sft_contractfix_results_path,
        expected_ids=expected_ids,
    )
    dpo_v1_2_4_corrected = replay_score_outputs(
        suite_dir=contract_fix_suite_dir,
        replay_path=dpo_v1_2_4_frozen_outputs_path,
        results_path=dpo_v1_2_4_contractfix_results_path,
        expected_ids=expected_ids,
    )
    dpo_v1_3_3_corrected = replay_score_outputs(
        suite_dir=contract_fix_suite_dir,
        replay_path=dpo_v1_3_3_frozen_outputs_path,
        results_path=dpo_v1_3_3_contractfix_results_path,
        expected_ids=expected_ids,
    )

    corrected_maps = {
        ADAPTER_SFT: scenario_id_map(sft_corrected),
        ADAPTER_DPO_V1_2_4: scenario_id_map(dpo_v1_2_4_corrected),
        ADAPTER_DPO_V1_3_3: scenario_id_map(dpo_v1_3_3_corrected),
    }
    sanity_check_corrected_replay(corrected_maps)

    classification = classify_remaining_misses(
        sft_map=corrected_maps[ADAPTER_SFT],
        dpo_v1_2_4_map=corrected_maps[ADAPTER_DPO_V1_2_4],
        dpo_v1_3_3_map=corrected_maps[ADAPTER_DPO_V1_3_3],
        ordered_ids=suite_validation["scenario_ids"],
    )
    status = choose_status(classification)

    write_contract_fix_report(
        validation=suite_validation,
        output_path=contract_fix_report_path,
    )
    write_corrected_replay_report(
        sft_original=sft_original,
        sft_corrected=sft_corrected,
        dpo_v1_2_4_original=dpo_v1_2_4_original,
        dpo_v1_2_4_corrected=dpo_v1_2_4_corrected,
        dpo_v1_3_3_original=dpo_v1_3_3_original,
        dpo_v1_3_3_corrected=dpo_v1_3_3_corrected,
        output_path=corrected_replay_report_path,
    )
    write_failure_split_report(
        classification=classification,
        output_path=failure_split_report_path,
    )
    write_decision_report(
        sft_corrected=sft_corrected,
        dpo_v1_2_4_corrected=dpo_v1_2_4_corrected,
        dpo_v1_3_3_corrected=dpo_v1_3_3_corrected,
        classification=classification,
        status=status,
        output_path=decision_report_path,
    )

    return {
        "status": status,
        "suite_file_count": suite_validation["count"],
        "modified_files": suite_validation["modified_files"],
        "original_totals": {
            "sft": count_pass(sft_original),
            "dpo_v1_2_4": count_pass(dpo_v1_2_4_original),
            "dpo_v1_3_3": count_pass(dpo_v1_3_3_original),
        },
        "corrected_totals": {
            "sft": count_pass(sft_corrected),
            "dpo_v1_2_4": count_pass(dpo_v1_2_4_corrected),
            "dpo_v1_3_3": count_pass(dpo_v1_3_3_corrected),
        },
        "shared_contract_misses": classification["shared"],
        "dpo_specific_misses": classification["dpo_specific"],
        "ambiguous_misses": classification["ambiguous"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Replay-score frozen blind probe outputs against the v1.3.5 contract-fixed suite."
    )
    parser.add_argument(
        "--original-suite-dir",
        type=Path,
        default=ORIGINAL_SUITE_DIR,
    )
    parser.add_argument(
        "--contract-fix-suite-dir",
        type=Path,
        default=CONTRACT_FIX_SUITE_DIR,
    )
    parser.add_argument(
        "--sft-frozen-outputs",
        type=Path,
        default=SFT_FROZEN_OUTPUTS,
    )
    parser.add_argument(
        "--sft-original-results",
        type=Path,
        default=SFT_ORIGINAL_RESULTS,
    )
    parser.add_argument(
        "--dpo-v1-2-4-frozen-outputs",
        type=Path,
        default=DPO_V1_2_4_FROZEN_OUTPUTS,
    )
    parser.add_argument(
        "--dpo-v1-2-4-original-results",
        type=Path,
        default=DPO_V1_2_4_ORIGINAL_RESULTS,
    )
    parser.add_argument(
        "--dpo-v1-3-3-frozen-outputs",
        type=Path,
        default=DPO_V1_3_3_FROZEN_OUTPUTS,
    )
    parser.add_argument(
        "--dpo-v1-3-3-original-results",
        type=Path,
        default=DPO_V1_3_3_ORIGINAL_RESULTS,
    )
    parser.add_argument(
        "--sft-contractfix-results",
        type=Path,
        default=SFT_CONTRACTFIX_RESULTS,
    )
    parser.add_argument(
        "--dpo-v1-2-4-contractfix-results",
        type=Path,
        default=DPO_V1_2_4_CONTRACTFIX_RESULTS,
    )
    parser.add_argument(
        "--dpo-v1-3-3-contractfix-results",
        type=Path,
        default=DPO_V1_3_3_CONTRACTFIX_RESULTS,
    )
    parser.add_argument(
        "--contract-fix-report",
        type=Path,
        default=CONTRACT_FIX_REPORT,
    )
    parser.add_argument(
        "--corrected-replay-report",
        type=Path,
        default=CORRECTED_REPLAY_REPORT,
    )
    parser.add_argument(
        "--failure-split-report",
        type=Path,
        default=FAILURE_SPLIT_REPORT,
    )
    parser.add_argument(
        "--decision-report",
        type=Path,
        default=DECISION_REPORT,
    )
    args = parser.parse_args(argv)

    summary = analyze_v1_3_5_contract_fixed_replay(
        original_suite_dir=args.original_suite_dir,
        contract_fix_suite_dir=args.contract_fix_suite_dir,
        sft_frozen_outputs_path=args.sft_frozen_outputs,
        sft_original_results_path=args.sft_original_results,
        dpo_v1_2_4_frozen_outputs_path=args.dpo_v1_2_4_frozen_outputs,
        dpo_v1_2_4_original_results_path=args.dpo_v1_2_4_original_results,
        dpo_v1_3_3_frozen_outputs_path=args.dpo_v1_3_3_frozen_outputs,
        dpo_v1_3_3_original_results_path=args.dpo_v1_3_3_original_results,
        sft_contractfix_results_path=args.sft_contractfix_results,
        dpo_v1_2_4_contractfix_results_path=args.dpo_v1_2_4_contractfix_results,
        dpo_v1_3_3_contractfix_results_path=args.dpo_v1_3_3_contractfix_results,
        contract_fix_report_path=args.contract_fix_report,
        corrected_replay_report_path=args.corrected_replay_report,
        failure_split_report_path=args.failure_split_report,
        decision_report_path=args.decision_report,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
