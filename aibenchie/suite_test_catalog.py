from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


TAIL_CHARS = 4000
TRUE_VALUES = {"1", "true", "yes", "on"}
PYTHON_OVERRIDE_ENV = {
    "aibenchie_core": "AIBENCHIE_CORE_PYTHON",
    "nullbridge_trust_fabric": "AIBENCHIE_NULLBRIDGE_PYTHON",
    "nullxoid_wrapper_backend": "AIBENCHIE_NULLXOID_WRAPPER_PYTHON",
}
SECRET_VALUE_RE = re.compile(
    r"(?i)\b(password|passwd|token|secret|api[_-]?key|authorization)\b\s*[:=]\s*([^\s,;]+)"
)


@dataclass(frozen=True)
class SuiteTestTarget:
    name: str
    description: str
    repo_env: str
    repo_candidates: tuple[str, ...]
    required_paths: tuple[str, ...]
    command: tuple[str, ...]
    optional: bool = False
    timeout_seconds: int = 180

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "repo_env": self.repo_env,
            "repo_candidates": list(self.repo_candidates),
            "required_paths": list(self.required_paths),
            "command": list(self.command),
            "optional": self.optional,
            "timeout_seconds": self.timeout_seconds,
        }


@dataclass
class SuiteTestResult:
    name: str
    description: str
    status: str
    ok: bool
    optional: bool
    repo: str
    command: list[str]
    returncode: int | None = None
    duration_seconds: float = 0.0
    stdout_tail: str = ""
    stderr_tail: str = ""
    failure: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "ok": self.ok,
            "optional": self.optional,
            "repo": self.repo,
            "command": self.command,
            "returncode": self.returncode,
            "duration_seconds": round(self.duration_seconds, 3),
            "stdout_tail": self.stdout_tail,
            "stderr_tail": self.stderr_tail,
            "failure": self.failure,
        }


@dataclass
class SuiteTestCatalogResult:
    ok: bool
    root: str
    include_optional: bool
    require_all: bool
    selected_targets: list[str]
    targets: list[SuiteTestTarget]
    results: list[SuiteTestResult]

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "root": self.root,
            "include_optional": self.include_optional,
            "require_all": self.require_all,
            "selected_targets": self.selected_targets,
            "targets": [target.as_dict() for target in self.targets],
            "results": [result.as_dict() for result in self.results],
        }


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _env_flag(env: dict[str, str], name: str) -> bool:
    return env.get(name, "").strip().lower() in TRUE_VALUES


def _redact(text: str) -> str:
    if not text:
        return ""
    return SECRET_VALUE_RE.sub(lambda match: f"{match.group(1)}=[REDACTED]", text)


def _tail(text: str) -> str:
    value = _redact(text or "")
    if len(value) <= TAIL_CHARS:
        return value
    return value[-TAIL_CHARS:]


def _dedupe(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for path in paths:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


def _candidate_paths(root: Path, candidate: str) -> list[Path]:
    path = Path(candidate).expanduser()
    if path.is_absolute():
        return [path]
    return _dedupe([(root / path).resolve(), (root.parent / path).resolve()])


def _resolve_repo(root: Path, env: dict[str, str], target: SuiteTestTarget) -> Path | None:
    env_value = env.get(target.repo_env, "").strip()
    if env_value:
        path = Path(env_value).expanduser()
        if not path.is_absolute():
            path = (root / path).resolve()
        return path if path.exists() else None

    fallback: Path | None = None
    for candidate in target.repo_candidates:
        for path in _candidate_paths(root, candidate):
            if path.exists():
                if fallback is None:
                    fallback = path
                if not _missing_paths(path, target):
                    return path
    return fallback


def _android_command() -> tuple[str, ...]:
    if os.name == "nt":
        return ("cmd", "/c", "gradlew.bat", ":app:testDebugUnitTest")
    return ("./gradlew", ":app:testDebugUnitTest")


def _npm_command(*args: str) -> tuple[str, ...]:
    executable = "npm.cmd" if os.name == "nt" else "npm"
    return (executable, *args)


def _java_executable(java_home: Path) -> Path:
    name = "java.exe" if os.name == "nt" else "java"
    return java_home / "bin" / name


def _java_home_candidates(root: Path, env: dict[str, str]) -> list[Path]:
    paths: list[Path] = []
    for key in ("AIBENCHIE_JAVA_HOME", "JAVA_HOME"):
        value = env.get(key, "").strip()
        if value:
            paths.append(Path(value).expanduser())

    if os.name == "nt":
        paths.extend(
            [
                Path(r"C:\Program Files\Android\Android Studio\jbr"),
                Path(r"C:\Program Files\Android\Android Studio\jre"),
            ]
        )
        for parent in (
            Path(r"C:\Program Files\Eclipse Adoptium"),
            Path(r"C:\Program Files\Java"),
            Path.home() / ".jdks",
        ):
            if parent.exists():
                paths.extend(sorted(parent.glob("*jdk*"), reverse=True))
                paths.extend(sorted(parent.glob("*temurin*"), reverse=True))
    else:
        for parent in (Path("/usr/lib/jvm"), Path("/opt/homebrew/opt"), Path.home() / ".jdks"):
            if parent.exists():
                paths.extend(sorted(parent.glob("*jdk*"), reverse=True))
                paths.extend(sorted(parent.glob("*java*"), reverse=True))

    return _dedupe([path if path.is_absolute() else (root / path).resolve() for path in paths])


def _discover_java_home(root: Path, env: dict[str, str]) -> Path | None:
    for java_home in _java_home_candidates(root, env):
        if _java_executable(java_home).exists():
            return java_home
    return None


def _process_env(root: Path, env: dict[str, str], target: SuiteTestTarget) -> dict[str, str]:
    process_env = {**os.environ, **env}
    if target.name.startswith("android_"):
        java_home = _discover_java_home(root, process_env)
        if java_home:
            process_env["JAVA_HOME"] = str(java_home)
            process_env["PATH"] = f"{java_home / 'bin'}{os.pathsep}{process_env.get('PATH', '')}"
    return process_env


def _target_command(env: dict[str, str], target: SuiteTestTarget) -> list[str]:
    command = list(target.command)
    override_env = PYTHON_OVERRIDE_ENV.get(target.name)
    if override_env and env.get(override_env, "").strip():
        command[0] = env[override_env].strip()
    return command


def build_suite_test_catalog() -> list[SuiteTestTarget]:
    return [
        SuiteTestTarget(
            name="aibenchie_core",
            description="AIBenchie hosted, security, secure sign-in, auth provider config, NullBridge E2E trust/notification, resource, output, and Companion gates",
            repo_env="AIBENCHIE_REPO",
            repo_candidates=(".",),
            required_paths=(
                "tests/test_suite_security.py",
                "tests/test_secure_signin_setup.py",
                "tests/test_auth_provider_config.py",
                "tests/test_local_nullbridge_runner.py",
                "tests/test_live_trust_path.py",
                "tests/test_hosted_nullxoid_stack.py",
                "tests/test_hosted_nullxoid_chat.py",
                "tests/test_resource_budget.py",
                "tests/test_generated_output_policy.py",
                "tests/test_suite_security_privacy.py",
                "tests/test_release_artifacts.py",
                "tests/test_release_bundle.py",
                "tests/test_companion_remote_backend.py",
                "tests/test_e2ee_readiness.py",
                "tests/test_zero_knowledge_devices.py",
            ),
            command=(
                sys.executable,
                "-m",
                "pytest",
                "tests/test_suite_security.py",
                "tests/test_secure_signin_setup.py",
                "tests/test_auth_provider_config.py",
                "tests/test_local_nullbridge_runner.py",
                "tests/test_live_trust_path.py",
                "tests/test_hosted_nullxoid_stack.py",
                "tests/test_hosted_nullxoid_chat.py",
                "tests/test_resource_budget.py",
                "tests/test_generated_output_policy.py",
                "tests/test_suite_security_privacy.py",
                "tests/test_release_artifacts.py",
                "tests/test_release_bundle.py",
                "tests/test_companion_remote_backend.py",
                "tests/test_e2ee_readiness.py",
                "tests/test_zero_knowledge_devices.py",
            ),
            timeout_seconds=240,
        ),
        SuiteTestTarget(
            name="aibenchie_security_privacy",
            description="M36 suite security/privacy gate definition, route inventory, canary leakage, artifact/CCC scoping, and NullBridge denial evidence",
            repo_env="AIBENCHIE_REPO",
            repo_candidates=(".",),
            required_paths=(
                "aibenchie/suite_security_privacy.py",
                "aibenchie/policies/route-privacy-inventory.json",
                "tests/test_suite_security_privacy.py",
            ),
            command=(
                sys.executable,
                "-m",
                "pytest",
                "tests/test_suite_security_privacy.py",
            ),
            timeout_seconds=240,
        ),
        SuiteTestTarget(
            name="aibenchie_echolabs_store",
            description="EchoLabs Store Alpha catalog, cross-platform parity, approval gating, artifact privacy, and credential isolation gate",
            repo_env="AIBENCHIE_REPO",
            repo_candidates=(".",),
            required_paths=(
                "aibenchie/echolabs_store.py",
                "tests/test_echolabs_store.py",
            ),
            command=(
                sys.executable,
                "-m",
                "pytest",
                "tests/test_echolabs_store.py",
            ),
            timeout_seconds=240,
        ),
        SuiteTestTarget(
            name="nullbridge_trust_fabric",
            description="NullBridge signed service identity, deny-by-default routing, notification policy, redacted audit, release-fabric, and cleanup contracts",
            repo_env="AIBENCHIE_NULLBRIDGE_REPO",
            repo_candidates=("../NullBridge", "NullBridge"),
            required_paths=(
                "backend/tests/test_service_bridge_compliance.py",
                "backend/tests/test_suite_trust_release_fabric.py",
                "backend/tests/test_nullbridge_runtime_cleanup.py",
            ),
            command=(
                sys.executable,
                "-m",
                "pytest",
                "backend/tests/test_service_bridge_compliance.py",
                "backend/tests/test_suite_trust_release_fabric.py",
                "backend/tests/test_nullbridge_runtime_cleanup.py",
            ),
            timeout_seconds=180,
        ),
        SuiteTestTarget(
            name="nullxoid_wrapper_backend",
            description="NullXoid wrapper backend auth, corruption recovery, project/chat, model inventory, and ephemeral user contracts",
            repo_env="AIBENCHIE_NULLXOID_WRAPPER_REPO",
            repo_candidates=("../.NullXoid", "../NullXoid-live", "../Felnx/NullXoid", "../NullXoid"),
            required_paths=(
                "backend/tests/test_auth_json_contract.py",
                "backend/tests/test_store_corruption_contract.py",
                "backend/tests/test_chat_contract.py",
                "backend/tests/test_project_contract.py",
                "backend/tests/test_model_inventory.py",
                "backend/tests/test_ephemeral_e2e_user.py",
                "backend/tests/test_dependency_contract.py",
            ),
            command=(
                sys.executable,
                "-m",
                "pytest",
                "backend/tests/test_auth_json_contract.py",
                "backend/tests/test_store_corruption_contract.py",
                "backend/tests/test_chat_contract.py",
                "backend/tests/test_project_contract.py",
                "backend/tests/test_model_inventory.py",
                "backend/tests/test_ephemeral_e2e_user.py",
                "backend/tests/test_dependency_contract.py",
            ),
            timeout_seconds=180,
        ),
        SuiteTestTarget(
            name="nullxoid_wrapper_frontend_e2ee",
            description="NullXoid wrapper frontend saved-chat E2EE and zero-knowledge device setup contracts",
            repo_env="AIBENCHIE_NULLXOID_WRAPPER_REPO",
            repo_candidates=("../.NullXoid", "../NullXoid-live", "../Felnx/NullXoid", "../NullXoid"),
            required_paths=(
                "frontend/package.json",
                "frontend/scripts/test-chat-e2ee.mjs",
                "frontend/scripts/test-e2ee-device-lifecycle.mjs",
                "frontend/scripts/test-e2ee-device-setup-state.mjs",
                "frontend/src/lib/chatE2ee.js",
                "frontend/src/lib/e2eeDeviceLifecycle.js",
                "frontend/src/lib/e2eeDeviceSetupState.js",
            ),
            command=_npm_command("run", "test:e2ee", "--prefix", "frontend"),
            timeout_seconds=180,
        ),
        SuiteTestTarget(
            name="android_companion_unit",
            description="NullXoid Companion/Android backend endpoint and app unit contracts",
            repo_env="AIBENCHIE_ANDROID_REPO",
            repo_candidates=("../NullXoidAndroid", "NullXoidAndroid"),
            required_paths=("app/build.gradle.kts", "app/src/test/java/com/nullxoid/android/data/api/BackendEndpointTest.kt"),
            command=_android_command(),
            optional=True,
            timeout_seconds=300,
        ),
    ]


def _missing_paths(repo: Path, target: SuiteTestTarget) -> list[str]:
    return [relative for relative in target.required_paths if not (repo / relative).exists()]


def _skip_or_fail(
    target: SuiteTestTarget,
    *,
    repo: Path | None,
    command: list[str],
    reason: str,
    require_all: bool,
) -> SuiteTestResult:
    status = "fail" if require_all else "skip"
    return SuiteTestResult(
        name=target.name,
        description=target.description,
        status=status,
        ok=not require_all,
        optional=target.optional,
        repo=str(repo) if repo else "",
        command=command,
        failure=reason,
    )


def _run_target(root: Path, env: dict[str, str], target: SuiteTestTarget, *, require_all: bool) -> SuiteTestResult:
    repo = _resolve_repo(root, env, target)
    command = _target_command(env, target)
    if repo is None:
        return _skip_or_fail(target, repo=repo, command=command, reason="repo_not_found", require_all=require_all)

    missing = _missing_paths(repo, target)
    if missing:
        return _skip_or_fail(
            target,
            repo=repo,
            command=command,
            reason=f"missing_required_paths:{','.join(missing)}",
            require_all=require_all,
        )

    start = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=repo,
            env=_process_env(root, env, target),
            text=True,
            capture_output=True,
            timeout=target.timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        duration = time.monotonic() - start
        return SuiteTestResult(
            name=target.name,
            description=target.description,
            status="fail",
            ok=False,
            optional=target.optional,
            repo=str(repo),
            command=command,
            returncode=None,
            duration_seconds=duration,
            stdout_tail=_tail(exc.stdout or ""),
            stderr_tail=_tail(exc.stderr or ""),
            failure="timeout",
        )

    duration = time.monotonic() - start
    ok = completed.returncode == 0
    return SuiteTestResult(
        name=target.name,
        description=target.description,
        status="pass" if ok else "fail",
        ok=ok,
        optional=target.optional,
        repo=str(repo),
        command=command,
        returncode=completed.returncode,
        duration_seconds=duration,
        stdout_tail=_tail(completed.stdout),
        stderr_tail=_tail(completed.stderr),
        failure="" if ok else f"exit_{completed.returncode}",
    )


def run_suite_tests(
    *,
    root: Path | None = None,
    env: dict[str, str] | None = None,
    selected_targets: list[str] | None = None,
    include_optional: bool | None = None,
    require_all: bool | None = None,
) -> SuiteTestCatalogResult:
    actual_root = (root or _repo_root()).resolve()
    actual_env = dict(os.environ if env is None else env)
    actual_include_optional = _env_flag(actual_env, "AIBENCHIE_SUITE_TEST_INCLUDE_OPTIONAL")
    if include_optional is not None:
        actual_include_optional = include_optional
    actual_require_all = _env_flag(actual_env, "AIBENCHIE_SUITE_TEST_REQUIRE_ALL")
    if require_all is not None:
        actual_require_all = require_all

    catalog = build_suite_test_catalog()
    by_name = {target.name: target for target in catalog}
    selected = [name for name in (selected_targets or []) if name]
    if selected and "all" not in selected:
        targets = [by_name[name] for name in selected if name in by_name]
    else:
        targets = [target for target in catalog if actual_include_optional or not target.optional]

    results: list[SuiteTestResult] = []
    for name in selected:
        if name != "all" and name not in by_name:
            results.append(
                SuiteTestResult(
                    name=name,
                    description="Unknown suite test target",
                    status="fail",
                    ok=False,
                    optional=False,
                    repo="",
                    command=[],
                    failure="unknown_target",
                )
            )

    for target in targets:
        results.append(_run_target(actual_root, actual_env, target, require_all=actual_require_all))

    return SuiteTestCatalogResult(
        ok=all(result.ok for result in results),
        root=str(actual_root),
        include_optional=actual_include_optional,
        require_all=actual_require_all,
        selected_targets=selected or ["default"],
        targets=targets,
        results=results,
    )


def run_suite_tests_from_env(
    selected_targets: list[str] | None = None,
    *,
    include_optional: bool | None = None,
    require_all: bool | None = None,
) -> SuiteTestCatalogResult:
    return run_suite_tests(
        selected_targets=selected_targets,
        include_optional=include_optional,
        require_all=require_all,
    )
