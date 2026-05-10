from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUITE_ROOT = ROOT.parent


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_docker_docs_are_explicitly_coming_soon_not_supported():
    docker_doc = _read(ROOT / "docs" / "DOCKER_SUPPORT.md").lower()
    aibenchie_readme = _read(ROOT / "README.md").lower()
    website_readme = _read(SUITE_ROOT / "NullXoid-live" / "README.md").lower()
    release_gates = _read(ROOT / "docs" / "echolabs" / "ECHOLABS_RELEASE_GATES.md").lower()

    for source in (docker_doc, aibenchie_readme, website_readme, release_gates):
        assert "coming soon" in source
        assert "not supported" in source or "not a supported" in source

    assert "docker-specific aibenchie gate" in docker_doc
    assert "no tracked `dockerfile`" in docker_doc
    assert "provider tokens" in docker_doc
    assert "e2ee" in docker_doc
    assert "persistent data survives container recreation" in docker_doc


def test_docker_support_is_not_advertised_without_files():
    forbidden_files = [
        SUITE_ROOT / "NullXoid-live" / "Dockerfile",
        SUITE_ROOT / "NullXoid-live" / "docker-compose.yml",
        SUITE_ROOT / "NullBridge" / "Dockerfile",
        SUITE_ROOT / "NullBridge" / "docker-compose.yml",
        ROOT / "Dockerfile",
        ROOT / "docker-compose.yml",
    ]

    assert not [path for path in forbidden_files if path.exists()]


def test_docker_backlog_status_matches_foundation_boundary():
    backlog = _read(ROOT / "docs" / "SUITE_PRIORITY_BACKLOG.md")

    assert "| 9 | Docker support documentation | 210 | Foundation ready |" in backlog
    assert "explicitly not supported yet" in backlog
