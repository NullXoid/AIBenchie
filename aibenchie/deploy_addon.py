from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from aibenchie.release_artifacts import verify_release_artifacts_manifest


DEPLOY_ADDON_SCHEMA = "aibenchie.deploy-addon.v1"
DEPLOY_PLAN_SCHEMA = "aibenchie.deploy-plan.v1"
CONFIG_ENV = "AIBENCHIE_DEPLOY_ADDON_CONFIG"
REQUIRED_DEPLOY_ASSET_KINDS = ("wrapper", "android", "public")
ALLOWED_PROVIDERS = {
    "forgejo",
    "gitea",
    "github",
    "github_enterprise",
    "forgejo_compatible",
    "gitea_compatible",
}
PASS_VALUES = {"pass", "passed", "green", "ready", "gated", "success", "ok", "ship"}
FAIL_VALUES = {"fail", "failed", "red", "blocked", "error", "no-go", "nogo"}
SECRET_KEY_PARTS = ("token", "secret", "password", "credential", "private_key", "apikey", "api_key")
SECRET_VALUE_PREFIXES = ("ghp_", "github_pat_", "gitea_", "forgejo_", "glpat-", "xoxb-", "sk-")


@dataclass(frozen=True)
class DeployAddonCheck:
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
class DeployAddonResult:
    ok: bool
    config_path: str
    provider: str
    repository: str
    release_tag: str
    dry_run: bool
    checks: list[DeployAddonCheck]
    deploy_plan: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "config_path": self.config_path,
            "provider": self.provider,
            "repository": self.repository,
            "release_tag": self.release_tag,
            "dry_run": self.dry_run,
            "checks": [check.as_dict() for check in self.checks],
            "deploy_plan": self.deploy_plan,
        }


@dataclass(frozen=True)
class DeployPlanVerification:
    ok: bool
    plan_path: str
    checks: list[DeployAddonCheck]
    deploy_plan: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "plan_path": self.plan_path,
            "checks": [check.as_dict() for check in self.checks],
            "deploy_plan": self.deploy_plan,
        }


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve(base: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return (base / path).resolve()


def _check(name: str, ok: bool, failure: str = "", **detail: Any) -> DeployAddonCheck:
    return DeployAddonCheck(name=name, ok=ok, failure="" if ok else failure, detail=detail)


def _scan_secret_like_values(value: Any, path: str = "") -> list[str]:
    failures: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}" if path else key_text
            key_lower = key_text.lower()
            if key_lower == "token_env":
                if not isinstance(child, str) or not child.strip():
                    failures.append(f"{child_path}:token_env_missing")
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
        stripped = value.strip()
        lower = stripped.lower()
        if any(lower.startswith(prefix) for prefix in SECRET_VALUE_PREFIXES):
            failures.append(f"{path}:secret_value_not_allowed")
    return failures


def _verdict_value(payload: dict[str, Any]) -> str:
    for key in ("verdict", "releaseVerdict", "status", "result"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    if payload.get("ok") is True:
        return "ok"
    return "unknown"


def _suite_verdict_ok(path: Path) -> tuple[bool, str, dict[str, Any]]:
    if not path.exists():
        return False, "suite_verdict_missing", {}
    try:
        payload = _load_json(path)
    except json.JSONDecodeError as exc:
        return False, f"suite_verdict_invalid_json:{exc.lineno}", {}
    if not isinstance(payload, dict):
        return False, "suite_verdict_not_object", {}
    value = _verdict_value(payload)
    if value in FAIL_VALUES:
        return False, f"suite_verdict_blocking:{value}", {"verdict": value}
    if value in PASS_VALUES:
        return True, "", {"verdict": value}
    return False, f"suite_verdict_unknown:{value}", {"verdict": value}


def _provider_ok(provider: dict[str, Any]) -> tuple[bool, str]:
    provider_type = str(provider.get("type") or "").strip().lower()
    if provider_type not in ALLOWED_PROVIDERS:
        return False, f"unsupported_provider:{provider_type or 'missing'}"
    parsed = urlparse(str(provider.get("base_url") or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False, "provider_base_url_invalid"
    repository = str(provider.get("repository") or "").strip()
    if "/" not in repository or repository.startswith("/") or repository.endswith("/"):
        return False, "provider_repository_invalid"
    return True, ""


def _token_ok(config: dict[str, Any], *, require_token: bool) -> tuple[bool, str, dict[str, Any]]:
    auth = config.get("auth") if isinstance(config.get("auth"), dict) else {}
    token_env = str(auth.get("token_env") or "").strip()
    if not token_env:
        return False, "token_env_missing", {}
    if not token_env.replace("_", "").isalnum() or token_env[0].isdigit():
        return False, "token_env_invalid", {"token_env": token_env}
    if require_token and not os.environ.get(token_env):
        return False, "token_env_value_missing", {"token_env": token_env}
    return True, "", {"token_env": token_env, "token_required": require_token}


def _artifact_plan(artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    plan = []
    for artifact in artifacts:
        plan.append(
            {
                "kind": artifact.get("kind") or "",
                "name": artifact.get("name") or artifact.get("kind") or "",
                "path": artifact.get("path") or "",
                "sha256": artifact.get("sha256") or "",
            }
        )
    return plan


def _is_sha256(value: Any) -> bool:
    text = str(value or "").strip()
    return len(text) == 64 and all(char in "0123456789abcdefABCDEF" for char in text)


def verify_deploy_plan(plan_path: Path) -> DeployPlanVerification:
    resolved_plan = plan_path.expanduser().resolve()
    checks: list[DeployAddonCheck] = []
    plan: dict[str, Any] = {}

    if resolved_plan.exists():
        try:
            loaded = _load_json(resolved_plan)
            plan = loaded if isinstance(loaded, dict) else {}
            checks.append(_check("plan_json", isinstance(loaded, dict), "plan_not_object"))
        except json.JSONDecodeError as exc:
            checks.append(_check("plan_json", False, f"plan_invalid_json:{exc.lineno}"))
    else:
        checks.append(_check("plan_json", False, "plan_missing"))

    checks.append(_check("schema", plan.get("schema") == DEPLOY_PLAN_SCHEMA, "schema_mismatch"))

    secret_failures = _scan_secret_like_values(plan)
    checks.append(_check("secret_boundary", not secret_failures, ";".join(secret_failures), scanned=True))

    provider = plan.get("provider") if isinstance(plan.get("provider"), dict) else {}
    provider_ok, provider_failure = _provider_ok(provider)
    checks.append(
        _check(
            "provider",
            provider_ok,
            provider_failure,
            provider=str(provider.get("type") or "").strip().lower(),
            repository=str(provider.get("repository") or "").strip(),
        )
    )

    release = plan.get("release") if isinstance(plan.get("release"), dict) else {}
    release_tag = str(release.get("tag") or "").strip()
    checks.append(_check("release_tag", bool(release_tag), "release_tag_missing", tag=release_tag))

    assets = plan.get("assets") if isinstance(plan.get("assets"), list) else []
    asset_kinds = {str(asset.get("kind") or "") for asset in assets if isinstance(asset, dict)}
    missing_kinds = [kind for kind in REQUIRED_DEPLOY_ASSET_KINDS if kind not in asset_kinds]
    checks.append(_check("required_assets", not missing_kinds, ";".join(f"asset_missing:{kind}" for kind in missing_kinds)))

    asset_failures: list[str] = []
    for index, asset in enumerate(assets):
        if not isinstance(asset, dict):
            asset_failures.append(f"asset_not_object:{index}")
            continue
        kind = str(asset.get("kind") or "").strip()
        path = str(asset.get("path") or "").strip()
        sha256 = str(asset.get("sha256") or "").strip()
        if not kind:
            asset_failures.append(f"asset_kind_missing:{index}")
        if not path:
            asset_failures.append(f"asset_path_missing:{kind or index}")
        if not _is_sha256(sha256):
            asset_failures.append(f"asset_sha256_invalid:{kind or index}")
    checks.append(_check("assets", not asset_failures, ";".join(asset_failures), count=len(assets)))

    return DeployPlanVerification(
        ok=all(check.ok for check in checks),
        plan_path=str(resolved_plan),
        checks=checks,
        deploy_plan=plan,
    )


def run_deploy_addon_check(
    *,
    config_path: Path | None = None,
    require_token: bool = False,
) -> DeployAddonResult:
    selected_config = config_path or Path(os.environ.get(CONFIG_ENV, "configs/aibenchie_deploy_addon.example.json"))
    resolved_config = selected_config.expanduser().resolve()
    base = resolved_config.parent
    checks: list[DeployAddonCheck] = []

    config: dict[str, Any] = {}
    if resolved_config.exists():
        try:
            loaded = _load_json(resolved_config)
            config = loaded if isinstance(loaded, dict) else {}
            checks.append(_check("config_json", isinstance(loaded, dict), "config_not_object"))
        except json.JSONDecodeError as exc:
            checks.append(_check("config_json", False, f"config_invalid_json:{exc.lineno}"))
    else:
        checks.append(_check("config_json", False, "config_missing"))

    checks.append(_check("schema", config.get("schema") == DEPLOY_ADDON_SCHEMA, "schema_mismatch"))

    secret_failures = _scan_secret_like_values(config)
    checks.append(
        _check(
            "secret_boundary",
            not secret_failures,
            ";".join(secret_failures),
            scanned=True,
        )
    )

    provider = config.get("provider") if isinstance(config.get("provider"), dict) else {}
    provider_type = str(provider.get("type") or "").strip().lower()
    repository = str(provider.get("repository") or "").strip()
    provider_check, provider_failure = _provider_ok(provider)
    checks.append(_check("provider", provider_check, provider_failure, provider=provider_type, repository=repository))

    token_check, token_failure, token_detail = _token_ok(config, require_token=require_token)
    checks.append(_check("provider_auth_reference", token_check, token_failure, **token_detail))

    release = config.get("release") if isinstance(config.get("release"), dict) else {}
    release_tag = str(release.get("tag") or "").strip()
    checks.append(_check("release_tag", bool(release_tag), "release_tag_missing", tag=release_tag))

    evidence = config.get("evidence") if isinstance(config.get("evidence"), dict) else {}
    suite_verdict_ref = str(evidence.get("suite_verdict") or "").strip()
    if suite_verdict_ref:
        suite_verdict_path = _resolve(base, suite_verdict_ref)
        suite_ok, suite_failure, suite_detail = _suite_verdict_ok(suite_verdict_path)
        checks.append(_check("suite_verdict", suite_ok, suite_failure, path=str(suite_verdict_path), **suite_detail))
    else:
        checks.append(_check("suite_verdict", False, "suite_verdict_path_missing"))

    release_artifacts_ref = str(evidence.get("release_artifacts") or "").strip()
    artifact_summaries: list[dict[str, Any]] = []
    if release_artifacts_ref:
        release_artifacts_path = _resolve(base, release_artifacts_ref)
        verification = verify_release_artifacts_manifest(release_artifacts_path)
        artifact_summaries = verification.artifacts
        checks.append(
            _check(
                "release_attestation",
                verification.ok,
                ";".join(verification.failures),
                manifest=verification.manifest,
                artifact_count=verification.artifact_count,
            )
        )
    else:
        checks.append(_check("release_attestation", False, "release_artifacts_path_missing"))

    dry_run = bool(config.get("dry_run", True))
    deploy_plan = {
        "schema": DEPLOY_PLAN_SCHEMA,
        "dry_run": dry_run,
        "provider": {
            "type": provider_type,
            "base_url": str(provider.get("base_url") or "").strip(),
            "repository": repository,
        },
        "release": {
            "tag": release_tag,
            "name": str(release.get("name") or release_tag).strip(),
            "prerelease": bool(release.get("prerelease", True)),
        },
        "assets": _artifact_plan(artifact_summaries),
        "requires": [
            "passing_suite_verdict",
            "verified_release_artifact_attestation",
            "runtime_provider_token",
        ],
    }

    return DeployAddonResult(
        ok=all(check.ok for check in checks),
        config_path=str(resolved_config),
        provider=provider_type,
        repository=repository,
        release_tag=release_tag,
        dry_run=dry_run,
        checks=checks,
        deploy_plan=deploy_plan,
    )


def run_from_env() -> DeployAddonResult:
    config = os.environ.get(CONFIG_ENV, "").strip()
    require_token = os.environ.get("AIBENCHIE_DEPLOY_ADDON_REQUIRE_TOKEN", "").strip().lower() in {"1", "true", "yes"}
    return run_deploy_addon_check(config_path=Path(config) if config else None, require_token=require_token)
