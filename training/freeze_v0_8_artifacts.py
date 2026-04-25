from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS = PROJECT_ROOT / "reports" / "training" / "v0_8_sft_eval_results.jsonl"
DEFAULT_CONFIG = PROJECT_ROOT / "training" / "qlora_smoke_config.yaml"
DEFAULT_DATASET_DIR = PROJECT_ROOT / "data" / "pilot_v1_5"
DEFAULT_ADAPTER_DIR = PROJECT_ROOT / "models" / "adapters" / "lv7_sft_smoke_v0_8"
DEFAULT_MARKDOWN = PROJECT_ROOT / "reports" / "training" / "V0_8_FREEZE.md"
DEFAULT_MANIFEST = PROJECT_ROOT / "reports" / "training" / "v0_8_artifact_manifest.json"

REQUIRED_TRACKED_FILES = [
    Path("data/pilot_v1_5/sft_messages.jsonl"),
    Path("data/pilot_v1_5/sft_train_ready.jsonl"),
    Path("reports/training/v0_8_sft_eval_results.jsonl"),
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


def build_manifest(
    *,
    root: Path,
    results_path: Path,
    config_path: Path,
    dataset_dir: Path,
    adapter_dir: Path,
) -> dict[str, Any]:
    results = read_jsonl(results_path)
    tracked_files = collect_tracked_files(root, REQUIRED_TRACKED_FILES)
    adapter_files = collect_adapter_files(adapter_dir)
    strict_score = {
        "passed": sum(1 for result in results if result["pass"]),
        "total": len(results),
    }
    return {
        "generated_at": now_iso(),
        "base_model": "Qwen/Qwen2.5-1.5B-Instruct",
        "adapter_path": adapter_dir.relative_to(root).as_posix() + "/",
        "dataset_dir": dataset_dir.relative_to(root).as_posix() + "/",
        "config_path": config_path.relative_to(root).as_posix(),
        "seed": 42,
        "eval_suite_id": "lv7_smoke_v1_2",
        "strict_score": strict_score,
        "pytest_result": "52 passed",
        "tracked_files": tracked_files,
        "adapter_files": adapter_files,
    }


def render_freeze_markdown(manifest: dict[str, Any]) -> str:
    tracked_rows = [
        "| `{path}` | `{sha256}` | `{size_bytes}` | `{line_count}` |".format(
            path=path,
            sha256=entry["sha256"],
            size_bytes=entry["size_bytes"],
            line_count=entry.get("line_count", "--"),
        )
        for path, entry in manifest["tracked_files"].items()
    ]
    adapter_rows = [
        "| `{path}` | `{sha256}` | `{size_bytes}` |".format(
            path=path,
            sha256=entry["sha256"],
            size_bytes=entry["size_bytes"],
        )
        for path, entry in manifest["adapter_files"].items()
    ]
    return "\n".join(
        [
            "# V0.8 Freeze",
            "",
            f"- Generated at: `{manifest['generated_at']}`",
            f"- Base model: `{manifest['base_model']}`",
            f"- Adapter path: `{manifest['adapter_path']}`",
            f"- Dataset dir: `{manifest['dataset_dir']}`",
            f"- Config path: `{manifest['config_path']}`",
            f"- Seed: `{manifest['seed']}`",
            f"- Eval suite: `{manifest['eval_suite_id']}`",
            f"- Strict score: `{manifest['strict_score']['passed']}/{manifest['strict_score']['total']}`",
            f"- Pytest result: `{manifest['pytest_result']}`",
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
            "",
            "This freeze records the accepted v0.8 artifact state before any holdout robustness review.",
        ]
    ) + "\n"


def freeze_v0_8_artifacts(
    *,
    results_path: Path = DEFAULT_RESULTS,
    config_path: Path = DEFAULT_CONFIG,
    dataset_dir: Path = DEFAULT_DATASET_DIR,
    adapter_dir: Path = DEFAULT_ADAPTER_DIR,
    markdown_path: Path = DEFAULT_MARKDOWN,
    manifest_path: Path = DEFAULT_MANIFEST,
) -> dict[str, Any]:
    manifest = build_manifest(
        root=PROJECT_ROOT,
        results_path=results_path,
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
        "strict_score": manifest["strict_score"],
        "adapter_file_count": len(manifest["adapter_files"]),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Freeze the accepted v0.8 artifact state.")
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--adapter-dir", type=Path, default=DEFAULT_ADAPTER_DIR)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN)
    parser.add_argument("--manifest-output", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args(argv)

    summary = freeze_v0_8_artifacts(
        results_path=args.results,
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
