from __future__ import annotations

from tests.conftest import ROOT


REPORTS_DIR = ROOT / "reports" / "training"


def test_v1_2_1_dependency_enablement_report_exists():
    report = REPORTS_DIR / "V1_2_1_DPO_DEPENDENCY_ENABLEMENT.md"
    assert report.exists(), f"Missing v1.2.1 dependency report: {report}"


def test_v1_2_1_dependency_enablement_report_records_before_after_and_preflight():
    text = (REPORTS_DIR / "V1_2_1_DPO_DEPENDENCY_ENABLEMENT.md").read_text(encoding="utf-8")

    assert "Active WSL venv: `~/.venvs/lv7-sft`" in text
    assert "final dry-run line: `Would install trl-1.2.0`" in text
    assert "`trl`: `missing`" in text
    assert "`trl`: `1.2.0`" in text
    assert "preflight status: `DPO_PREFLIGHT_READY`" in text
    assert "No DPO training was run." in text
    assert "No `train`, `eval_adapter`, or `full` execution was run." in text


def test_v1_2_1_preflight_report_is_now_ready():
    preflight = (REPORTS_DIR / "V1_2_DPO_PREFLIGHT.md").read_text(encoding="utf-8")

    assert "Preflight status: `DPO_PREFLIGHT_READY`" in preflight
    assert "`trl` available: `True`" in preflight
    assert "Selected pair count: `28`" in preflight
