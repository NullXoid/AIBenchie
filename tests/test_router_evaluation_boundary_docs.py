from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_router_evaluation_boundary_docs_define_aibenchie_role():
    doc = (ROOT / "docs" / "ROUTER_EVALUATION_BOUNDARY.md").read_text(encoding="utf-8")

    assert "AIBenchie is not an intent router." in doc
    assert "benchmark, testbed, release gate, approval-status system" in doc
    assert "router-under-test" in doc
    assert "intent-router candidate" in doc
    assert "Lv-7 owns intent normalization" in doc


def test_readme_points_to_router_evaluation_boundary():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "AIBenchie is not an intent router." in readme
    assert "docs/ROUTER_EVALUATION_BOUNDARY.md" in readme
