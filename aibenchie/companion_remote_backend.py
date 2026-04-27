from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aibenchie.hosted_nullxoid_auth import normalize_base_path, normalize_origin
from aibenchie.hosted_nullxoid_stack import HostedStackResult, run_hosted_nullxoid_stack_check


DEFAULT_PUBLIC_API = "https://api.example.test/nullxoid"
DEFAULT_ORIGIN = "https://api.example.test"
DEFAULT_BASE_PATH = "/nullxoid"

REQUIRED_ANDROID_FILES = (
    "README.md",
    "app/build.gradle.kts",
    "app/src/main/java/com/nullxoid/android/data/api/BackendEndpoint.kt",
    "app/src/main/java/com/nullxoid/android/data/prefs/SettingsStore.kt",
    "app/src/test/java/com/nullxoid/android/data/api/BackendEndpointTest.kt",
)


@dataclass(frozen=True)
class CompanionRemoteBackendCheck:
    name: str
    ok: bool
    failure: str = ""
    detail: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "ok": self.ok,
            "failure": self.failure,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class CompanionRemoteBackendResult:
    ok: bool
    android_repo: str
    public_api: str
    origin: str
    base_path: str
    checks: list[CompanionRemoteBackendCheck]
    hosted_stack: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "android_repo": self.android_repo,
            "public_api": self.public_api,
            "origin": self.origin,
            "base_path": self.base_path,
            "checks": [check.as_dict() for check in self.checks],
            "hosted_stack": self.hosted_stack,
        }


def default_android_repo() -> Path:
    return Path(__file__).resolve().parents[2] / "NullXoidAndroid"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _pass(name: str, **detail: Any) -> CompanionRemoteBackendCheck:
    return CompanionRemoteBackendCheck(name=name, ok=True, detail=detail)


def _fail(name: str, failure: str, **detail: Any) -> CompanionRemoteBackendCheck:
    return CompanionRemoteBackendCheck(name=name, ok=False, failure=failure, detail=detail)


def _contains_all(text: str, needles: list[str]) -> bool:
    return all(needle in text for needle in needles)


def _file_contains(repo: Path, relative_path: str, needles: list[str]) -> CompanionRemoteBackendCheck:
    path = repo / relative_path
    if not path.exists():
        return _fail(
            f"{relative_path}:content",
            "missing_file",
            relative_path=relative_path,
            missing=needles,
        )
    text = _read_text(path)
    missing = [needle for needle in needles if needle not in text]
    if missing:
        return _fail(
            f"{relative_path}:content",
            "missing_required_text",
            relative_path=relative_path,
            missing=missing,
        )
    return _pass(f"{relative_path}:content", relative_path=relative_path)


def _hosted_stack_check(
    *,
    origin: str,
    base_path: str,
    host_header: str,
    timeout: int,
) -> tuple[CompanionRemoteBackendCheck, dict[str, Any]]:
    result: HostedStackResult = run_hosted_nullxoid_stack_check(
        origin=origin,
        base_path=base_path,
        host_header=host_header,
        timeout=timeout,
    )
    result_dict = result.as_dict()
    failures = {
        route["name"]: route["failure"]
        for route in result_dict.get("routes", [])
        if not route.get("ok")
    }
    if not result.ok:
        return (
            _fail(
                "hosted_api_stack_contract",
                "hosted_stack_failed",
                origin=origin,
                base_path=base_path,
                failures=failures,
            ),
            result_dict,
        )
    return _pass("hosted_api_stack_contract", origin=origin, base_path=base_path), result_dict


def run_companion_remote_backend_check(
    *,
    android_repo: str | Path | None = None,
    public_api: str = DEFAULT_PUBLIC_API,
    origin: str = DEFAULT_ORIGIN,
    base_path: str = DEFAULT_BASE_PATH,
    host_header: str = "",
    timeout: int = 15,
    run_hosted_stack: bool = True,
) -> CompanionRemoteBackendResult:
    repo = Path(android_repo) if android_repo is not None else default_android_repo()
    repo = repo.resolve()
    resolved_public_api = public_api.rstrip("/")
    resolved_origin = normalize_origin(origin)
    resolved_base_path = normalize_base_path(base_path)

    checks: list[CompanionRemoteBackendCheck] = []
    hosted_stack: dict[str, Any] = {}

    if not repo.exists():
        checks.append(_fail("android_repo_exists", "missing_repo", android_repo=str(repo)))
        return CompanionRemoteBackendResult(
            ok=False,
            android_repo=str(repo),
            public_api=resolved_public_api,
            origin=resolved_origin,
            base_path=resolved_base_path,
            checks=checks,
            hosted_stack=hosted_stack,
        )

    checks.append(_pass("android_repo_exists", android_repo=str(repo)))

    missing_files = [relative for relative in REQUIRED_ANDROID_FILES if not (repo / relative).exists()]
    if missing_files:
        checks.append(_fail("android_contract_files", "missing_files", missing_files=missing_files))
    else:
        checks.append(_pass("android_contract_files", count=len(REQUIRED_ANDROID_FILES)))

    checks.append(
        _file_contains(
            repo,
            "README.md",
            [
                "Hosted API",
                resolved_public_api,
                "passkeys",
            ],
        )
    )
    checks.append(
        _file_contains(
            repo,
            "app/build.gradle.kts",
            [
                "NULLXOID_PUBLIC_BACKEND_URL",
                "PUBLIC_BACKEND_URL",
                resolved_public_api,
            ],
        )
    )
    checks.append(
        _file_contains(
            repo,
            "app/src/main/java/com/nullxoid/android/data/api/BackendEndpoint.kt",
            [
                "PUBLIC_ECHOLABS_URL",
                resolved_public_api,
                "https://",
            ],
        )
    )
    checks.append(
        _file_contains(
            repo,
            "app/src/main/java/com/nullxoid/android/data/prefs/SettingsStore.kt",
            [
                "PUBLIC_BACKEND_URL",
                "BackendEndpoint.PUBLIC_ECHOLABS_URL",
            ],
        )
    )
    checks.append(
        _file_contains(
            repo,
            "app/src/test/java/com/nullxoid/android/data/api/BackendEndpointTest.kt",
            [
                resolved_public_api,
                "/auth/login",
                resolved_public_api.removeprefix("https://").removeprefix("http://"),
            ],
        )
    )

    if run_hosted_stack:
        stack_check, hosted_stack = _hosted_stack_check(
            origin=resolved_origin,
            base_path=resolved_base_path,
            host_header=host_header,
            timeout=timeout,
        )
        checks.append(stack_check)
    else:
        checks.append(_pass("hosted_api_stack_contract", skipped=True))

    return CompanionRemoteBackendResult(
        ok=all(check.ok for check in checks),
        android_repo=str(repo),
        public_api=resolved_public_api,
        origin=resolved_origin,
        base_path=resolved_base_path,
        checks=checks,
        hosted_stack=hosted_stack,
    )


def run_from_env() -> CompanionRemoteBackendResult:
    skip_hosted_stack = os.environ.get("AIBENCHIE_COMPANION_SKIP_HOSTED_STACK", "").lower() in {
        "1",
        "true",
        "yes",
    }
    return run_companion_remote_backend_check(
        android_repo=os.environ.get("AIBENCHIE_COMPANION_ANDROID_REPO") or default_android_repo(),
        public_api=os.environ.get("AIBENCHIE_COMPANION_PUBLIC_API", DEFAULT_PUBLIC_API),
        origin=os.environ.get("AIBENCHIE_NULLXOID_ORIGIN", DEFAULT_ORIGIN),
        base_path=os.environ.get("AIBENCHIE_NULLXOID_BASE_PATH", DEFAULT_BASE_PATH),
        host_header=os.environ.get("AIBENCHIE_NULLXOID_HOST_HEADER", ""),
        timeout=int(os.environ.get("AIBENCHIE_COMPANION_TIMEOUT", "15")),
        run_hosted_stack=not skip_hosted_stack,
    )
