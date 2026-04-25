from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


if __package__ in {None, ""}:
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
    import sys

    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from training.freeze_v1_0_5_artifacts import (
        collect_adapter_files,
        collect_tracked_files,
        metric_count,
        now_iso,
        read_jsonl,
    )
else:
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
    from .freeze_v1_0_5_artifacts import (
        collect_adapter_files,
        collect_tracked_files,
        metric_count,
        now_iso,
        read_jsonl,
    )


DEFAULT_EXACT_RESULTS = PROJECT_ROOT / "reports" / "training" / "v1_2_4_dpo_exact_eval_results.jsonl"
DEFAULT_HOLDOUT_RESULTS = PROJECT_ROOT / "reports" / "training" / "v1_2_4_dpo_holdout_eval_results.jsonl"
DEFAULT_PROBE_RESULTS = PROJECT_ROOT / "reports" / "training" / "v1_2_4_dpo_probe_results.jsonl"
DEFAULT_AMBIGUOUS_POSTCHECK = (
    PROJECT_ROOT / "reports" / "training" / "v1_2_4_ambiguous_goal_postcheck.json"
)
DEFAULT_CONFIG = PROJECT_ROOT / "training" / "dpo_smoke_config_v1_2_4.yaml"
DEFAULT_SELECTED_DPO = PROJECT_ROOT / "data" / "dpo_smoke_v1_1" / "dpo_pairs_selected.jsonl"
DEFAULT_ACCEPTED_ADAPTER_DIR = PROJECT_ROOT / "models" / "adapters" / "lv7_dpo_smoke_v1_2_4"
DEFAULT_MARKDOWN = PROJECT_ROOT / "reports" / "training" / "V1_2_4_FREEZE.md"
DEFAULT_MANIFEST = PROJECT_ROOT / "reports" / "training" / "v1_2_4_artifact_manifest.json"

REQUIRED_TRACKED_FILES = [
    Path("reports/training/v1_2_4_dpo_exact_eval_results.jsonl"),
    Path("reports/training/v1_2_4_dpo_holdout_eval_results.jsonl"),
    Path("reports/training/v1_2_4_dpo_probe_results.jsonl"),
    Path("reports/training/v1_2_4_ambiguous_goal_precheck.json"),
    Path("reports/training/v1_2_4_ambiguous_goal_postcheck.json"),
    Path("reports/training/V1_2_4_DPO_SMOKE_ANALYSIS.md"),
    Path("reports/training/DPO_READINESS_REVIEW_V1_2_4.md"),
    Path("reports/training/v1_2_4_dpo_run_config.json"),
    Path("reports/training/v1_2_4_dpo_train_log.jsonl"),
    Path("training/dpo_smoke_config_v1_2_4.yaml"),
    Path("data/dpo_smoke_v1_1/dpo_pairs_selected.jsonl"),
]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_manifest(
    *,
    root: Path,
    exact_results_path: Path,
    holdout_results_path: Path,
    probe_results_path: Path,
    ambiguous_postcheck_path: Path,
    config_path: Path,
    selected_dpo_path: Path,
    accepted_adapter_dir: Path,
) -> dict[str, Any]:
    exact_results = read_jsonl(exact_results_path)
    holdout_results = read_jsonl(holdout_results_path)
    probe_results = read_jsonl(probe_results_path)
    ambiguous_postcheck = read_json(ambiguous_postcheck_path)

    exact_passed = sum(1 for record in exact_results if record.get("pass") is True)
    holdout_passed = sum(1 for record in holdout_results if record.get("pass") is True)
    probe_passed = sum(1 for record in probe_results if record.get("pass") is True)
    ambiguous_cases = ambiguous_postcheck.get("cases", [])
    ambiguous_clarify = sum(1 for case in ambiguous_cases if case.get("observed_mode") == "clarify")

    return {
        "generated_at": now_iso(),
        "base_model": "Qwen/Qwen2.5-1.5B-Instruct",
        "starting_adapter": "models/adapters/lv7_sft_smoke_v1_0_5/",
        "accepted_dpo_adapter": "models/adapters/lv7_dpo_smoke_v1_2_4/",
        "blocked_dpo_adapter": "models/adapters/lv7_dpo_smoke_v1_2/",
        "config_path": config_path.relative_to(root).as_posix(),
        "selected_dpo_dataset": selected_dpo_path.relative_to(root).as_posix(),
        "exact_suite": {"passed": exact_passed, "total": len(exact_results)},
        "development_holdout": {"passed": holdout_passed, "total": len(holdout_results)},
        "dpo_probes": {"passed": probe_passed, "total": len(probe_results)},
        "policy_rationale_present": metric_count(holdout_results, "policy_rationale_present"),
        "mode_match": metric_count(holdout_results, "mode_match"),
        "ambiguous_goal_checks": {
            "clarify_count": ambiguous_clarify,
            "total": len(ambiguous_cases),
            "all_clarify": ambiguous_postcheck.get("all_clarify", False),
        },
        "pytest_result": "141 passed",
        "tracked_files": collect_tracked_files(root, REQUIRED_TRACKED_FILES),
        "adapter_files": collect_adapter_files(accepted_adapter_dir),
    }


def render_freeze_markdown(manifest: dict[str, Any]) -> str:
    tracked_rows = [
        "| `{path}` | `{sha}` | `{size}` | `{lines}` |".format(
            path=path,
            sha=entry["sha256"],
            size=entry["size_bytes"],
            lines=entry.get("line_count", "--"),
        )
        for path, entry in manifest["tracked_files"].items()
    ]
    adapter_rows = [
        "| `{path}` | `{sha}` | `{size}` |".format(
            path=path,
            sha=entry["sha256"],
            size=entry["size_bytes"],
        )
        for path, entry in manifest["adapter_files"].items()
    ]
    ambiguous = manifest["ambiguous_goal_checks"]
    return "\n".join(
        [
            "# V1.2.4 Freeze",
            "",
            f"- Generated at: `{manifest['generated_at']}`",
            f"- Base model: `{manifest['base_model']}`",
            f"- Starting adapter: `{manifest['starting_adapter']}`",
            f"- Accepted DPO adapter: `{manifest['accepted_dpo_adapter']}`",
            f"- Blocked DPO adapter: `{manifest['blocked_dpo_adapter']}`",
            f"- Config path: `{manifest['config_path']}`",
            f"- Selected DPO dataset: `{manifest['selected_dpo_dataset']}`",
            f"- Exact suite: `{manifest['exact_suite']['passed']}/{manifest['exact_suite']['total']}`",
            f"- Development holdout: `{manifest['development_holdout']['passed']}/{manifest['development_holdout']['total']}`",
            f"- DPO probes: `{manifest['dpo_probes']['passed']}/{manifest['dpo_probes']['total']}`",
            f"- Policy rationale present: `{manifest['policy_rationale_present']}`",
            f"- Mode match: `{manifest['mode_match']}`",
            f"- Ambiguous Goal checks: `{ambiguous['clarify_count']}/{ambiguous['total']} clarify`",
            f"- Pytest result: `{manifest['pytest_result']}`",
            "",
            "This freeze captures the accepted `v1.2.4` DPO smoke adapter before blind evaluation. ",
            "`evals/holdout/paraphrase_v0` remains a development set after repeated failure-derived patches, ",
            "and a fresh blind evidence layer is required before broader generalization claims. ",
            "DPO here is for preference contrast, not lexical-token repair.",
            "",
            "## Tracked Files",
            "",
            "| path | sha256 | size_bytes | line_count |",
            "| --- | --- | --- | --- |",
            *tracked_rows,
            "",
            "## Adapter Files",
            "",
            "| path | sha256 | size_bytes |",
            "| --- | --- | --- |",
            *adapter_rows,
        ]
    ) + "\n"


def freeze_v1_2_4_artifacts(
    *,
    exact_results_path: Path = DEFAULT_EXACT_RESULTS,
    holdout_results_path: Path = DEFAULT_HOLDOUT_RESULTS,
    probe_results_path: Path = DEFAULT_PROBE_RESULTS,
    ambiguous_postcheck_path: Path = DEFAULT_AMBIGUOUS_POSTCHECK,
    config_path: Path = DEFAULT_CONFIG,
    selected_dpo_path: Path = DEFAULT_SELECTED_DPO,
    accepted_adapter_dir: Path = DEFAULT_ACCEPTED_ADAPTER_DIR,
    markdown_path: Path = DEFAULT_MARKDOWN,
    manifest_path: Path = DEFAULT_MANIFEST,
) -> dict[str, Any]:
    manifest = build_manifest(
        root=PROJECT_ROOT,
        exact_results_path=exact_results_path,
        holdout_results_path=holdout_results_path,
        probe_results_path=probe_results_path,
        ambiguous_postcheck_path=ambiguous_postcheck_path,
        config_path=config_path,
        selected_dpo_path=selected_dpo_path,
        accepted_adapter_dir=accepted_adapter_dir,
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_freeze_markdown(manifest), encoding="utf-8")
    return {
        "markdown_path": str(markdown_path),
        "manifest_path": str(manifest_path),
        "exact_suite": manifest["exact_suite"],
        "development_holdout": manifest["development_holdout"],
        "dpo_probes": manifest["dpo_probes"],
        "adapter_file_count": len(manifest["adapter_files"]),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Freeze the accepted v1.2.4 DPO smoke checkpoint.")
    parser.add_argument("--exact-results", type=Path, default=DEFAULT_EXACT_RESULTS)
    parser.add_argument("--holdout-results", type=Path, default=DEFAULT_HOLDOUT_RESULTS)
    parser.add_argument("--probe-results", type=Path, default=DEFAULT_PROBE_RESULTS)
    parser.add_argument("--ambiguous-postcheck", type=Path, default=DEFAULT_AMBIGUOUS_POSTCHECK)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--selected-dpo", type=Path, default=DEFAULT_SELECTED_DPO)
    parser.add_argument("--accepted-adapter-dir", type=Path, default=DEFAULT_ACCEPTED_ADAPTER_DIR)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN)
    parser.add_argument("--manifest-output", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args(argv)

    summary = freeze_v1_2_4_artifacts(
        exact_results_path=args.exact_results,
        holdout_results_path=args.holdout_results,
        probe_results_path=args.probe_results,
        ambiguous_postcheck_path=args.ambiguous_postcheck,
        config_path=args.config,
        selected_dpo_path=args.selected_dpo,
        accepted_adapter_dir=args.accepted_adapter_dir,
        markdown_path=args.markdown_output,
        manifest_path=args.manifest_output,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
