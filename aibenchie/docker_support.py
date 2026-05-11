from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DOCKER_SUPPORT_STATUS = "coming_soon"
DOCKER_SUPPORT_PROOF_SCHEMA = "aibenchie.docker-support-proof.v1"
DEFAULT_DOCKER_SUPPORT_PROOF = Path("configs/aibenchie_docker_support.example.json")
SUPPORTED_DOCKER_FILES = {
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
}
REQUIRED_SERVICES = {"echolabs_web", "bridgeecho", "aibenchie"}
REQUIRED_VOLUMES = {"vault", "artifacts", "logs", "aibenchie_evidence"}
REQUIRED_SECRET_PATHS = {"provider_tokens", "service_credentials", "release_signing", "e2ee_recovery"}
SECRET_KEY_PARTS = ("token", "secret", "password", "credential", "private_key", "apikey", "api_key")
SECRET_VALUE_PREFIXES = ("ghp_", "github_pat_", "gitea_", "forgejo_", "glpat-", "xoxb-", "sk-", "eyj")


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


@dataclass(frozen=True)
class DockerSupportProofResult:
    ok: bool
    proof_path: str
    status: str
    checks: list[DockerSupportCheck]

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "proof_path": self.proof_path,
            "status": self.status,
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


def _load_json(path: Path) -> tuple[dict[str, Any], str]:
    if not path.exists():
        return {}, "proof_missing"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {}, f"proof_invalid_json:{exc.lineno}"
    if not isinstance(payload, dict):
        return {}, "proof_not_object"
    return payload, ""


def _scan_secret_like_values(value: Any, path: str = "") -> list[str]:
    failures: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}" if path else key_text
            key_lower = key_text.lower()
            if key_lower == "secret_scan":
                failures.extend(_scan_secret_like_values(child, child_path))
                continue
            if key_lower.endswith("_env") or key_lower.endswith("_path") or key_lower in {"secret_paths", "runtime_secret_paths"}:
                failures.extend(_scan_secret_like_values(child, child_path))
                continue
            if any(part in key_lower for part in SECRET_KEY_PARTS):
                failures.append(f"{child_path}:secret_key_not_allowed")
                continue
            failures.extend(_scan_secret_like_values(child, child_path))
        return failures
    if isinstance(value, list):
        for index, child in enumerate(value):
            failures.extend(_scan_secret_like_values(child, f"{path}[{index}]"))
        return failures
    if isinstance(value, str):
        lower = value.strip().lower()
        if any(lower.startswith(prefix) for prefix in SECRET_VALUE_PREFIXES):
            failures.append(f"{path}:secret_value_not_allowed")
    return failures


def _is_sha256_digest(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(re.fullmatch(r"sha256:[0-9a-fA-F]{64}", text))


def _ids(items: Any) -> set[str]:
    if not isinstance(items, list):
        return set()
    return {str(item.get("id") or item.get("name") or "").strip() for item in items if isinstance(item, dict)}


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


def validate_docker_support_proof(proof_path: str | Path | None = None) -> DockerSupportProofResult:
    selected = Path(proof_path) if proof_path else DEFAULT_DOCKER_SUPPORT_PROOF
    resolved = selected.expanduser().resolve()
    payload, load_failure = _load_json(resolved)
    checks: list[DockerSupportCheck] = []

    checks.append(_check("proof_json", not load_failure, load_failure))
    checks.append(_check("schema", payload.get("schema") == DOCKER_SUPPORT_PROOF_SCHEMA, "schema_mismatch"))
    checks.append(_check("not_template", not bool(payload.get("template", False)), "template_proof_not_release_evidence"))

    secret_failures = _scan_secret_like_values(payload)
    checks.append(_check("secret_boundary", not secret_failures, ";".join(secret_failures), scanned=True))

    services = payload.get("services") if isinstance(payload.get("services"), list) else []
    service_ids = _ids(services)
    missing_services = sorted(REQUIRED_SERVICES.difference(service_ids))
    service_failures: list[str] = []
    for service in services:
        if not isinstance(service, dict):
            service_failures.append("service_not_object")
            continue
        service_id = str(service.get("id") or "").strip()
        if not _is_sha256_digest(service.get("image_digest")):
            service_failures.append(f"image_digest_invalid:{service_id or 'unknown'}")
        if not service.get("healthcheck"):
            service_failures.append(f"healthcheck_missing:{service_id or 'unknown'}")
        resources = service.get("resources") if isinstance(service.get("resources"), dict) else {}
        if not resources.get("cpu") or not resources.get("memory"):
            service_failures.append(f"resources_missing:{service_id or 'unknown'}")
    checks.append(
        _check(
            "services",
            not missing_services and not service_failures,
            ";".join([*(f"service_missing:{item}" for item in missing_services), *service_failures]),
            count=len(services),
        )
    )

    volume_ids = _ids(payload.get("persistent_volumes"))
    missing_volumes = sorted(REQUIRED_VOLUMES.difference(volume_ids))
    checks.append(_check("persistent_volumes", not missing_volumes, ";".join(f"volume_missing:{item}" for item in missing_volumes), count=len(volume_ids)))

    secret_paths = payload.get("runtime_secret_paths") if isinstance(payload.get("runtime_secret_paths"), list) else []
    missing_secret_paths = sorted(REQUIRED_SECRET_PATHS.difference({str(item).strip() for item in secret_paths}))
    checks.append(_check("runtime_secret_paths", not missing_secret_paths, ";".join(f"secret_path_missing:{item}" for item in missing_secret_paths), count=len(secret_paths)))

    network = payload.get("network") if isinstance(payload.get("network"), dict) else {}
    checks.append(
        _check(
            "network_policy",
            bool(network.get("https_routes") and network.get("local_only_services") and network.get("sse_or_websocket")),
            "network_policy_incomplete",
        )
    )

    gates = payload.get("gates") if isinstance(payload.get("gates"), dict) else {}
    checks.append(
        _check(
            "release_gates",
            str(gates.get("suite_release_gate") or "").lower() == "pass"
            and str(gates.get("docker_supported_mode_gate") or "").lower() == "pass"
            and str(gates.get("secret_scan") or "").lower() == "pass",
            "release_gates_incomplete",
        )
    )

    status = str(payload.get("status") or "").strip().lower()
    checks.append(_check("supported_status", status == "supported", f"unsupported_status:{status or 'missing'}"))

    return DockerSupportProofResult(
        ok=all(check.ok for check in checks),
        proof_path=str(resolved),
        status=status,
        checks=checks,
    )
