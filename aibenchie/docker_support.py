from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DOCKER_SUPPORT_STATUS = "coming_soon"
SUPPORTED_DOCKER_FILES = {
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
}


@dataclass(frozen=True)
class DockerSupportCheck:
    name: str
    ok: bool
    status: str
    failure: str = ""
    detail: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "ok": self.ok,
            "status": self.status,
            "failure": self.failure,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class DockerSupportResult:
    ok: bool
    status: str
    root: str
    checks: list[DockerSupportCheck]

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "root": self.root,
            "checks": [check.as_dict() for check in self.checks],
        }


def _check(name: str, ok: bool, failure: str = "", **detail: Any) -> DockerSupportCheck:
    return DockerSupportCheck(
        name=name,
        ok=ok,
        status="pass" if ok else "fail",
        failure="" if ok else failure,
        detail=detail,
    )


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").lower()


def _tracked_docker_files(root: Path) -> list[str]:
    ignored_parts = {".git", ".pytest_cache", "__pycache__"}
    return [
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
        and not (set(path.relative_to(root).parts) & ignored_parts)
        and path.name in SUPPORTED_DOCKER_FILES
    ]


def _known_suite_docker_files(root: Path) -> list[str]:
    suite_root = root.parent
    candidates = [
        suite_root / "NullXoid-live" / "Dockerfile",
        suite_root / "NullXoid-live" / "docker-compose.yml",
        suite_root / "NullBridge" / "Dockerfile",
        suite_root / "NullBridge" / "docker-compose.yml",
        root / "Dockerfile",
        root / "docker-compose.yml",
    ]
    return [str(path) for path in candidates if path.exists()]


def run_docker_support_gate(root: Path | None = None) -> DockerSupportResult:
    resolved_root = (root or Path(__file__).resolve().parents[1]).resolve()
    suite_root = resolved_root.parent
    docker_doc = _read(resolved_root / "docs" / "DOCKER_SUPPORT.md")
    readme = _read(resolved_root / "README.md")
    release_gates = _read(resolved_root / "docs" / "echolabs" / "ECHOLABS_RELEASE_GATES.md")
    website_readme = _read(suite_root / "NullXoid-live" / "README.md")

    tracked_docker_files = _tracked_docker_files(resolved_root)
    known_suite_files = _known_suite_docker_files(resolved_root)
    docs = [docker_doc, readme, release_gates, website_readme]

    checks = [
        _check("status_guard", "status: coming soon" in docker_doc, "docker_status_not_guarded"),
        _check(
            "not_supported_disclaimer",
            all("coming soon" in text and ("not supported" in text or "not a supported" in text) for text in docs),
            "docker_disclaimer_missing",
        ),
        _check(
            "secret_boundary",
            "provider tokens, service credentials, private hostnames" in docker_doc
            and "never in images or compose files" in docker_doc,
            "docker_secret_boundary_missing",
        ),
        _check(
            "acceptance_criteria",
            "persistent data survives container recreation" in docker_doc
            and "docker-specific aibenchie gate" in docker_doc
            and "release attestation for container images" in docker_doc,
            "docker_acceptance_criteria_missing",
        ),
        _check(
            "no_tracked_docker_entrypoints",
            not tracked_docker_files,
            "tracked_docker_entrypoints_present",
            files=tracked_docker_files,
        ),
        _check(
            "no_known_suite_docker_entrypoints",
            not known_suite_files,
            "suite_docker_entrypoints_present",
            files=known_suite_files,
        ),
    ]

    return DockerSupportResult(
        ok=all(check.ok for check in checks),
        status=DOCKER_SUPPORT_STATUS,
        root=str(resolved_root),
        checks=checks,
    )
