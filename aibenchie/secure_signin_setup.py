from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aibenchie.hosted_nullxoid_auth import normalize_base_path, normalize_origin
from aibenchie.hosted_nullxoid_stack import json_payload, json_route_failure, request_raw
from training.release_fabric import validate_auth_policy, validate_setup_policy


DEFAULT_PUBLIC_API = "https://api.echolabs.diy/nullxoid"
DEFAULT_ORIGIN = "https://api.echolabs.diy"
DEFAULT_BASE_PATH = "/nullxoid"

ANDROID_REQUIRED_FILES = (
    "README.md",
    "docs/PASSKEY_AUTH_ANDROID.md",
    "app/src/main/java/com/nullxoid/android/ui/auth/LoginScreen.kt",
    "app/src/main/java/com/nullxoid/android/data/api/NullXoidApi.kt",
)

WRAPPER_REQUIRED_FILES = (
    "backend/main.py",
    "backend/tests/test_auth_json_contract.py",
)

FORBIDDEN_ANDROID_TEXT = (
    "NULLBRIDGE_SERVICE_SECRET",
    "NULLBRIDGE_SERVICE_TOKEN",
    "X-NullBridge-Service-Secret",
    "access_token=",
    "password_only",
)


@dataclass(frozen=True)
class SecureSigninSetupCheck:
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
class SecureSigninSetupResult:
    ok: bool
    root: str
    android_repo: str
    wrapper_repo: str
    public_api: str
    origin: str
    base_path: str
    checks: list[SecureSigninSetupCheck]

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "root": self.root,
            "android_repo": self.android_repo,
            "wrapper_repo": self.wrapper_repo,
            "public_api": self.public_api,
            "origin": self.origin,
            "base_path": self.base_path,
            "checks": [check.as_dict() for check in self.checks],
        }


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _pass(name: str, **detail: Any) -> SecureSigninSetupCheck:
    return SecureSigninSetupCheck(name=name, ok=True, detail=detail)


def _fail(name: str, failure: str, **detail: Any) -> SecureSigninSetupCheck:
    return SecureSigninSetupCheck(name=name, ok=False, failure=failure, detail=detail)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _missing_files(repo: Path, required: tuple[str, ...]) -> list[str]:
    return [relative for relative in required if not (repo / relative).exists()]


def _contains_check(repo: Path, relative_path: str, needles: list[str]) -> SecureSigninSetupCheck:
    path = repo / relative_path
    if not path.exists():
        return _fail(f"{relative_path}:content", "missing_file", relative_path=relative_path)
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


def _no_forbidden_text(repo: Path, relative_paths: tuple[str, ...], forbidden: tuple[str, ...]) -> SecureSigninSetupCheck:
    present: list[dict[str, str]] = []
    for relative in relative_paths:
        path = repo / relative
        if not path.exists():
            continue
        text = _read_text(path)
        for needle in forbidden:
            if needle in text:
                present.append({"path": relative, "text": needle})
    if present:
        return _fail("android_auth_secrets_absent", "forbidden_text_present", present=present)
    return _pass("android_auth_secrets_absent", scanned=len(relative_paths))


def _resolve_repo(explicit: str | Path | None, candidates: list[Path], required: tuple[str, ...]) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    for candidate in candidates:
        resolved = candidate.expanduser().resolve()
        if resolved.exists() and not _missing_files(resolved, required):
            return resolved
    return candidates[0].expanduser().resolve()


def default_android_repo(root: Path | None = None) -> Path:
    actual_root = root or _repo_root()
    return _resolve_repo(
        None,
        [
            actual_root.parent / "NullXoidAndroid",
            actual_root / "NullXoidAndroid",
        ],
        ANDROID_REQUIRED_FILES,
    )


def default_wrapper_repo(root: Path | None = None) -> Path:
    actual_root = root or _repo_root()
    return _resolve_repo(
        None,
        [
            actual_root.parent / "Felnx" / "NullXoid" / ".NullXoid",
            actual_root.parent / ".NullXoid",
            actual_root.parent / "NullXoid",
            actual_root.parent / "NullXoid-live",
        ],
        WRAPPER_REQUIRED_FILES,
    )


def _policy_checks(root: Path) -> list[SecureSigninSetupCheck]:
    checks: list[SecureSigninSetupCheck] = []
    auth_path = root / ".suite" / "policies" / "auth-policy.json"
    setup_path = root / ".suite" / "policies" / "setup-policy.json"
    for name, path, validator in [
        ("auth_policy", auth_path, validate_auth_policy),
        ("setup_policy", setup_path, validate_setup_policy),
    ]:
        if not path.exists():
            checks.append(_fail(name, "missing_policy", path=str(path)))
            continue
        try:
            errors = validator(_load_json(path))
        except Exception as exc:
            checks.append(_fail(name, f"policy_error:{type(exc).__name__}", path=str(path)))
            continue
        if errors:
            checks.append(_fail(name, "policy_invalid", errors=errors, path=str(path)))
        else:
            checks.append(_pass(name, path=str(path)))
    return checks


def _android_checks(android_repo: Path) -> list[SecureSigninSetupCheck]:
    checks: list[SecureSigninSetupCheck] = []
    if not android_repo.exists():
        return [_fail("android_repo_exists", "missing_repo", android_repo=str(android_repo))]
    checks.append(_pass("android_repo_exists", android_repo=str(android_repo)))
    missing = _missing_files(android_repo, ANDROID_REQUIRED_FILES)
    if missing:
        checks.append(_fail("android_secure_signin_files", "missing_files", missing=missing))
        return checks
    checks.append(_pass("android_secure_signin_files", count=len(ANDROID_REQUIRED_FILES)))
    checks.append(
        _contains_check(
            android_repo,
            "docs/PASSKEY_AUTH_ANDROID.md",
            [
                "Credential Manager",
                "OIDC Authorization Code with PKCE",
                "Password sign-in remains a development or migration fallback only",
                "Android Keystore",
            ],
        )
    )
    checks.append(
        _contains_check(
            android_repo,
            "app/src/main/java/com/nullxoid/android/ui/auth/LoginScreen.kt",
            [
                'Modifier.testTag("login-passkey")',
                "Set up passkey sign-in",
                'Modifier.testTag("login-oidc")',
                "Set up OIDC",
                "Password fallback is for development or migration only.",
            ],
        )
    )
    checks.append(
        _contains_check(
            android_repo,
            "app/src/main/java/com/nullxoid/android/data/api/NullXoidApi.kt",
            [
                "/auth/login",
                "LoginRequest",
            ],
        )
    )
    checks.append(_no_forbidden_text(android_repo, ANDROID_REQUIRED_FILES, FORBIDDEN_ANDROID_TEXT))
    return checks


def _wrapper_checks(wrapper_repo: Path) -> list[SecureSigninSetupCheck]:
    checks: list[SecureSigninSetupCheck] = []
    if not wrapper_repo.exists():
        return [_fail("wrapper_repo_exists", "missing_repo", wrapper_repo=str(wrapper_repo))]
    checks.append(_pass("wrapper_repo_exists", wrapper_repo=str(wrapper_repo)))
    missing = _missing_files(wrapper_repo, WRAPPER_REQUIRED_FILES)
    if missing:
        checks.append(_fail("wrapper_secure_signin_files", "missing_files", missing=missing))
        return checks
    checks.append(_pass("wrapper_secure_signin_files", count=len(WRAPPER_REQUIRED_FILES)))
    checks.append(
        _contains_check(
            wrapper_repo,
            "backend/main.py",
            [
                '"auth_primary_method": "passkey"',
                '"oidc_pkce"',
                '"auth_token_storage": "http_only_secure_samesite_cookie"',
                '"auth_password_fallback": "migration_only_mfa_required"',
                '"setup_mode": "guided_ui_first"',
                '"setup_cli_required": False',
            ],
        )
    )
    checks.append(
        _contains_check(
            wrapper_repo,
            "backend/tests/test_auth_json_contract.py",
            [
                "test_health_features_advertises_passkey_guided_setup_contract",
                "auth_primary_method",
                "auth_allowed_methods",
                "setup_cli_required",
            ],
        )
    )
    return checks


def _feature_route_check(
    *,
    origin: str,
    path: str,
    host_header: str,
    timeout: int,
) -> SecureSigninSetupCheck:
    status, content_type, body = request_raw(origin, path, host_header=host_header, timeout=timeout)
    failure = json_route_failure(status, content_type, body, route_name=path.strip("/").replace("/", "_"), allowed_statuses={200})
    if failure:
        return _fail(
            f"hosted_features:{path}",
            failure,
            status=status,
            content_type=content_type,
        )
    payload = json_payload(body)
    if not isinstance(payload, dict):
        return _fail(f"hosted_features:{path}", "features_not_object", status=status, content_type=content_type)
    expected = {
        "auth_primary_method": "passkey",
        "auth_token_storage": "http_only_secure_samesite_cookie",
        "auth_password_fallback": "migration_only_mfa_required",
        "setup_mode": "guided_ui_first",
        "setup_cli_required": False,
    }
    mismatches = {
        key: {"expected": expected_value, "actual": payload.get(key)}
        for key, expected_value in expected.items()
        if payload.get(key) != expected_value
    }
    allowed = set(payload.get("auth_allowed_methods") or [])
    for method in ["passkey", "oidc_pkce"]:
        if method not in allowed:
            mismatches[f"auth_allowed_methods:{method}"] = {"expected": "present", "actual": sorted(allowed)}
    if payload.get("nullbridge_credentials_in_frontend") is not False:
        mismatches["nullbridge_credentials_in_frontend"] = {
            "expected": False,
            "actual": payload.get("nullbridge_credentials_in_frontend"),
        }
    if mismatches:
        return _fail(
            f"hosted_features:{path}",
            "features_contract_mismatch",
            status=status,
            content_type=content_type,
            mismatches=mismatches,
        )
    return _pass(f"hosted_features:{path}", status=status, content_type=content_type)


def _hosted_feature_checks(
    *,
    origin: str,
    base_path: str,
    host_header: str,
    timeout: int,
) -> list[SecureSigninSetupCheck]:
    return [
        _feature_route_check(
            origin=origin,
            path=f"{base_path}/health/features",
            host_header=host_header,
            timeout=timeout,
        )
    ]


def run_secure_signin_setup_check(
    *,
    root: str | Path | None = None,
    android_repo: str | Path | None = None,
    wrapper_repo: str | Path | None = None,
    public_api: str = DEFAULT_PUBLIC_API,
    origin: str = DEFAULT_ORIGIN,
    base_path: str = DEFAULT_BASE_PATH,
    host_header: str = "",
    timeout: int = 15,
    run_hosted_features: bool = True,
) -> SecureSigninSetupResult:
    actual_root = Path(root).resolve() if root else _repo_root()
    resolved_android = _resolve_repo(
        android_repo,
        [actual_root.parent / "NullXoidAndroid", actual_root / "NullXoidAndroid"],
        ANDROID_REQUIRED_FILES,
    )
    resolved_wrapper = _resolve_repo(
        wrapper_repo,
        [
            actual_root.parent / "Felnx" / "NullXoid" / ".NullXoid",
            actual_root.parent / ".NullXoid",
            actual_root.parent / "NullXoid",
            actual_root.parent / "NullXoid-live",
        ],
        WRAPPER_REQUIRED_FILES,
    )
    resolved_origin = normalize_origin(origin)
    resolved_base_path = normalize_base_path(base_path)
    resolved_public_api = public_api.rstrip("/")

    checks: list[SecureSigninSetupCheck] = []
    checks.extend(_policy_checks(actual_root))
    checks.extend(_android_checks(resolved_android))
    checks.extend(_wrapper_checks(resolved_wrapper))
    if resolved_public_api != f"{resolved_origin}{resolved_base_path}":
        checks.append(
            _fail(
                "public_api_consistency",
                "public_api_origin_or_base_path_mismatch",
                public_api=resolved_public_api,
                origin=resolved_origin,
                base_path=resolved_base_path,
            )
        )
    else:
        checks.append(_pass("public_api_consistency", public_api=resolved_public_api))
    if run_hosted_features:
        checks.extend(
            _hosted_feature_checks(
                origin=resolved_origin,
                base_path=resolved_base_path,
                host_header=host_header,
                timeout=timeout,
            )
        )
    else:
        checks.append(_pass("hosted_features", skipped=True))

    return SecureSigninSetupResult(
        ok=all(check.ok for check in checks),
        root=str(actual_root),
        android_repo=str(resolved_android),
        wrapper_repo=str(resolved_wrapper),
        public_api=resolved_public_api,
        origin=resolved_origin,
        base_path=resolved_base_path,
        checks=checks,
    )


def run_from_env() -> SecureSigninSetupResult:
    skip_hosted = os.environ.get("AIBENCHIE_SECURE_SIGNIN_SKIP_HOSTED", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    return run_secure_signin_setup_check(
        root=os.environ.get("AIBENCHIE_REPO") or None,
        android_repo=os.environ.get("AIBENCHIE_ANDROID_REPO")
        or os.environ.get("AIBENCHIE_COMPANION_ANDROID_REPO")
        or None,
        wrapper_repo=os.environ.get("AIBENCHIE_NULLXOID_WRAPPER_REPO") or None,
        public_api=os.environ.get("AIBENCHIE_COMPANION_PUBLIC_API", DEFAULT_PUBLIC_API),
        origin=os.environ.get("AIBENCHIE_NULLXOID_ORIGIN", DEFAULT_ORIGIN),
        base_path=os.environ.get("AIBENCHIE_NULLXOID_BASE_PATH", DEFAULT_BASE_PATH),
        host_header=os.environ.get("AIBENCHIE_NULLXOID_HOST_HEADER", ""),
        timeout=int(os.environ.get("AIBENCHIE_SECURE_SIGNIN_TIMEOUT", "15")),
        run_hosted_features=not skip_hosted,
    )
