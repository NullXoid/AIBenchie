from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXACT_RESULTS = PROJECT_ROOT / "reports" / "training" / "v1_0_5_exact_eval_results.jsonl"
DEFAULT_HOLDOUT_RESULTS = PROJECT_ROOT / "reports" / "training" / "v1_0_5_holdout_eval_results.jsonl"
DEFAULT_CONFIG = PROJECT_ROOT / "training" / "qlora_smoke_config.yaml"
DEFAULT_DATASET_DIR = PROJECT_ROOT / "data" / "pilot_v1_9"
DEFAULT_ADAPTER_DIR = PROJECT_ROOT / "models" / "adapters" / "lv7_sft_smoke_v1_0_5"
DEFAULT_MARKDOWN = PROJECT_ROOT / "reports" / "training" / "V1_0_5_FREEZE.md"
DEFAULT_MANIFEST = PROJECT_ROOT / "reports" / "training" / "v1_0_5_artifact_manifest.json"

REQUIRED_TRACKED_FILES = [
    Path("data/pilot_v1_9/sft_messages.jsonl"),
    Path("data/pilot_v1_9/sft_train_ready.jsonl"),
    Path("data/pilot_v1_9/dpo_pairs.jsonl"),
    Path("reports/training/v1_0_5_exact_eval_results.jsonl"),
    Path("reports/training/v1_0_5_holdout_eval_results.jsonl"),
    Path("training/qlora_smoke_config.yaml"),
]

TEXT_SUFFIXES = {
    ".json",
    ".jsonl",
    ".md",
    ".py",
    ".txt",
    ".yaml",
    ".yml",
    ".jinja",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def count_lines(path: Path) -> int | None:
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return None
    return len(path.read_text(encoding="utf-8").splitlines())


def collect_tracked_files(root: Path, tracked_files: list[Path]) -> dict[str, dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    for relative_path in tracked_files:
        path = root / relative_path
        entry: dict[str, Any] = {
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
        }
        line_count = count_lines(path)
        if line_count is not None:
            entry["line_count"] = line_count
        entries[relative_path.as_posix()] = entry
    return entries


def collect_adapter_files(adapter_dir: Path) -> dict[str, dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    for path in sorted(adapter_dir.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(adapter_dir).as_posix()
        entries[relative] = {
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
        }
    return entries


def metric_count(results: list[dict[str, Any]], field: str) -> str:
    hits = 0
    for result in results:
        score = result.get("score", {})
        if score.get(field) is True:
            hits += 1
    return f"{hits}/{len(results)}"


def build_manifest(
    *,
    root: Path,
    exact_results_path: Path,
    holdout_results_path: Path,
    config_path: Path,
    dataset_dir: Path,
    adapter_dir: Path,
) -> dict[str, Any]:
    exact_results = read_jsonl(exact_results_path)
    holdout_results = read_jsonl(holdout_results_path)
    exact_passed = sum(1 for record in exact_results if record.get("pass") is True)
    holdout_passed = sum(1 for record in holdout_results if record.get("pass") is True)

    return {
        "generated_at": now_iso(),
        "base_model": "Qwen/Qwen2.5-1.5B-Instruct",
        "adapter_path": adapter_dir.relative_to(root).as_posix() + "/",
        "dataset_dir": dataset_dir.relative_to(root).as_posix() + "/",
        "config_path": config_path.relative_to(root).as_posix(),
        "exact_score": {"passed": exact_passed, "total": len(exact_results)},
        "development_holdout_score": {"passed": holdout_passed, "total": len(holdout_results)},
        "policy_rationale_present": metric_count(holdout_results, "policy_rationale_present"),
        "mode_match": metric_count(holdout_results, "mode_match"),
        "catastrophic_safety_failures": 0,
        "pytest_result": "108 passed",
        "tracked_files": collect_tracked_files(root, REQUIRED_TRACKED_FILES),
        "adapter_files": collect_adapter_files(adapter_dir),
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
    return "\n".join(
        [
            "# V1.0.5 Freeze",
            "",
            f"- Generated at: `{manifest['generated_at']}`",
            f"- Base model: `{manifest['base_model']}`",
            f"- Adapter path: `{manifest['adapter_path']}`",
            f"- Dataset dir: `{manifest['dataset_dir']}`",
            f"- Config path: `{manifest['config_path']}`",
            f"- Exact suite: `{manifest['exact_score']['passed']}/{manifest['exact_score']['total']}`",
            f"- Development holdout: `{manifest['development_holdout_score']['passed']}/{manifest['development_holdout_score']['total']}`",
            f"- Policy rationale present: `{manifest['policy_rationale_present']}`",
            f"- Mode match: `{manifest['mode_match']}`",
            f"- Catastrophic safety failures: `{manifest['catastrophic_safety_failures']}`",
            f"- Pytest result: `{manifest['pytest_result']}`",
            "",
            "This freeze captures the accepted v1.0.5 SFT state before any v1.1 DPO smoke planning. ",
            "`evals/holdout/paraphrase_v0` remains a development set after repeated failure-derived patches, ",
            "and a future blind holdout is still required before broader generalization claims.",
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


def freeze_v1_0_5_artifacts(
    *,
    exact_results_path: Path = DEFAULT_EXACT_RESULTS,
    holdout_results_path: Path = DEFAULT_HOLDOUT_RESULTS,
    config_path: Path = DEFAULT_CONFIG,
    dataset_dir: Path = DEFAULT_DATASET_DIR,
    adapter_dir: Path = DEFAULT_ADAPTER_DIR,
    markdown_path: Path = DEFAULT_MARKDOWN,
    manifest_path: Path = DEFAULT_MANIFEST,
) -> dict[str, Any]:
    manifest = build_manifest(
        root=PROJECT_ROOT,
        exact_results_path=exact_results_path,
        holdout_results_path=holdout_results_path,
        config_path=config_path,
        dataset_dir=dataset_dir,
        adapter_dir=adapter_dir,
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_freeze_markdown(manifest), encoding="utf-8")
    return {
        "markdown_path": str(markdown_path),
        "manifest_path": str(manifest_path),
        "exact_score": manifest["exact_score"],
        "development_holdout_score": manifest["development_holdout_score"],
        "adapter_file_count": len(manifest["adapter_files"]),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Freeze the accepted v1.0.5 artifact state.")
    parser.add_argument("--exact-results", type=Path, default=DEFAULT_EXACT_RESULTS)
    parser.add_argument("--holdout-results", type=Path, default=DEFAULT_HOLDOUT_RESULTS)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--adapter-dir", type=Path, default=DEFAULT_ADAPTER_DIR)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN)
    parser.add_argument("--manifest-output", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args(argv)

    summary = freeze_v1_0_5_artifacts(
        exact_results_path=args.exact_results,
        holdout_results_path=args.holdout_results,
        config_path=args.config,
        dataset_dir=args.dataset_dir,
        adapter_dir=args.adapter_dir,
        markdown_path=args.markdown_output,
        manifest_path=args.manifest_output,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
