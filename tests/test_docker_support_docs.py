from __future__ import annotations

from pathlib import Path

import aibenchie_local
from aibenchie.docker_support import run_docker_support_gate


ROOT = Path(__file__).resolve().parents[1]
SUITE_ROOT = ROOT.parent
DOCKER_DOC = ROOT / "docs" / "DOCKER_SUPPORT.md"
README = ROOT / "README.md"
SUPPORTED_DOCKER_FILES = {
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_docker_support_is_explicitly_not_supported_yet():
    docker_doc = _read(DOCKER_DOC).lower()
    aibenchie_readme = _read(README).lower()
    website_readme = _read(SUITE_ROOT / "NullXoid-live" / "README.md").lower()
    release_gates = _read(ROOT / "docs" / "echolabs" / "ECHOLABS_RELEASE_GATES.md").lower()

    for source in (docker_doc, aibenchie_readme, website_readme, release_gates):
        assert "coming soon" in source
        assert "not supported" in source or "not a supported" in source

    assert "no tracked `dockerfile`" in docker_doc
    assert "provider tokens" in docker_doc
    assert "e2ee" in docker_doc
    assert "persistent data survives container recreation" in docker_doc
    assert "status: coming soon" in docker_doc
    assert "not a supported echolabs suite deployment path yet" in docker_doc
    assert "docker-specific aibenchie gate" in docker_doc
    assert "provider tokens, service credentials, private hostnames" in docker_doc
    assert "docker support is coming soon" in aibenchie_readme
    assert "docs/docker_support.md" in aibenchie_readme


def test_known_suite_docker_entrypoints_are_not_advertised_without_gate():
    forbidden_files = [
        SUITE_ROOT / "NullXoid-live" / "Dockerfile",
        SUITE_ROOT / "NullXoid-live" / "docker-compose.yml",
        SUITE_ROOT / "NullBridge" / "Dockerfile",
        SUITE_ROOT / "NullBridge" / "docker-compose.yml",
        ROOT / "Dockerfile",
        ROOT / "docker-compose.yml",
    ]

    assert not [path for path in forbidden_files if path.exists()]


def test_tracked_docker_entrypoints_do_not_exist_before_gate_is_ready():
    tracked_docker_files = [
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*")
        if path.is_file()
        and ".git" not in path.parts
        and ".pytest_cache" not in path.parts
        and path.name in SUPPORTED_DOCKER_FILES
    ]

    assert tracked_docker_files == []


def test_docker_backlog_status_matches_guarded_boundary():
    backlog = _read(ROOT / "docs" / "SUITE_PRIORITY_BACKLOG.md")

    assert "| 9 | Docker support boundary | 210 | Guarded gate |" in backlog
    assert "explicitly not supported yet" in backlog
    assert "`--docker-support` gate" in backlog


def test_docker_support_gate_enforces_guarded_boundary():
    result = run_docker_support_gate(ROOT).as_dict()
    checks = {check["name"]: check for check in result["checks"]}

    assert result["ok"] is True
    assert result["status"] == "coming_soon"
    assert checks["status_guard"]["ok"] is True
    assert checks["not_supported_disclaimer"]["ok"] is True
    assert checks["secret_boundary"]["ok"] is True
    assert checks["acceptance_criteria"]["ok"] is True
    assert checks["no_tracked_docker_entrypoints"]["ok"] is True
    assert checks["no_known_suite_docker_entrypoints"]["ok"] is True


def test_docker_support_cli_outputs_boundary_verdict(capsys):
    exit_code = aibenchie_local.main(["--docker-support", "--json"])

    assert exit_code == 0
    assert '"status": "coming_soon"' in capsys.readouterr().out
