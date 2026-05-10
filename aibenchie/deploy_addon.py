from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from aibenchie.release_artifacts import sha256_file, verify_release_artifacts_manifest


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
PUBLISH_CONFIRM_ENV = "AIBENCHIE_DEPLOY_PUBLISH_CONFIRM"


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


@dataclass(frozen=True)
class DeployExecutionResult:
    ok: bool
    config_path: str
    provider: str
    repository: str
    release_tag: str
    dry_run: bool
    published: bool
    checks: list[DeployAddonCheck]
    evidence: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "config_path": self.config_path,
            "provider": self.provider,
            "repository": self.repository,
            "release_tag": self.release_tag,
            "dry_run": self.dry_run,
            "published": self.published,
            "checks": [check.as_dict() for check in self.checks],
            "evidence": self.evidence,
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


def _asset_root(path: Path) -> str:
    return str(path.expanduser().resolve().parent)


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
        "asset_root": _asset_root(release_artifacts_path) if release_artifacts_ref else "",
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


def _json_request(
    method: str,
    url: str,
    *,
    token: str,
    payload: dict[str, Any] | None = None,
    data: bytes | None = None,
    content_type: str = "application/json",
    timeout: int = 30,
) -> tuple[int, dict[str, Any]]:
    body = data
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "AIBenchie-Deploy-Addon",
    }
    if body is not None:
        headers["Content-Type"] = content_type
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            text = response.read().decode("utf-8-sig", errors="replace")
            return response.status, json.loads(text) if text else {}
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8-sig", errors="replace")
        try:
            payload = json.loads(text) if text else {}
        except json.JSONDecodeError:
            payload = {"error": text[:500]}
        return exc.code, payload


def _release_api_base(provider: dict[str, Any]) -> str:
    provider_type = str(provider.get("type") or "").strip().lower()
    base_url = str(provider.get("base_url") or "").strip().rstrip("/")
    repository = urllib.parse.quote(str(provider.get("repository") or "").strip(), safe="/")
    if provider_type == "github" and base_url in {"https://github.com", "http://github.com"}:
        return f"https://api.github.com/repos/{repository}/releases"
    if provider_type in {"github", "github_enterprise"}:
        return f"{base_url}/api/v3/repos/{repository}/releases"
    return f"{base_url}/api/v1/repos/{repository}/releases"


def _release_tag_url(provider: dict[str, Any], tag: str) -> str:
    return f"{_release_api_base(provider).rstrip('/')}/tags/{urllib.parse.quote(tag)}"


def _release_payload(plan: dict[str, Any]) -> dict[str, Any]:
    release = plan.get("release") if isinstance(plan.get("release"), dict) else {}
    return {
        "tag_name": str(release.get("tag") or "").strip(),
        "name": str(release.get("name") or release.get("tag") or "").strip(),
        "prerelease": bool(release.get("prerelease", True)),
        "draft": False,
        "body": "Published by AIBenchie deploy add-on after suite verdict and release attestation verification.",
    }


def _asset_path(plan: dict[str, Any], asset: dict[str, Any], config_dir: Path) -> Path:
    path = Path(str(asset.get("path") or "")).expanduser()
    if path.is_absolute():
        return path
    asset_root = str(plan.get("asset_root") or "").strip()
    if asset_root:
        return (Path(asset_root).expanduser() / path).resolve()
    return (config_dir / path).resolve()


def _upload_url(provider: dict[str, Any], release_response: dict[str, Any], asset_name: str) -> str:
    provider_type = str(provider.get("type") or "").strip().lower()
    if provider_type in {"github", "github_enterprise"}:
        template = str(release_response.get("upload_url") or "").split("{", 1)[0]
        return f"{template}?name={urllib.parse.quote(asset_name)}"
    base_url = str(provider.get("base_url") or "").strip().rstrip("/")
    repository = urllib.parse.quote(str(provider.get("repository") or "").strip(), safe="/")
    release_id = str(release_response.get("id") or "").strip()
    return f"{base_url}/api/v1/repos/{repository}/releases/{release_id}/assets?name={urllib.parse.quote(asset_name)}"


def _multipart_file_payload(
    *,
    field_name: str,
    filename: str,
    data: bytes,
    content_type: str = "application/octet-stream",
) -> tuple[bytes, str]:
    boundary = f"aibenchie-{sha256(filename.encode('utf-8') + data).hexdigest()[:24]}"
    header = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode("utf-8")
    footer = f"\r\n--{boundary}--\r\n".encode("utf-8")
    return header + data + footer, f"multipart/form-data; boundary={boundary}"


def _asset_upload_body(provider: dict[str, Any], asset_name: str, asset_bytes: bytes) -> tuple[bytes, str]:
    provider_type = str(provider.get("type") or "").strip().lower()
    if provider_type in {"github", "github_enterprise"}:
        return asset_bytes, "application/octet-stream"
    return _multipart_file_payload(field_name="attachment", filename=asset_name, data=asset_bytes)


def _publish_plan(
    *,
    plan: dict[str, Any],
    config_dir: Path,
    token: str,
    request_json=_json_request,
) -> tuple[bool, str, list[dict[str, Any]]]:
    provider = plan.get("provider") if isinstance(plan.get("provider"), dict) else {}
    release = plan.get("release") if isinstance(plan.get("release"), dict) else {}
    release_tag = str(release.get("tag") or "").strip()
    release_tag_url = _release_tag_url(provider, release_tag)
    tag_status, _tag_response = request_json("GET", release_tag_url, token=token)
    evidence = [
        {
            "kind": "provider_request",
            "operation": "check_release_absent",
            "status": tag_status,
            "ok": tag_status == 404,
            "url": release_tag_url,
        }
    ]
    if tag_status == 200:
        return False, "release_tag_already_exists", evidence
    if tag_status != 404:
        return False, f"release_tag_preflight_failed:{tag_status}", evidence

    release_url = _release_api_base(provider)
    release_status, release_response = request_json("POST", release_url, token=token, payload=_release_payload(plan))
    evidence.append(
        {
            "kind": "provider_request",
            "operation": "create_release",
            "status": release_status,
            "ok": 200 <= release_status < 300,
            "url": release_url,
        }
    )
    if not 200 <= release_status < 300:
        return False, f"release_create_failed:{release_status}", evidence

    for asset in plan.get("assets") if isinstance(plan.get("assets"), list) else []:
        if not isinstance(asset, dict):
            continue
        asset_name = str(asset.get("name") or asset.get("kind") or "asset").strip()
        asset_file = _asset_path(plan, asset, config_dir)
        if not asset_file.exists() or not asset_file.is_file():
            evidence.append(
                {
                    "kind": "provider_request",
                    "operation": "upload_asset",
                    "asset": asset_name,
                    "ok": False,
                    "failure": "asset_file_missing",
                    "path": str(asset_file),
                }
            )
            return False, f"asset_file_missing:{asset_name}", evidence
        expected_sha256 = str(asset.get("sha256") or "").strip().lower()
        actual_sha256 = sha256_file(asset_file).lower()
        if expected_sha256 and actual_sha256 != expected_sha256:
            evidence.append(
                {
                    "kind": "provider_request",
                    "operation": "upload_asset",
                    "asset": asset_name,
                    "ok": False,
                    "failure": "asset_sha256_mismatch",
                    "path": str(asset_file),
                }
            )
            return False, f"asset_sha256_mismatch:{asset_name}", evidence
        upload_url = _upload_url(provider, release_response, asset_name)
        upload_body, upload_content_type = _asset_upload_body(provider, asset_name, asset_file.read_bytes())
        status, _payload = request_json(
            "POST",
            upload_url,
            token=token,
            data=upload_body,
            content_type=upload_content_type,
        )
        evidence.append(
            {
                "kind": "provider_request",
                "operation": "upload_asset",
                "asset": asset_name,
                "status": status,
                "ok": 200 <= status < 300,
                "url": upload_url,
            }
        )
        if not 200 <= status < 300:
            return False, f"asset_upload_failed:{asset_name}:{status}", evidence

    return True, "", evidence


def execute_deploy_addon(
    *,
    config_path: Path | None = None,
    publish_confirm: str = "",
    request_json=_json_request,
) -> DeployExecutionResult:
    gate = run_deploy_addon_check(config_path=config_path, require_token=True)
    checks = list(gate.checks)
    config_file = Path(gate.config_path)
    try:
        loaded_config = _load_json(config_file) if config_file.exists() else {}
        config = loaded_config if isinstance(loaded_config, dict) else {}
    except json.JSONDecodeError:
        config = {}
    auth = config.get("auth") if isinstance(config, dict) and isinstance(config.get("auth"), dict) else {}
    token_env = str(auth.get("token_env") or "").strip()
    token = os.environ.get(token_env, "") if token_env else ""
    confirmation = publish_confirm.strip() or os.environ.get(PUBLISH_CONFIRM_ENV, "").strip()
    release_tag = gate.release_tag

    checks.append(_check("publish_gate_passed", gate.ok, "deploy_gate_failed"))
    checks.append(_check("plan_is_not_dry_run", not gate.dry_run, "plan_is_dry_run", dry_run=gate.dry_run))
    checks.append(
        _check(
            "publish_confirmation",
            bool(release_tag) and confirmation == release_tag,
            "publish_confirmation_mismatch",
            expected=release_tag,
        )
    )
    checks.append(_check("runtime_token", bool(token), "runtime_token_missing", token_env=token_env))

    if not all(check.ok for check in checks):
        return DeployExecutionResult(
            ok=False,
            config_path=gate.config_path,
            provider=gate.provider,
            repository=gate.repository,
            release_tag=release_tag,
            dry_run=gate.dry_run,
            published=False,
            checks=checks,
        )

    publish_ok, publish_failure, evidence = _publish_plan(
        plan=gate.deploy_plan,
        config_dir=config_file.parent,
        token=token,
        request_json=request_json,
    )
    checks.append(_check("provider_publish", publish_ok, publish_failure))
    return DeployExecutionResult(
        ok=publish_ok,
        config_path=gate.config_path,
        provider=gate.provider,
        repository=gate.repository,
        release_tag=release_tag,
        dry_run=gate.dry_run,
        published=publish_ok,
        checks=checks,
        evidence=evidence,
    )
