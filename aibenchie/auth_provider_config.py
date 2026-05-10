from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


DEFAULT_CONFIG_PATH = Path("configs/echolabs_auth_provider_config.example.json")
EXPECTED_SCHEMA = "echolabs.auth-provider-config.v1"
EXPECTED_ANDROID_PACKAGE = "com.nullxoid.android"
EXPECTED_ASSETLINKS_RELATION = "delegate_permission/common.get_login_creds"
EXPECTED_ASSETLINKS_PATH = "/.well-known/assetlinks.json"
EXPECTED_OIDC_REDIRECT_URI = "nullxoid://auth/oidc/callback"
SHA256_FINGERPRINT = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2}){31}$", re.IGNORECASE)
PLACEHOLDER_MARKERS = ("REPLACE_", "<", ">", "example.test", "ISSUER", "CLIENT_ID")
FORBIDDEN_KEYS = {"client_secret", "private_key", "password", "service_secret", "service_token"}


@dataclass(frozen=True)
class AuthProviderConfigCheck:
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
class AuthProviderConfigResult:
    ok: bool
    config_path: str
    template: bool
    require_real: bool
    checks: list[AuthProviderConfigCheck]
    next_steps: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "config_path": self.config_path,
            "template": self.template,
            "require_real": self.require_real,
            "checks": [check.as_dict() for check in self.checks],
            "next_steps": self.next_steps,
        }


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _pass(name: str, **detail: Any) -> AuthProviderConfigCheck:
    return AuthProviderConfigCheck(name=name, ok=True, detail=detail)


def _fail(name: str, failure: str, **detail: Any) -> AuthProviderConfigCheck:
    return AuthProviderConfigCheck(name=name, ok=False, failure=failure, detail=detail)


def _is_placeholder(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    stripped = value.strip()
    return not stripped or any(marker in stripped for marker in PLACEHOLDER_MARKERS)


def _is_https_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def _host(value: str) -> str:
    return urlparse(value).netloc.lower()


def _check_forbidden_secret_keys(payload: Any, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            lowered = str(key).lower()
            if lowered in FORBIDDEN_KEYS or lowered.endswith("_secret") or lowered.endswith("_token"):
                found.append(f"{path}.{key}")
            found.extend(_check_forbidden_secret_keys(value, f"{path}.{key}"))
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            found.extend(_check_forbidden_secret_keys(item, f"{path}[{index}]"))
    return found


def _validate_passkey(config: dict[str, Any], *, template: bool, require_real: bool) -> list[AuthProviderConfigCheck]:
    checks: list[AuthProviderConfigCheck] = []
    passkey = config.get("passkey")
    if not isinstance(passkey, dict):
        return [_fail("passkey", "missing_passkey_config")]

    rp_id = passkey.get("rp_id")
    origin = passkey.get("origin")
    assetlinks_url = passkey.get("assetlinks_url")
    package_name = passkey.get("android_package")
    relations = passkey.get("relations")
    fingerprints = passkey.get("android_sha256_fingerprints")

    if not isinstance(rp_id, str) or not rp_id.strip() or "://" in rp_id:
        checks.append(_fail("passkey.rp_id", "invalid_rp_id", value=rp_id))
    elif require_real and _is_placeholder(rp_id):
        checks.append(_fail("passkey.rp_id", "placeholder_not_allowed", value=rp_id))
    else:
        checks.append(_pass("passkey.rp_id", value=rp_id))

    if not _is_https_url(origin):
        checks.append(_fail("passkey.origin", "origin_must_be_https", value=origin))
    elif isinstance(rp_id, str) and rp_id.strip() and not _is_placeholder(rp_id) and _host(origin) != rp_id.lower():
        checks.append(_fail("passkey.origin", "origin_host_must_match_rp_id", origin=origin, rp_id=rp_id))
    elif require_real and _is_placeholder(origin):
        checks.append(_fail("passkey.origin", "placeholder_not_allowed", value=origin))
    else:
        checks.append(_pass("passkey.origin", value=origin))

    if not _is_https_url(assetlinks_url):
        checks.append(_fail("passkey.assetlinks_url", "assetlinks_url_must_be_https", value=assetlinks_url))
    else:
        parsed = urlparse(assetlinks_url)
        if parsed.path != EXPECTED_ASSETLINKS_PATH:
            checks.append(_fail("passkey.assetlinks_url", "assetlinks_path_mismatch", expected=EXPECTED_ASSETLINKS_PATH, actual=parsed.path))
        elif isinstance(origin, str) and _is_https_url(origin) and parsed.netloc.lower() != _host(origin):
            checks.append(_fail("passkey.assetlinks_url", "assetlinks_host_must_match_origin", assetlinks_url=assetlinks_url, origin=origin))
        else:
            checks.append(_pass("passkey.assetlinks_url", value=assetlinks_url))

    if package_name != EXPECTED_ANDROID_PACKAGE:
        checks.append(_fail("passkey.android_package", "android_package_mismatch", expected=EXPECTED_ANDROID_PACKAGE, actual=package_name))
    else:
        checks.append(_pass("passkey.android_package", value=package_name))

    if not isinstance(relations, list) or EXPECTED_ASSETLINKS_RELATION not in relations:
        checks.append(_fail("passkey.relations", "missing_get_login_creds_relation", expected=EXPECTED_ASSETLINKS_RELATION))
    else:
        checks.append(_pass("passkey.relations", count=len(relations)))

    if not isinstance(fingerprints, list) or not fingerprints:
        checks.append(_fail("passkey.android_sha256_fingerprints", "missing_fingerprints"))
    else:
        placeholders = [value for value in fingerprints if _is_placeholder(value)]
        invalid = [
            value
            for value in fingerprints
            if not _is_placeholder(value) and (not isinstance(value, str) or not SHA256_FINGERPRINT.fullmatch(value.strip()))
        ]
        if require_real and (template or placeholders):
            checks.append(_fail("passkey.android_sha256_fingerprints", "real_release_fingerprint_required", placeholders=len(placeholders)))
        elif invalid:
            checks.append(_fail("passkey.android_sha256_fingerprints", "invalid_fingerprint_format", invalid_count=len(invalid)))
        else:
            checks.append(
                _pass(
                    "passkey.android_sha256_fingerprints",
                    count=len(fingerprints),
                    placeholders=len(placeholders),
                    template=template,
                )
            )
    return checks


def _validate_oidc(config: dict[str, Any], *, require_real: bool) -> list[AuthProviderConfigCheck]:
    checks: list[AuthProviderConfigCheck] = []
    oidc = config.get("oidc")
    if not isinstance(oidc, dict):
        return [_fail("oidc", "missing_oidc_config")]

    issuer = oidc.get("issuer")
    client_id = oidc.get("client_id")
    redirect_uri = oidc.get("redirect_uri")
    flow = oidc.get("flow")
    pkce_required = oidc.get("pkce_required")
    client_secret_allowed = oidc.get("client_secret_allowed")
    scopes = oidc.get("scopes")

    if not _is_https_url(issuer):
        checks.append(_fail("oidc.issuer", "issuer_must_be_https", value=issuer))
    elif require_real and _is_placeholder(issuer):
        checks.append(_fail("oidc.issuer", "placeholder_not_allowed", value=issuer))
    else:
        checks.append(_pass("oidc.issuer", value=issuer))

    if not isinstance(client_id, str) or not client_id.strip():
        checks.append(_fail("oidc.client_id", "missing_client_id"))
    elif require_real and _is_placeholder(client_id):
        checks.append(_fail("oidc.client_id", "placeholder_not_allowed", value=client_id))
    else:
        checks.append(_pass("oidc.client_id", placeholder=_is_placeholder(client_id)))

    if redirect_uri != EXPECTED_OIDC_REDIRECT_URI:
        checks.append(_fail("oidc.redirect_uri", "redirect_uri_mismatch", expected=EXPECTED_OIDC_REDIRECT_URI, actual=redirect_uri))
    else:
        checks.append(_pass("oidc.redirect_uri", value=redirect_uri))

    if flow != "authorization_code_pkce":
        checks.append(_fail("oidc.flow", "flow_must_be_authorization_code_pkce", actual=flow))
    else:
        checks.append(_pass("oidc.flow", value=flow))

    if pkce_required is not True:
        checks.append(_fail("oidc.pkce_required", "pkce_required_must_be_true"))
    else:
        checks.append(_pass("oidc.pkce_required"))

    if client_secret_allowed is not False:
        checks.append(_fail("oidc.client_secret_allowed", "public_client_secret_must_be_disallowed"))
    else:
        checks.append(_pass("oidc.client_secret_allowed", value=False))

    if not isinstance(scopes, list) or "openid" not in scopes:
        checks.append(_fail("oidc.scopes", "missing_openid_scope"))
    else:
        checks.append(_pass("oidc.scopes", count=len(scopes)))
    return checks


def validate_auth_provider_config(
    path: str | Path | None = None,
    *,
    require_real: bool = False,
) -> AuthProviderConfigResult:
    repo_root = _repo_root()
    config_path = Path(path or repo_root / DEFAULT_CONFIG_PATH)
    if not config_path.is_absolute():
        config_path = (repo_root / config_path).resolve()

    checks: list[AuthProviderConfigCheck] = []
    next_steps = [
        "Replace template placeholders with provider dashboard values in an ignored environment or deployment secret store.",
        "Publish /.well-known/assetlinks.json on the passkey RP origin after release signing SHA-256 fingerprints are known.",
        "Run this gate with --auth-provider-config-require-real before marking provider setup production-ready.",
    ]

    if not config_path.exists():
        check = _fail("config_file", "missing_config_file", path=str(config_path))
        return AuthProviderConfigResult(False, str(config_path), False, require_real, [check], next_steps)

    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception as exc:
        check = _fail("config_file", f"invalid_json:{type(exc).__name__}", path=str(config_path))
        return AuthProviderConfigResult(False, str(config_path), False, require_real, [check], next_steps)

    if not isinstance(payload, dict):
        check = _fail("config_file", "config_must_be_object", path=str(config_path))
        return AuthProviderConfigResult(False, str(config_path), False, require_real, [check], next_steps)

    template = payload.get("template") is True
    checks.append(_pass("config_file", path=str(config_path)))
    if payload.get("schema") != EXPECTED_SCHEMA:
        checks.append(_fail("schema", "schema_mismatch", expected=EXPECTED_SCHEMA, actual=payload.get("schema")))
    else:
        checks.append(_pass("schema", value=EXPECTED_SCHEMA))

    if require_real and template:
        checks.append(_fail("template", "template_config_not_allowed_when_real_required"))
    else:
        checks.append(_pass("template", value=template))

    forbidden = _check_forbidden_secret_keys(payload)
    if forbidden:
        checks.append(_fail("secret_keys_absent", "forbidden_secret_keys_present", paths=forbidden))
    else:
        checks.append(_pass("secret_keys_absent"))

    checks.extend(_validate_passkey(payload, template=template, require_real=require_real))
    checks.extend(_validate_oidc(payload, require_real=require_real))

    setup = payload.get("deployment_setup")
    if not isinstance(setup, dict):
        checks.append(_fail("deployment_setup", "missing_deployment_setup"))
    else:
        env_names = setup.get("env_names")
        if not isinstance(env_names, list) or not env_names:
            checks.append(_fail("deployment_setup.env_names", "missing_env_names"))
        elif any(not isinstance(value, str) or not value.startswith("NULLXOID_AUTH_") for value in env_names):
            checks.append(_fail("deployment_setup.env_names", "env_names_must_be_namespaced"))
        else:
            checks.append(_pass("deployment_setup.env_names", count=len(env_names)))

    return AuthProviderConfigResult(
        ok=all(check.ok for check in checks),
        config_path=str(config_path),
        template=template,
        require_real=require_real,
        checks=checks,
        next_steps=next_steps,
    )


def run_from_env() -> AuthProviderConfigResult:
    require_real = os.environ.get("AIBENCHIE_AUTH_PROVIDER_CONFIG_REQUIRE_REAL", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    return validate_auth_provider_config(
        os.environ.get("AIBENCHIE_AUTH_PROVIDER_CONFIG") or None,
        require_real=require_real,
    )
