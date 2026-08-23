from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from aibenchie.hosted_nullxoid_auth import normalize_base_path, normalize_origin
from aibenchie.hosted_nullxoid_stack import json_payload, json_route_failure, request_raw
from training.release_fabric import validate_auth_policy, validate_setup_policy


DEFAULT_PUBLIC_API = "https://api.elabs.test/nullxoid"
DEFAULT_ORIGIN = "https://api.elabs.test"
DEFAULT_BASE_PATH = "/nullxoid"
ANDROID_PACKAGE_NAME = "com.nullxoid.android"
ANDROID_ASSETLINKS_RELATION = "delegate_permission/common.get_login_creds"
ANDROID_ASSETLINKS_PATH = "/.well-known/assetlinks.json"
ANDROID_SHA256_FINGERPRINT = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2}){31}$", re.IGNORECASE)

ANDROID_REQUIRED_FILES = (
    "README.md",
    "docs/PASSKEY_AUTH_ANDROID.md",
    "app/build.gradle.kts",
    "app/src/main/AndroidManifest.xml",
    "app/src/main/java/com/nullxoid/android/MainActivity.kt",
    "app/src/main/java/com/nullxoid/android/ui/NullXoidNavHost.kt",
    "app/src/main/java/com/nullxoid/android/ui/NullXoidViewModel.kt",
    "app/src/main/java/com/nullxoid/android/ui/auth/LoginScreen.kt",
    "app/src/main/java/com/nullxoid/android/ui/settings/SettingsScreen.kt",
    "app/src/main/java/com/nullxoid/android/data/auth/NativeAuthCoordinator.kt",
    "app/src/main/java/com/nullxoid/android/data/auth/Pkce.kt",
    "app/src/main/java/com/nullxoid/android/data/api/NullXoidApi.kt",
    "app/src/main/java/com/nullxoid/android/data/repo/NullXoidRepository.kt",
    "app/src/main/java/com/nullxoid/android/data/model/Models.kt",
    "scripts/generate_assetlinks.py",
    "app/src/test/java/com/nullxoid/android/data/auth/PkceTest.kt",
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
                "/auth/passkey/register/complete",
                "Digital Asset Links",
                ".well-known/assetlinks.json",
                "delegate_permission/common.get_login_creds",
                "release signing SHA-256",
                "scripts/generate_assetlinks.py",
            ],
        )
    )
    checks.append(
        _contains_check(
            android_repo,
            "scripts/generate_assetlinks.py",
            [
                "delegate_permission/common.get_login_creds",
                "com.nullxoid.android",
                "apksigner",
                "sha256_cert_fingerprints",
            ],
        )
    )
    checks.append(
        _contains_check(
            android_repo,
            "app/src/main/java/com/nullxoid/android/ui/auth/LoginScreen.kt",
            [
                'Modifier.testTag("login-passkey")',
                "Use existing passkey",
                'Modifier.testTag("login-oidc")',
                "Continue with OIDC",
                "Password fallback is for development or migration only.",
            ],
        )
    )
    checks.append(
        _contains_check(
            android_repo,
            "app/build.gradle.kts",
            [
                "androidx.credentials:credentials",
                "androidx.credentials:credentials-play-services-auth",
            ],
        )
    )
    checks.append(
        _contains_check(
            android_repo,
            "app/src/main/AndroidManifest.xml",
            [
                "android.intent.category.BROWSABLE",
                'android:scheme="nullxoid"',
                'android:host="auth"',
                'android:path="/oidc/callback"',
            ],
        )
    )
    checks.append(
        _contains_check(
            android_repo,
            "app/src/main/java/com/nullxoid/android/data/auth/NativeAuthCoordinator.kt",
            [
                "CredentialManager",
                "CreatePublicKeyCredentialRequest",
                "CreatePublicKeyCredentialResponse",
                "GetPublicKeyCredentialOption",
                "PublicKeyCredential",
                "authenticationResponseJson",
                "registrationResponseJson",
                "registerPasskey",
                "codeChallenge",
                "codeVerifier",
            ],
        )
    )
    checks.append(
        _contains_check(
            android_repo,
            "app/src/main/java/com/nullxoid/android/data/auth/Pkce.kt",
            [
                "CHALLENGE_METHOD = \"S256\"",
                "MessageDigest.getInstance(\"SHA-256\")",
                "Base64.getUrlEncoder().withoutPadding()",
            ],
        )
    )
    checks.append(
        _contains_check(
            android_repo,
            "app/src/main/java/com/nullxoid/android/data/api/NullXoidApi.kt",
            [
                "/auth/login",
                "/auth/passkey/options",
                "/auth/passkey/complete",
                "/auth/passkey/credentials",
                "/auth/passkey/register/options",
                "/auth/passkey/register/complete",
                "/auth/oidc/start",
                "/auth/oidc/complete",
                "LoginRequest",
            ],
        )
    )
    checks.append(
        _contains_check(
            android_repo,
            "app/src/main/java/com/nullxoid/android/ui/NullXoidViewModel.kt",
            [
                "registerPasskey",
                "refreshPasskeys",
                "revokePasskey",
                "loginWithPasskey",
                "startOidcSignIn",
                "completeOidcSignIn",
                "nullxoid://auth/oidc/callback",
                "OIDC state mismatch",
            ],
        )
    )
    checks.append(
        _contains_check(
            android_repo,
            "app/src/main/java/com/nullxoid/android/ui/NullXoidNavHost.kt",
            [
                "vm.loginWithPasskey(context)",
                "vm.registerPasskey(context)",
                "onRefreshPasskeys",
                "vm::startOidcSignIn",
                "vm.completeOidcSignIn",
            ],
        )
    )
    checks.append(
        _contains_check(
            android_repo,
            "app/src/main/java/com/nullxoid/android/ui/settings/SettingsScreen.kt",
            [
                'Modifier.testTag("settings-passkey-add")',
                'Modifier.testTag("settings-passkey-remove")',
                "Add passkey",
                "Security",
                "onRefreshPasskeys",
                "onRevokePasskey",
            ],
        )
    )
    checks.append(
        _contains_check(
            android_repo,
            "app/src/main/java/com/nullxoid/android/data/repo/NullXoidRepository.kt",
            [
                "registerPasskey",
                "passkeyCredentials",
                "revokePasskey",
            ],
        )
    )
    checks.append(
        _contains_check(
            android_repo,
            "app/src/main/java/com/nullxoid/android/data/model/Models.kt",
            [
                "PasskeyCredentialsResponse",
                "PasskeyCredentialRecord",
                "PasskeyProviderStatus",
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
                '"auth_native_ceremony_endpoints": True',
                '"/auth/passkey/options"',
                '"/auth/passkey/complete"',
                '"/auth/passkey/credentials"',
                '"/auth/passkey/register/options"',
                '"/auth/passkey/register/complete"',
                '"/auth/oidc/start"',
                '"/auth/oidc/complete"',
                '"auth_token_storage": "http_only_secure_samesite_cookie"',
                '"auth_password_fallback": "migration_only_mfa_required"',
                '"setup_mode": "guided_ui_first"',
                '"setup_cli_required": False',
                '"request_json"',
                '"public_key"',
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
                "auth_native_ceremony_endpoints",
                "setup_cli_required",
                "test_native_auth_ceremony_endpoints_fail_json_until_provider_configured",
                "test_passkey_complete_verifies_assertion_and_sets_session",
                "test_passkey_registration_stores_verified_public_key",
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
        "auth_native_ceremony_endpoints": True,
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
    for key in [
        "auth_passkey_provider_configured",
        "auth_oidc_provider_configured",
        "auth_passkey_login_ready",
        "auth_passkey_registration_enabled",
        "auth_oidc_login_ready",
        "auth_oidc_start_ready",
    ]:
        if not isinstance(payload.get(key), bool):
            mismatches[key] = {"expected": "boolean", "actual": payload.get(key)}
    if payload.get("nullbridge_credentials_in_frontend") is not False:
        mismatches["nullbridge_credentials_in_frontend"] = {
            "expected": False,
            "actual": payload.get("nullbridge_credentials_in_frontend"),
        }
    provider_status_text = json.dumps(payload.get("auth_provider_status") or {}).lower()
    for forbidden in ["client_secret", "private_key", "password"]:
        if forbidden in provider_status_text:
            mismatches[f"auth_provider_status:{forbidden}"] = {"expected": "absent", "actual": "present"}
    if mismatches:
        return _fail(
            f"hosted_features:{path}",
            "features_contract_mismatch",
            status=status,
            content_type=content_type,
            mismatches=mismatches,
        )
    provider_status = payload.get("auth_provider_status") if isinstance(payload.get("auth_provider_status"), dict) else {}
    passkey_status = provider_status.get("passkey") if isinstance(provider_status.get("passkey"), dict) else {}
    return _pass(
        f"hosted_features:{path}",
        status=status,
        content_type=content_type,
        auth_passkey_provider_configured=payload.get("auth_passkey_provider_configured"),
        auth_passkey_registration_enabled=payload.get("auth_passkey_registration_enabled"),
        passkey_rp_id=passkey_status.get("rp_id"),
        passkey_origin=passkey_status.get("origin"),
    )


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


def _relation_values(statement: dict[str, Any]) -> list[str]:
    relation = statement.get("relation")
    if isinstance(relation, str):
        return [relation]
    if isinstance(relation, list):
        return [value for value in relation if isinstance(value, str)]
    return []


def _valid_assetlinks_statement(payload: Any) -> tuple[bool, str, dict[str, Any]]:
    if not isinstance(payload, list):
        return False, "assetlinks_not_list", {}
    package_seen = False
    relation_seen = False
    for statement in payload:
        if not isinstance(statement, dict):
            continue
        target = statement.get("target")
        if not isinstance(target, dict):
            continue
        if target.get("namespace") != "android_app":
            continue
        if target.get("package_name") != ANDROID_PACKAGE_NAME:
            continue
        package_seen = True
        relations = _relation_values(statement)
        if ANDROID_ASSETLINKS_RELATION not in relations:
            continue
        relation_seen = True
        fingerprints = target.get("sha256_cert_fingerprints")
        if not isinstance(fingerprints, list) or not fingerprints:
            return False, "assetlinks_missing_fingerprints", {"package_name": ANDROID_PACKAGE_NAME}
        invalid = [
            value
            for value in fingerprints
            if not isinstance(value, str) or not ANDROID_SHA256_FINGERPRINT.fullmatch(value.strip())
        ]
        if invalid:
            return False, "assetlinks_invalid_fingerprints", {"invalid_count": len(invalid)}
        return True, "", {"package_name": ANDROID_PACKAGE_NAME, "fingerprint_count": len(fingerprints)}
    if package_seen and not relation_seen:
        return False, "assetlinks_missing_get_login_creds_relation", {"package_name": ANDROID_PACKAGE_NAME}
    return False, "assetlinks_missing_android_package", {"package_name": ANDROID_PACKAGE_NAME}


def _assetlinks_origin_from_feature(feature_check: SecureSigninSetupCheck, default_origin: str) -> tuple[str, str]:
    passkey_origin = feature_check.detail.get("passkey_origin")
    rp_id = feature_check.detail.get("passkey_rp_id")
    if isinstance(passkey_origin, str) and passkey_origin.strip():
        parsed = urlparse(passkey_origin.strip())
        if parsed.scheme == "https" and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}", str(rp_id or parsed.netloc)
    if isinstance(rp_id, str) and rp_id.strip():
        return f"https://{rp_id.strip()}", rp_id.strip()
    return default_origin, ""


def _hosted_android_assetlinks_check(
    *,
    feature_check: SecureSigninSetupCheck,
    origin: str,
    timeout: int,
) -> SecureSigninSetupCheck:
    name = "hosted_android_assetlinks"
    if not feature_check.ok:
        return _pass(name, skipped=True, reason="feature_contract_failed")
    if feature_check.detail.get("auth_passkey_provider_configured") is not True:
        return _pass(
            name,
            skipped=True,
            reason="passkey_provider_not_configured",
            physical_mobile_test_required=False,
        )
    passkey_rp_id = feature_check.detail.get("passkey_rp_id")
    if not isinstance(passkey_rp_id, str) or not passkey_rp_id.strip():
        return _fail(name, "passkey_rp_id_missing")
    passkey_origin = feature_check.detail.get("passkey_origin")
    if isinstance(passkey_origin, str) and passkey_origin.strip():
        parsed_origin = urlparse(passkey_origin.strip())
        if parsed_origin.scheme != "https" or not parsed_origin.netloc:
            return _fail(name, "passkey_origin_not_https", passkey_origin=passkey_origin, rp_id=passkey_rp_id)
    assetlinks_origin, rp_id = _assetlinks_origin_from_feature(feature_check, origin)
    if not assetlinks_origin.startswith("https://"):
        return _fail(name, "assetlinks_origin_not_https", assetlinks_origin=assetlinks_origin, rp_id=rp_id)
    status, content_type, body = request_raw(
        assetlinks_origin,
        ANDROID_ASSETLINKS_PATH,
        timeout=timeout,
    )
    failure = json_route_failure(
        status,
        content_type,
        body,
        route_name="android_assetlinks",
        allowed_statuses={200},
    )
    if failure:
        return _fail(
            name,
            failure,
            status=status,
            content_type=content_type,
            assetlinks_origin=assetlinks_origin,
            path=ANDROID_ASSETLINKS_PATH,
            rp_id=rp_id,
        )
    payload = json_payload(body)
    ok, assetlinks_failure, detail = _valid_assetlinks_statement(payload)
    if not ok:
        return _fail(
            name,
            assetlinks_failure,
            status=status,
            content_type=content_type,
            assetlinks_origin=assetlinks_origin,
            path=ANDROID_ASSETLINKS_PATH,
            rp_id=rp_id,
            **detail,
        )
    return _pass(
        name,
        status=status,
        content_type=content_type,
        assetlinks_origin=assetlinks_origin,
        path=ANDROID_ASSETLINKS_PATH,
        rp_id=rp_id,
        relation=ANDROID_ASSETLINKS_RELATION,
        physical_mobile_test_required=True,
        **detail,
    )


def _auth_ceremony_route_check(
    *,
    origin: str,
    path: str,
    host_header: str,
    timeout: int,
    method: str = "GET",
    payload: dict[str, object] | None = None,
) -> SecureSigninSetupCheck:
    status, content_type, body = request_raw(
        origin,
        path,
        host_header=host_header,
        method=method,
        payload=payload,
        timeout=timeout,
    )
    failure = json_route_failure(
        status,
        content_type,
        body,
        route_name=path.strip("/").replace("/", "_"),
        allowed_statuses={200, 501},
    )
    name = f"hosted_auth_ceremony:{path}"
    if failure:
        return _fail(name, failure, status=status, content_type=content_type)
    payload_json = json_payload(body)
    if not isinstance(payload_json, dict):
        return _fail(name, "auth_ceremony_payload_not_object", status=status, content_type=content_type)
    if status == 501:
        detail = payload_json.get("detail")
        if not isinstance(detail, dict) or detail.get("setup_required") is not True:
            return _fail(name, "auth_ceremony_501_without_setup_contract", status=status, content_type=content_type)
        return _pass(name, status=status, content_type=content_type, configured=False)
    if path.endswith("/auth/passkey/options"):
        public_key = payload_json.get("public_key") or payload_json.get("credential_request_options")
        if not isinstance(public_key, dict):
            return _fail(name, "passkey_options_missing", status=status, content_type=content_type)
        request_json = payload_json.get("request_json")
        if not isinstance(request_json, str) or not request_json.strip():
            return _fail(name, "passkey_request_json_missing", status=status, content_type=content_type)
        try:
            parsed_request = json.loads(request_json)
        except Exception:
            return _fail(name, "passkey_request_json_invalid", status=status, content_type=content_type)
        if not isinstance(parsed_request, dict) or parsed_request.get("challenge") != public_key.get("challenge"):
            return _fail(name, "passkey_request_json_mismatch", status=status, content_type=content_type)
    if path.endswith("/auth/oidc/start"):
        if not payload_json.get("authorization_url") or not payload_json.get("state"):
            return _fail(name, "oidc_start_missing_authorization_url", status=status, content_type=content_type)
    return _pass(name, status=status, content_type=content_type, configured=True)


def _hosted_auth_ceremony_checks(
    *,
    origin: str,
    base_path: str,
    host_header: str,
    timeout: int,
) -> list[SecureSigninSetupCheck]:
    return [
        _auth_ceremony_route_check(
            origin=origin,
            path=f"{base_path}/auth/passkey/options",
            host_header=host_header,
            timeout=timeout,
        ),
        _auth_ceremony_route_check(
            origin=origin,
            path=f"{base_path}/auth/oidc/start",
            host_header=host_header,
            timeout=timeout,
            method="POST",
            payload={
                "redirect_uri": "nullxoid://auth/oidc/callback",
                "code_challenge": "aibenchie-pkce-challenge",
                "code_challenge_method": "S256",
            },
        ),
    ]


def _protected_auth_route_check(
    *,
    origin: str,
    path: str,
    host_header: str,
    timeout: int,
    method: str = "GET",
    payload: dict[str, object] | None = None,
) -> SecureSigninSetupCheck:
    status, content_type, body = request_raw(
        origin,
        path,
        host_header=host_header,
        method=method,
        payload=payload,
        timeout=timeout,
    )
    failure = json_route_failure(
        status,
        content_type,
        body,
        route_name=path.strip("/").replace("/", "_"),
        allowed_statuses={401, 403, 501},
    )
    name = f"hosted_protected_auth:{path}"
    if failure:
        return _fail(name, failure, status=status, content_type=content_type)
    payload_json = json_payload(body)
    if not isinstance(payload_json, dict):
        return _fail(name, "protected_auth_payload_not_object", status=status, content_type=content_type)
    serialized = json.dumps(payload_json).lower()
    for forbidden in ["client_secret", "private_key", "nullbridge_service_secret"]:
        if forbidden in serialized:
            return _fail(name, "protected_auth_payload_exposed_secret", status=status, content_type=content_type)
    return _pass(name, status=status, content_type=content_type)


def _hosted_protected_auth_checks(
    *,
    origin: str,
    base_path: str,
    host_header: str,
    timeout: int,
) -> list[SecureSigninSetupCheck]:
    return [
        _protected_auth_route_check(
            origin=origin,
            path=f"{base_path}/auth/passkey/credentials",
            host_header=host_header,
            timeout=timeout,
        ),
        _protected_auth_route_check(
            origin=origin,
            path=f"{base_path}/auth/passkey/register/options",
            host_header=host_header,
            timeout=timeout,
        ),
        _protected_auth_route_check(
            origin=origin,
            path=f"{base_path}/auth/passkey/register/complete",
            host_header=host_header,
            timeout=timeout,
            method="POST",
            payload={"request_id": "aibenchie-route-check", "credential_json": "{}"},
        ),
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
        hosted_feature_checks = _hosted_feature_checks(
            origin=resolved_origin,
            base_path=resolved_base_path,
            host_header=host_header,
            timeout=timeout,
        )
        checks.extend(hosted_feature_checks)
        if hosted_feature_checks:
            checks.append(
                _hosted_android_assetlinks_check(
                    feature_check=hosted_feature_checks[0],
                    origin=resolved_origin,
                    timeout=timeout,
                )
            )
        checks.extend(
            _hosted_auth_ceremony_checks(
                origin=resolved_origin,
                base_path=resolved_base_path,
                host_header=host_header,
                timeout=timeout,
            )
        )
        checks.extend(
            _hosted_protected_auth_checks(
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
