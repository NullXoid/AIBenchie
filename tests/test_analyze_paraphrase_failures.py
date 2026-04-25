from __future__ import annotations

import json

from training.analyze_paraphrase_failures import (
    TARGET_HOLDOUT_IDS,
    analyze_paraphrase_failures,
)


def write_jsonl(path, records):
    path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )


def make_result(holdout_id: str, base_scenario_id: str, prompt: str, mode: str) -> dict:
    return {
        "id": holdout_id,
        "prompt": prompt,
        "parsed_policy_rationale": {"mode": mode},
        "metadata": {"base_scenario_id": base_scenario_id},
        "score": {
            "must_include_hits": {"token": False},
            "required_behavior_hits": {"behavior": False},
            "failure_modes_checked": {"failure": False},
        },
    }


def test_analyze_paraphrase_failures_writes_only_the_target_rows(tmp_path):
    results = []
    for holdout_id in TARGET_HOLDOUT_IDS:
        base_id = holdout_id.rsplit("_holdout_", 1)[0]
        results.append(make_result(holdout_id, base_id, f"prompt for {holdout_id}", "challenge"))
    results.append(make_result("extra_holdout", "extra_base", "extra", "execute"))

    results_path = tmp_path / "results.jsonl"
    output_path = tmp_path / "analysis.md"
    write_jsonl(results_path, results)

    summary = analyze_paraphrase_failures(results_path=results_path, output_path=output_path)

    text = output_path.read_text(encoding="utf-8")
    assert summary["failure_count"] == 8
    assert sum(1 for line in text.splitlines() if line.startswith("| `") and "_holdout_" in line) == 8
    assert "extra_holdout" not in text
