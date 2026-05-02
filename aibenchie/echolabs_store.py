from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
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
    "realProviderSmoke",
    "localVideoStudio",
    "local3DStudio",
    "videoApprovalRequired",
    "model3DApprovalRequired",
    "videoApprovedGeneration",
    "model3DApprovedGeneration",
    "videoDeniedGeneration",
    "model3DDeniedGeneration",
    "videoArtifactSandboxing",
    "model3DArtifactSandboxing",
    "realProviderSmoke.video",
    "realProviderSmoke.model3d",
    "storeAssistant.contextEndpoint",
    "storeAssistant.groundingPrompt",
    "storeAssistant.noHostedCloudFalseClaim",
    "storeAssistant.secretLeakCheck",
)

LOCAL_IMAGE_STUDIO = "local-image-studio"
LOCAL_IMAGE_CAPABILITY = "suite.media.image.generate"
LOCAL_IMAGE_ACTION = "media.image.generate.local"
LOCAL_VIDEO_STUDIO = "local-video-studio"
LOCAL_VIDEO_CAPABILITY = "suite.media.video.generate"
LOCAL_VIDEO_ACTION = "media.video.generate.local"
LOCAL_3D_STUDIO = "local-3d-studio"
LOCAL_3D_CAPABILITY = "suite.media.model3d.generate"
LOCAL_3D_ACTION = "media.model3d.generate.local"
CREATIVE_WORKFLOWS = "Creative Workflows"
STORE_ADDONS = {
    LOCAL_IMAGE_STUDIO: ("Local Image Studio", LOCAL_IMAGE_CAPABILITY, LOCAL_IMAGE_ACTION),
    LOCAL_VIDEO_STUDIO: ("Local Video Studio", LOCAL_VIDEO_CAPABILITY, LOCAL_VIDEO_ACTION),
    LOCAL_3D_STUDIO: ("Local 3D Studio", LOCAL_3D_CAPABILITY, LOCAL_3D_ACTION),
}

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
    warnings: list[str] | None = None
    required: bool | None = None
    configured: bool | None = None
    provider_kind: str | None = None
    error_code: str = ""

    @property
    def ok(self) -> bool:
        return self.status in {"passed", "skipped", "failed_non_blocking"} and not self.failures

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": self.status,
            "evidence": self.evidence,
        }
        if self.failures:
            payload["failures"] = self.failures
        if self.warnings:
            payload["warnings"] = self.warnings
        if self.required is not None:
            payload["required"] = self.required
        if self.configured is not None:
            payload["configured"] = self.configured
        if self.provider_kind:
            payload["providerKind"] = self.provider_kind
        if self.error_code:
            payload["errorCode"] = self.error_code
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


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _provider_kind(raw: str) -> str:
    normalized = (raw or "mock").strip().lower().replace("_", "-")
    if normalized in {"", "mock", "test"}:
        return "mock"
    if normalized in {"local", "local-image", "local-image-engine", "real", "comfyui", "ltx"}:
        return "local-image-engine"
    return normalized


def _provider_health(base_url: str, timeout_seconds: float = 3.0) -> tuple[bool, str]:
    if not base_url:
        return False, "PROVIDER_NOT_CONFIGURED"
    url = base_url.rstrip("/") + "/"
    try:
        request = urllib.request.Request(url, method="GET", headers={"Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return response.status < 500, "" if response.status < 500 else "PROVIDER_UNAVAILABLE"
    except (OSError, urllib.error.URLError, urllib.error.HTTPError):
        return False, "PROVIDER_UNAVAILABLE"


def _real_provider_smoke_gate(source: dict[str, str], wrapper: Path | None) -> StoreGateCheck:
    provider_kind = _provider_kind(source.get("CREATIVE_PROVIDER", "mock"))
    required = _truthy(source.get("CREATIVE_REAL_PROVIDER_SMOKE_REQUIRED", ""))
    base_url = str(source.get("CREATIVE_PROVIDER_BASE_URL", "") or "").strip()
    configured = provider_kind != "mock" and bool(base_url)
    evidence = ["backend-only real provider smoke config"]

    creative_provider_source = _read(wrapper / "backend" / "creative_provider.py") if wrapper else ""
    missing_markers = [
        marker
        for marker in ("provider_config_from_env", "LocalImageEngineProvider", "CREATIVE_REAL_PROVIDER_SMOKE_REQUIRED")
        if marker not in creative_provider_source
    ]
    if wrapper:
        evidence.append("wrapper backend/creative_provider.py")
    if missing_markers:
        return StoreGateCheck(
            status="failed_blocking",
            evidence=evidence,
            failures=[f"REAL_PROVIDER_SMOKE_SOURCE_MISSING:{marker}" for marker in missing_markers],
            required=required,
            configured=configured,
            provider_kind="local-image-engine",
            error_code="REAL_PROVIDER_SOURCE_MISSING",
        )

    if not configured:
        return StoreGateCheck(
            status="skipped",
            evidence=evidence,
            failures=[],
            required=required,
            configured=False,
            provider_kind="local-image-engine",
        )

    ok, error_code = _provider_health(base_url)
    if ok:
        return StoreGateCheck(
            status="passed",
            evidence=[*evidence, "redacted provider health probe"],
            failures=[],
            required=required,
            configured=True,
            provider_kind="local-image-engine",
        )

    status = "failed_blocking" if required else "failed_non_blocking"
    return StoreGateCheck(
        status=status,
        evidence=[*evidence, "redacted provider health probe"],
        failures=[error_code] if required else [],
        warnings=[] if required else [error_code],
        required=required,
        configured=True,
        provider_kind="local-image-engine",
        error_code=error_code,
    )


def _optional_media_provider_smoke_gate(provider_kind: str) -> StoreGateCheck:
    return StoreGateCheck(
        status="skipped",
        evidence=[f"optional {provider_kind} smoke is non-blocking by default"],
        failures=[],
        required=False,
        configured=False,
        provider_kind=provider_kind,
    )


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
    wrapper_main = _read(wrapper / "backend" / "main.py") if wrapper else ""
    wrapper_service = _read(wrapper / "backend" / "store_service.py") if wrapper else ""
    wrapper_ui = _read(wrapper / "frontend" / "src" / "App.jsx") if wrapper else ""
    wrapper_store_prompt = _read(wrapper / "frontend" / "src" / "lib" / "storeAssistantPrompt.js") if wrapper else ""
    wrapper_test = _read(wrapper / "backend" / "tests" / "test_store_alpha.py") if wrapper else ""
    android_models = _read(android / "app" / "src" / "main" / "java" / "com" / "nullxoid" / "android" / "data" / "model" / "Models.kt") if android else ""
    android_screen = _read(android / "app" / "src" / "main" / "java" / "com" / "nullxoid" / "android" / "ui" / "store" / "StoreScreen.kt") if android else ""
    android_test = _read(android / "app" / "src" / "test" / "java" / "com" / "nullxoid" / "android" / "data" / "model" / "StoreCatalogContractTest.kt") if android else ""
    windows_adapter = _read(windows / "src" / "bridge" / "echolabs_store_adapter.cpp") + _read(windows / "src" / "bridge" / "echolabs_store_adapter.h") if windows else ""
    windows_test = _read(windows / "tests" / "unit" / "echolabs_store_adapter_test.cpp") if windows else ""

    web_missing = _has_all(
        wrapper_catalog + wrapper_service + wrapper_ui,
        [
            LOCAL_IMAGE_STUDIO,
            LOCAL_IMAGE_CAPABILITY,
            LOCAL_IMAGE_ACTION,
            LOCAL_VIDEO_STUDIO,
            LOCAL_VIDEO_CAPABILITY,
            LOCAL_VIDEO_ACTION,
            LOCAL_3D_STUDIO,
            LOCAL_3D_CAPABILITY,
            LOCAL_3D_ACTION,
            CREATIVE_WORKFLOWS,
            "/api/store/catalog",
        ],
    )
    gates["webCatalog"] = _gate(
        wrapper is not None and not web_missing,
        ["wrapper backend/store_catalog.py", "wrapper frontend/src/App.jsx"],
        [f"WEB_CATALOG_MISSING:{item}" for item in web_missing],
    )

    android_missing = _has_all(
        android_models + android_screen + android_test,
        [
            LOCAL_IMAGE_STUDIO,
            LOCAL_IMAGE_CAPABILITY,
            LOCAL_IMAGE_ACTION,
            LOCAL_VIDEO_STUDIO,
            LOCAL_VIDEO_CAPABILITY,
            LOCAL_VIDEO_ACTION,
            LOCAL_3D_STUDIO,
            LOCAL_3D_CAPABILITY,
            LOCAL_3D_ACTION,
            CREATIVE_WORKFLOWS,
        ],
    )
    gates["androidCatalog"] = _gate(
        android is not None and not android_missing,
        ["Android Store DTOs", "Android StoreScreen", "Android StoreCatalogContractTest"],
        [f"ANDROID_CATALOG_MISSING:{item}" for item in android_missing],
    )

    windows_missing = _has_all(
        windows_adapter + windows_test,
        [
            LOCAL_IMAGE_STUDIO,
            LOCAL_IMAGE_CAPABILITY,
            LOCAL_VIDEO_STUDIO,
            LOCAL_VIDEO_CAPABILITY,
            LOCAL_3D_STUDIO,
            LOCAL_3D_CAPABILITY,
            CREATIVE_WORKFLOWS,
            "EchoLabsStoreAdapter",
        ],
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
        for addon_id in STORE_ADDONS:
            if addon_id not in text:
                parity_failures.append(f"ADDON_PARITY_MISSING:{platform}:{addon_id}")
    gates["categoryParity"] = _gate(not parity_failures, ["shared category/add-on strings across wrapper, Android, Windows"], parity_failures)

    gates["localImageStudio"] = _gate(
        all(marker in wrapper_catalog for marker in (LOCAL_IMAGE_STUDIO, "Local Image Studio", "local-debug", "web", "android", "windows")),
        ["safe Local Image Studio manifest"],
        [] if wrapper_catalog else ["LOCAL_IMAGE_STUDIO_MANIFEST_MISSING"],
    )

    gates["localVideoStudio"] = _gate(
        all(marker in wrapper_catalog for marker in (LOCAL_VIDEO_STUDIO, "Local Video Studio", LOCAL_VIDEO_CAPABILITY, LOCAL_VIDEO_ACTION, "mock-video", "local-video-engine")),
        ["safe Local Video Studio manifest"],
        [] if wrapper_catalog else ["LOCAL_VIDEO_STUDIO_MANIFEST_MISSING"],
    )

    gates["local3DStudio"] = _gate(
        all(marker in wrapper_catalog for marker in (LOCAL_3D_STUDIO, "Local 3D Studio", LOCAL_3D_CAPABILITY, LOCAL_3D_ACTION, "mock-3d", "local-3d-engine", "glb", "gltf")),
        ["safe Local 3D Studio manifest with GLB/glTF metadata"],
        [] if wrapper_catalog else ["LOCAL_3D_STUDIO_MANIFEST_MISSING"],
    )

    gates["approvalRequired"] = _gate(
        "requiresApproval" in wrapper_catalog and "submit_approval_route" in wrapper_service,
        ["wrapper store manifest requires approval", "wrapper store_service submits NullBridge approval route"],
        [] if "submit_approval_route" in wrapper_service else ["APPROVAL_ROUTE_NOT_USED"],
    )

    gates["videoApprovalRequired"] = _gate(
        LOCAL_VIDEO_CAPABILITY in wrapper_catalog and "submit_approval_route" in wrapper_service,
        ["Local Video Studio approval-gated manifest", "shared store_service approval path"],
        [] if LOCAL_VIDEO_CAPABILITY in wrapper_catalog else ["VIDEO_APPROVAL_MANIFEST_MISSING"],
    )

    gates["model3DApprovalRequired"] = _gate(
        LOCAL_3D_CAPABILITY in wrapper_catalog and "submit_approval_route" in wrapper_service,
        ["Local 3D Studio approval-gated manifest", "shared store_service approval path"],
        [] if LOCAL_3D_CAPABILITY in wrapper_catalog else ["MODEL3D_APPROVAL_MANIFEST_MISSING"],
    )

    gates["approvedGeneration"] = _gate(
        "approved_generation_calls_mock_provider_once" in wrapper_test and "provider.submitJob" in wrapper_service,
        ["backend/tests/test_store_alpha.py approved_calls_provider_once", "backend/store_service.py provider submit"],
        [] if "approved_generation_calls_mock_provider_once" in wrapper_test else ["APPROVED_GENERATION_TEST_MISSING"],
    )

    gates["videoApprovedGeneration"] = _gate(
        "approved_mock_video_and_3d_call_provider_once" in wrapper_test and "mediaKind" in wrapper_service,
        ["backend/tests/test_store_alpha.py video/3D approved provider test", "backend/store_service.py mediaKind provider request"],
        [] if "approved_mock_video_and_3d_call_provider_once" in wrapper_test else ["VIDEO_APPROVED_GENERATION_TEST_MISSING"],
    )

    gates["model3DApprovedGeneration"] = _gate(
        "approved_mock_video_and_3d_call_provider_once" in wrapper_test and "format" in wrapper_service,
        ["backend/tests/test_store_alpha.py video/3D approved provider test", "backend/store_service.py GLB/glTF format request"],
        [] if "approved_mock_video_and_3d_call_provider_once" in wrapper_test else ["MODEL3D_APPROVED_GENERATION_TEST_MISSING"],
    )

    denial_required = ["denied_expired_pending_approval_does_not_call_provider", "unsupported_capability_denies"]
    denial_missing = [name for name in denial_required if name not in wrapper_test]
    gates["deniedGeneration"] = _gate(
        not denial_missing,
        ["backend/tests/test_store_alpha.py denied/expired/unsupported tests"],
        [f"DENIED_GENERATION_TEST_MISSING:{name}" for name in denial_missing],
    )

    video_denial_missing = "denied_video_and_3d_approval_does_not_call_provider" not in wrapper_test
    gates["videoDeniedGeneration"] = _gate(
        not video_denial_missing,
        ["backend/tests/test_store_alpha.py video/3D denied approval test"],
        ["VIDEO_DENIED_GENERATION_TEST_MISSING"] if video_denial_missing else [],
    )
    gates["model3DDeniedGeneration"] = _gate(
        not video_denial_missing,
        ["backend/tests/test_store_alpha.py video/3D denied approval test"],
        ["MODEL3D_DENIED_GENERATION_TEST_MISSING"] if video_denial_missing else [],
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

    gates["videoArtifactSandboxing"] = _gate(
        "posterUrl" in wrapper_catalog + wrapper_service and "durationMs" in wrapper_catalog + wrapper_service,
        ["video gallery safe poster/preview metadata"],
        [] if "posterUrl" in wrapper_catalog + wrapper_service else ["VIDEO_GALLERY_SAFE_FIELDS_MISSING"],
    )
    gates["model3DArtifactSandboxing"] = _gate(
        "modelPreviewUrl" in wrapper_catalog + wrapper_service and "model/gltf-binary" in wrapper_service,
        ["3D gallery safe model preview metadata"],
        [] if "modelPreviewUrl" in wrapper_catalog + wrapper_service else ["MODEL3D_GALLERY_SAFE_FIELDS_MISSING"],
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

    gates["realProviderSmoke"] = _real_provider_smoke_gate(source, wrapper)
    gates["realProviderSmoke.video"] = _optional_media_provider_smoke_gate("local-video-engine")
    gates["realProviderSmoke.model3d"] = _optional_media_provider_smoke_gate("local-3d-engine")

    context_markers = [
        "/api/store/addons/{addon_id}/assistant-context",
        "assistant_context",
        "store-assistant.v1",
        "providerConfigVisibleToClient",
    ]
    context_missing = _has_all(wrapper_main + wrapper_service + wrapper_test, context_markers)
    gates["storeAssistant.contextEndpoint"] = _gate(
        wrapper is not None and not context_missing,
        ["wrapper assistant context endpoint", "backend/tests/test_store_alpha.py assistant context safety"],
        [f"STORE_ASSISTANT_CONTEXT_MISSING:{item}" for item in context_missing],
    )

    prompt_markers = [
        "buildStoreAssistantSystemPrompt",
        "buildLocalImageStudioRequirementsAnswer",
        "buildStoreAddonRequirementsAnswer",
        "Do not invent provider behavior",
        "backend-only provider adapter",
        "NullBridge approval",
        "private artifacts",
        "Local Video Studio",
        "Local 3D Studio",
    ]
    prompt_missing = _has_all(wrapper_ui + wrapper_store_prompt, prompt_markers)
    gates["storeAssistant.groundingPrompt"] = _gate(
        wrapper is not None and not prompt_missing,
        ["frontend Store assistant prompt builder", "frontend Store assistant context wiring"],
        [f"STORE_ASSISTANT_PROMPT_MISSING:{item}" for item in prompt_missing],
    )

    false_claim_failures = []
    if "runs entirely on our servers" in wrapper_store_prompt:
        false_claim_failures.append("STORE_ASSISTANT_HOSTED_FALSE_CLAIM")
    if "unless the Store context explicitly says a remote or cloud provider is active" not in wrapper_store_prompt:
        false_claim_failures.append("STORE_ASSISTANT_REMOTE_CLOUD_GUARD_MISSING")
    if "no local hardware/install" in wrapper_store_prompt:
        false_claim_failures.append("STORE_ASSISTANT_NO_LOCAL_INSTALL_FALSE_CLAIM")
    gates["storeAssistant.noHostedCloudFalseClaim"] = _gate(
        wrapper is not None and not false_claim_failures,
        ["frontend Store assistant hosted/cloud false-claim guard"],
        false_claim_failures,
    )

    assistant_leaks = _scan_files(
        [
            wrapper / "frontend" / "src" / "App.jsx",
            wrapper / "frontend" / "src" / "lib" / "storeAssistantPrompt.js",
        ]
        if wrapper
        else []
    )
    gates["storeAssistant.secretLeakCheck"] = _gate(
        not assistant_leaks and "test_store_assistant_context_returns_safe_grounding_without_backend_secrets" in wrapper_test,
        ["Store assistant safe context and frontend prompt marker scan"],
        [f"STORE_ASSISTANT_LEAK:{item}" for item in assistant_leaks]
        + (
            []
            if "test_store_assistant_context_returns_safe_grounding_without_backend_secrets" in wrapper_test
            else ["STORE_ASSISTANT_BACKEND_LEAK_TEST_MISSING"]
        ),
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
