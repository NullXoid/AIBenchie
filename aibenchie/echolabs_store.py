from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


STORE_SECTIONS = (
    "webCatalog",
    "androidCatalog",
    "windowsCatalog",
    "categoryParity",
    "localImageStudio",
    "approvalRequired",
    "approvedGeneration",
    "deniedGeneration",
    "artifactSandboxing",
    "credentialIsolation",
)

LOCAL_IMAGE_STUDIO = "local-image-studio"
LOCAL_IMAGE_CAPABILITY = "suite.media.image.generate"
LOCAL_IMAGE_ACTION = "media.image.generate.local"
CREATIVE_WORKFLOWS = "Creative Workflows"

FORBIDDEN_CLIENT_MARKERS = (
    "CREATIVE_PROVIDER_BASE_URL",
    "CREATIVE_OUTPUT_DIR",
    "NULLBRIDGE_SERVICE_TOKEN",
    "provider-token",
    "service-token",
    "raw workflow",
    "private artifact path",
    "private_artifact_path",
    "M36_CANARY_SECRET_PROMPT_EDITOR_001",
    "M36_CANARY_NULLBRIDGE_SERVICE_TOKEN_001",
)


@dataclass(frozen=True)
class StoreGateCheck:
    status: str
    evidence: list[str]
    failures: list[str]

    @property
    def ok(self) -> bool:
        return self.status == "passed" and not self.failures

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": self.status,
            "evidence": self.evidence,
        }
        if self.failures:
            payload["failures"] = self.failures
        return payload


@dataclass(frozen=True)
class EchoLabsStoreResult:
    ok: bool
    blocking_failures: list[str]
    gates: dict[str, StoreGateCheck]
    repos: dict[str, str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "blockingFailures": self.blocking_failures,
            "echolabsStore": {name: gate.as_dict() for name, gate in self.gates.items()},
            "repos": self.repos,
        }


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _find_repo(env: dict[str, str], env_key: str, candidates: Iterable[str]) -> Path | None:
    configured = env.get(env_key, "").strip()
    roots: list[Path] = []
    if configured:
        roots.append(Path(configured).expanduser())
    base = repo_root()
    for candidate in candidates:
        path = Path(candidate)
        roots.append(path if path.is_absolute() else (base / path).resolve())
        roots.append(path if path.is_absolute() else (base.parent / path).resolve())
    for root in roots:
        if root.exists():
            return root.resolve()
    return None


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") if path.is_file() else ""


def _scan_files(paths: Iterable[Path], markers: Iterable[str] = FORBIDDEN_CLIENT_MARKERS) -> list[str]:
    findings: list[str] = []
    for path in paths:
        if not path.is_file():
            continue
        text = _read(path).lower()
        for marker in markers:
            if marker.lower() in text:
                findings.append(f"{path.name}:{marker}")
    return sorted(findings)


def _has_all(text: str, values: Iterable[str]) -> list[str]:
    return [value for value in values if value not in text]


def _gate(status: bool, evidence: list[str], failures: list[str] | None = None) -> StoreGateCheck:
    actual_failures = failures or []
    return StoreGateCheck(status="passed" if status and not actual_failures else "failed", evidence=evidence, failures=actual_failures)


def run_echolabs_store_check(env: dict[str, str] | None = None) -> EchoLabsStoreResult:
    source = dict(os.environ if env is None else env)
    wrapper = _find_repo(source, "AIBENCHIE_NULLXOID_WRAPPER_REPO", ("../Felnx/NullXoid/.NullXoid", "../.NullXoid"))
    android = _find_repo(source, "AIBENCHIE_ANDROID_REPO", ("../NullXoidAndroid", "NullXoidAndroid"))
    windows = _find_repo(source, "AIBENCHIE_WINDOWS_REPO", ("../AiAssistant", "AiAssistant"))

    repos = {
        "wrapper": str(wrapper or ""),
        "android": str(android or ""),
        "windows": str(windows or ""),
    }
    gates: dict[str, StoreGateCheck] = {}

    wrapper_catalog = _read(wrapper / "backend" / "store_catalog.py") if wrapper else ""
    wrapper_service = _read(wrapper / "backend" / "store_service.py") if wrapper else ""
    wrapper_ui = _read(wrapper / "frontend" / "src" / "App.jsx") if wrapper else ""
    wrapper_test = _read(wrapper / "backend" / "tests" / "test_store_alpha.py") if wrapper else ""
    android_models = _read(android / "app" / "src" / "main" / "java" / "com" / "nullxoid" / "android" / "data" / "model" / "Models.kt") if android else ""
    android_screen = _read(android / "app" / "src" / "main" / "java" / "com" / "nullxoid" / "android" / "ui" / "store" / "StoreScreen.kt") if android else ""
    android_test = _read(android / "app" / "src" / "test" / "java" / "com" / "nullxoid" / "android" / "data" / "model" / "StoreCatalogContractTest.kt") if android else ""
    windows_adapter = _read(windows / "src" / "bridge" / "echolabs_store_adapter.cpp") + _read(windows / "src" / "bridge" / "echolabs_store_adapter.h") if windows else ""
    windows_test = _read(windows / "tests" / "unit" / "echolabs_store_adapter_test.cpp") if windows else ""

    web_missing = _has_all(
        wrapper_catalog + wrapper_service + wrapper_ui,
        [LOCAL_IMAGE_STUDIO, LOCAL_IMAGE_CAPABILITY, LOCAL_IMAGE_ACTION, CREATIVE_WORKFLOWS, "/api/store/catalog"],
    )
    gates["webCatalog"] = _gate(
        wrapper is not None and not web_missing,
        ["wrapper backend/store_catalog.py", "wrapper frontend/src/App.jsx"],
        [f"WEB_CATALOG_MISSING:{item}" for item in web_missing],
    )

    android_missing = _has_all(
        android_models + android_screen + android_test,
        [LOCAL_IMAGE_STUDIO, LOCAL_IMAGE_CAPABILITY, LOCAL_IMAGE_ACTION, CREATIVE_WORKFLOWS],
    )
    gates["androidCatalog"] = _gate(
        android is not None and not android_missing,
        ["Android Store DTOs", "Android StoreScreen", "Android StoreCatalogContractTest"],
        [f"ANDROID_CATALOG_MISSING:{item}" for item in android_missing],
    )

    windows_missing = _has_all(
        windows_adapter + windows_test,
        [LOCAL_IMAGE_STUDIO, LOCAL_IMAGE_CAPABILITY, CREATIVE_WORKFLOWS, "EchoLabsStoreAdapter"],
    )
    gates["windowsCatalog"] = _gate(
        windows is not None and not windows_missing,
        ["Windows src/bridge/echolabs_store_adapter.*", "Windows tests/unit/echolabs_store_adapter_test.cpp"],
        [f"WINDOWS_CATALOG_MISSING:{item}" for item in windows_missing],
    )

    parity_failures = []
    for platform, text in (("web", wrapper_catalog + wrapper_ui), ("android", android_models + android_screen), ("windows", windows_adapter + windows_test)):
        if CREATIVE_WORKFLOWS not in text:
            parity_failures.append(f"CATEGORY_PARITY_MISSING:{platform}")
        if LOCAL_IMAGE_STUDIO not in text:
            parity_failures.append(f"ADDON_PARITY_MISSING:{platform}")
    gates["categoryParity"] = _gate(not parity_failures, ["shared category/add-on strings across wrapper, Android, Windows"], parity_failures)

    gates["localImageStudio"] = _gate(
        all(marker in wrapper_catalog for marker in (LOCAL_IMAGE_STUDIO, "Local Image Studio", "local-debug", "web", "android", "windows")),
        ["safe Local Image Studio manifest"],
        [] if wrapper_catalog else ["LOCAL_IMAGE_STUDIO_MANIFEST_MISSING"],
    )

    gates["approvalRequired"] = _gate(
        "requiresApproval" in wrapper_catalog and "submit_approval_route" in wrapper_service,
        ["wrapper store manifest requires approval", "wrapper store_service submits NullBridge approval route"],
        [] if "submit_approval_route" in wrapper_service else ["APPROVAL_ROUTE_NOT_USED"],
    )

    gates["approvedGeneration"] = _gate(
        "approved_generation_calls_mock_provider_once" in wrapper_test and "provider.submitJob" in wrapper_service,
        ["backend/tests/test_store_alpha.py approved_calls_provider_once", "backend/store_service.py provider submit"],
        [] if "approved_generation_calls_mock_provider_once" in wrapper_test else ["APPROVED_GENERATION_TEST_MISSING"],
    )

    denial_required = ["denied_expired_pending_approval_does_not_call_provider", "unsupported_capability_denies"]
    denial_missing = [name for name in denial_required if name not in wrapper_test]
    gates["deniedGeneration"] = _gate(
        not denial_missing,
        ["backend/tests/test_store_alpha.py denied/expired/unsupported tests"],
        [f"DENIED_GENERATION_TEST_MISSING:{name}" for name in denial_missing],
    )

    artifact_failures = []
    if "thumbnailUrl" not in wrapper_service or "artifactId" not in wrapper_service:
        artifact_failures.append("SANITIZED_GALLERY_FIELDS_MISSING")
    if (
        "private path" not in wrapper_test.lower()
        and "private artifact path" not in wrapper_test.lower()
        and "filesystem" not in wrapper_test.lower()
    ):
        artifact_failures.append("PRIVATE_PATH_ASSERTION_MISSING")
    gates["artifactSandboxing"] = _gate(
        not artifact_failures,
        ["backend/store_service.py safe gallery", "backend/tests/test_store_alpha.py private path assertions"],
        artifact_failures,
    )

    client_files = []
    if wrapper:
        client_files.extend([wrapper / "frontend" / "src" / "App.jsx"])
    if android:
        client_files.extend(
            [
                android / "app" / "src" / "main" / "java" / "com" / "nullxoid" / "android" / "data" / "model" / "Models.kt",
                android / "app" / "src" / "main" / "java" / "com" / "nullxoid" / "android" / "ui" / "store" / "StoreScreen.kt",
                android / "app" / "src" / "main" / "java" / "com" / "nullxoid" / "android" / "backend" / "routes" / "Routes.kt",
            ]
        )
    if windows:
        client_files.extend(
            [
                windows / "src" / "bridge" / "echolabs_store_adapter.cpp",
                windows / "src" / "bridge" / "echolabs_store_adapter.h",
            ]
        )
    leaks = _scan_files(client_files)
    gates["credentialIsolation"] = _gate(
        not leaks and "do_not_leak_fake_prompt_or_provider_secrets" in wrapper_test,
        ["client-safe surface marker scan", "backend fake prompt/provider secret leak test"],
        [f"STORE_CLIENT_LEAK:{item}" for item in leaks]
        + ([] if "do_not_leak_fake_prompt_or_provider_secrets" in wrapper_test else ["FAKE_SECRET_LEAK_TEST_MISSING"]),
    )

    blocking = [
        f"{name}:{failure}"
        for name, gate in gates.items()
        for failure in gate.failures
    ]
    return EchoLabsStoreResult(
        ok=not blocking and set(gates) == set(STORE_SECTIONS),
        blocking_failures=blocking,
        gates=gates,
        repos=repos,
    )


def run_from_env() -> EchoLabsStoreResult:
    return run_echolabs_store_check()
