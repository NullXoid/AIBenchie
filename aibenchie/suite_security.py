from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aibenchie.generated_output_policy import run_generated_output_policy_check
from aibenchie.hosted_nullxoid_auth import normalize_base_path, normalize_origin
from aibenchie.hosted_nullxoid_ephemeral_chat import run_ephemeral_hosted_nullxoid_chat_check
from aibenchie.hosted_nullxoid_stack import run_hosted_nullxoid_stack_check
from aibenchie.local_nullbridge_runner import run_local_trust_path


DEFAULT_PUBLIC_ORIGIN = "https://api.echolabs.diy"
DEFAULT_BASE_PATH = "/nullxoid"

DEFAULT_SCAN_PATHS = (
    "README.md",
    "aibenchie",
    "configs",
    "docs",
    "requirements.txt",
    "requirements-dev.txt",
    "streamlit_app.py",
    "tests",
    "aibenchie_local.py",
)

IGNORED_SCAN_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".suite",
    ".venv",
    "__pycache__",
    "data",
    "node_modules",
    "reports",
}

MAX_SCAN_FILE_BYTES = 512 * 1024
SAFE_PLACEHOLDER_VALUES = {
    "",
    "<runtime",
    "<runtime>",
    "<runtime username>",
    "<runtime password>",
    "<optional model id>",
    "[redacted]",
    "[redacted_service_token]",
    "redacted",
    "placeholder",
    "example",
    "changeme",
}

STATIC_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("github_token", re.compile(r"\bgh[opsru]_[A-Za-z0-9_]{30,}\b")),
    ("openai_api_key", re.compile(r"\bsk-[A-Za-z0-9_-]{24,}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    (
        "jwt",
        re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    ),
)

SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"\b(?P<key>[A-Za-z0-9_]*(?:TOKEN|SECRET|API_KEY|PRIVATE_KEY|SERVICE_KEY)[A-Za-z0-9_]*)"
    r"\b\s*[:=]\s*[\"']?(?P<value>[^\"'\s#]{16,})",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SecretFinding:
    path: str
    line: int
    kind: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "line": self.line,
            "kind": self.kind,
        }


@dataclass(frozen=True)
class SecretScanResult:
    ok: bool
    root: str
    scanned_files: int
    findings: list[SecretFinding] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "root": self.root,
            "scanned_files": self.scanned_files,
            "findings": [finding.as_dict() for finding in self.findings],
        }


@dataclass(frozen=True)
class SuiteSecurityCheck:
    name: str
    ok: bool
    status: str
    severity: str
    failure: str = ""
    detail: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "ok": self.ok,
            "status": self.status,
            "severity": self.severity,
            "failure": self.failure,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class SuiteSecurityResult:
    ok: bool
    origin: str
    base_path: str
    checks: list[SuiteSecurityCheck]

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "origin": self.origin,
            "base_path": self.base_path,
            "checks": [check.as_dict() for check in self.checks],
        }


def _env_bool(source: dict[str, str], key: str, *, default: bool = False) -> bool:
    value = source.get(key, "").strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


def _repo_root(source: dict[str, str]) -> Path:
    configured = source.get("AIBENCHIE_SUITE_SECURITY_ROOT", "").strip()
    if configured:
        return Path(configured).resolve()
    generated_root = source.get("AIBENCHIE_GENERATED_ROOT", "").strip()
    if generated_root:
        return Path(generated_root).resolve()
    return Path(__file__).resolve().parents[1]


def _scan_paths(root: Path) -> list[Path]:
    files: list[Path] = []
    for item in DEFAULT_SCAN_PATHS:
        path = root / item
        if not path.exists():
            continue
        if path.is_file():
            files.append(path)
            continue
        for child in path.rglob("*"):
            if not child.is_file():
                continue
            relative_parts = set(child.relative_to(root).parts)
            if relative_parts & IGNORED_SCAN_PARTS:
                continue
            files.append(child)
    return sorted(set(files))


def _safe_value(value: str) -> bool:
    normalized = value.strip().strip("\"'").lower()
    if normalized in SAFE_PLACEHOLDER_VALUES:
        return True
    return normalized.startswith("<") or normalized.startswith("[redacted")


def _looks_like_assigned_secret(key: str, value: str) -> bool:
    if _safe_value(value):
        return False
    normalized_key = key.lower()
    normalized_value = value.strip().strip("\"'")
    if "nullbridge" in normalized_key or "service" in normalized_key:
        return len(normalized_value) >= 20
    if normalized_value.startswith(("ghp_", "gho_", "ghs_", "ghu_", "ghr_", "sk-", "xox")):
        return True
    return len(normalized_value) >= 32 and bool(re.search(r"[A-Za-z]", normalized_value)) and bool(
        re.search(r"\d", normalized_value)
    )


def scan_public_files_for_secrets(root: Path | None = None) -> SecretScanResult:
    resolved_root = (root or Path(__file__).resolve().parents[1]).resolve()
    findings: list[SecretFinding] = []
    scanned_files = 0
    for path in _scan_paths(resolved_root):
        try:
            if path.stat().st_size > MAX_SCAN_FILE_BYTES:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        scanned_files += 1
        relative = path.relative_to(resolved_root).as_posix()
        for line_number, line in enumerate(text.splitlines(), start=1):
            for kind, pattern in STATIC_SECRET_PATTERNS:
                if pattern.search(line):
                    findings.append(SecretFinding(path=relative, line=line_number, kind=kind))
            for match in SECRET_ASSIGNMENT_PATTERN.finditer(line):
                key = match.group("key")
                value = match.group("value")
                if _looks_like_assigned_secret(key, value):
                    findings.append(SecretFinding(path=relative, line=line_number, kind="secret_assignment"))
    return SecretScanResult(
        ok=not findings,
        root=str(resolved_root),
        scanned_files=scanned_files,
        findings=sorted(findings, key=lambda item: (item.path, item.line, item.kind)),
    )


def _check_from_result(name: str, ok: bool, detail: dict[str, Any], *, severity: str, failure: str = "") -> SuiteSecurityCheck:
    return SuiteSecurityCheck(
        name=name,
        ok=ok,
        status="pass" if ok else "fail",
        severity=severity,
        failure="" if ok else failure,
        detail=detail,
    )


def _skip_check(name: str, reason: str, *, severity: str = "optional") -> SuiteSecurityCheck:
    return SuiteSecurityCheck(
        name=name,
        ok=True,
        status="skip",
        severity=severity,
        failure="",
        detail={"reason": reason},
    )


def run_suite_security_check(env: dict[str, str] | None = None) -> SuiteSecurityResult:
    source = dict(os.environ if env is None else env)
    origin = normalize_origin(source.get("AIBENCHIE_NULLXOID_ORIGIN", DEFAULT_PUBLIC_ORIGIN))
    base_path = normalize_base_path(source.get("AIBENCHIE_NULLXOID_BASE_PATH", DEFAULT_BASE_PATH))
    host_header = source.get("AIBENCHIE_NULLXOID_HOST_HEADER", "")
    timeout = int(source.get("AIBENCHIE_SUITE_SECURITY_TIMEOUT", "20"))
    root = _repo_root(source)

    checks: list[SuiteSecurityCheck] = []

    hosted_stack = run_hosted_nullxoid_stack_check(
        origin=origin,
        base_path=base_path,
        host_header=host_header,
        timeout=timeout,
    )
    failed_routes = [route.failure or route.name for route in hosted_stack.routes if not route.ok]
    checks.append(
        _check_from_result(
            "hosted_nullxoid_stack",
            hosted_stack.ok,
            hosted_stack.as_dict(),
            severity="critical",
            failure=";".join(failed_routes) or "hosted_stack_failed",
        )
    )

    secret_scan = scan_public_files_for_secrets(root)
    checks.append(
        _check_from_result(
            "public_secret_exposure",
            secret_scan.ok,
            secret_scan.as_dict(),
            severity="critical",
            failure="public_secret_pattern_detected",
        )
    )

    generated_policy = run_generated_output_policy_check({**source, "AIBENCHIE_GENERATED_ROOT": str(root)})
    generated_failures = [
        *(budget.failure for budget in generated_policy.budgets if not budget.ok),
        *(item.failure for item in generated_policy.forbidden_files),
        *(item.failure for item in generated_policy.dirty_tracked_files),
    ]
    checks.append(
        _check_from_result(
            "generated_output_policy",
            generated_policy.ok,
            generated_policy.as_dict(),
            severity="required",
            failure=";".join(sorted(set(generated_failures))) or "generated_output_policy_failed",
        )
    )

    if _env_bool(source, "AIBENCHIE_SUITE_SECURITY_EPHEMERAL"):
        ephemeral = run_ephemeral_hosted_nullxoid_chat_check(
            origin=origin,
            base_path=base_path,
            helper_origin=source.get("AIBENCHIE_NULLXOID_EPHEMERAL_HELPER_ORIGIN", "http://127.0.0.1:8090"),
            model=source.get("AIBENCHIE_NULLXOID_MODEL", ""),
            prompt=source.get("AIBENCHIE_NULLXOID_PROMPT", "Reply with a short greeting for the NullXoid E2E check."),
            timeout=int(source.get("AIBENCHIE_SUITE_SECURITY_CHAT_TIMEOUT", "45")),
        )
        checks.append(
            _check_from_result(
                "ephemeral_hosted_chat",
                ephemeral.ok,
                ephemeral.as_dict(),
                severity="critical",
                failure=ephemeral.failure or "ephemeral_chat_failed",
            )
        )
    else:
        checks.append(_skip_check("ephemeral_hosted_chat", "set AIBENCHIE_SUITE_SECURITY_EPHEMERAL=1"))

    if _env_bool(source, "AIBENCHIE_SUITE_SECURITY_NULLBRIDGE"):
        try:
            trust_path = run_local_trust_path()
            trust_ok = bool(trust_path.get("ok"))
            checks.append(
                _check_from_result(
                    "local_nullbridge_trust_path",
                    trust_ok,
                    trust_path,
                    severity="critical",
                    failure="local_nullbridge_trust_path_failed",
                )
            )
        except Exception as exc:
            checks.append(
                SuiteSecurityCheck(
                    name="local_nullbridge_trust_path",
                    ok=False,
                    status="fail",
                    severity="critical",
                    failure="local_nullbridge_trust_path_error",
                    detail={"error": str(exc)},
                )
            )
    else:
        checks.append(_skip_check("local_nullbridge_trust_path", "set AIBENCHIE_SUITE_SECURITY_NULLBRIDGE=1"))

    return SuiteSecurityResult(
        ok=all(check.ok for check in checks),
        origin=origin,
        base_path=base_path,
        checks=checks,
    )


def run_from_env() -> SuiteSecurityResult:
    return run_suite_security_check()
