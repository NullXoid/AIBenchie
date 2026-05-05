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
    "androidOutOfNetwork.asyncJobs",
    "androidOutOfNetwork.connectorRegistration",
    "androidOutOfNetwork.approvedImageGeneration",
    "androidOutOfNetwork.approvedVideoGeneration",
    "androidOutOfNetwork.nonAdminSelfApprovalDenied",
    "androidOutOfNetwork.adminSamePhoneApprovalAllowed",
    "androidOutOfNetwork.artifactDownload",
    "androidOutOfNetwork.saveToDevice",
    "androidOutOfNetwork.credentialIsolation",
    "timedApproval.thisJob",
    "timedApproval.timedGrant",
    "timedApproval.matchingImageSkipsApproval",
    "timedApproval.videoThisJob",
    "timedApproval.videoTimedGrant",
    "timedApproval.matchingVideoSkipsApproval",
    "timedApproval.videoGrantDoesNotAuthorizeImage",
    "timedApproval.videoGrantDoesNotAuthorize3D",
    "timedApproval.videoAudioArtifactIsolation",
    "timedApproval.crossCapabilityDenied",
    "timedApproval.expiredGrantRequiresApproval",
    "timedApproval.replayDoesNotExtendGrant",
    "timedApproval.revokeGrant",
    "timedApproval.revokedGrantRequiresApproval",
    "timedApproval.grantUpdate",
    "timedApproval.grantUpdatePreservesScope",
    "timedApproval.revokedGrantUpdateDenied",
    "timedApproval.grantListSafeMetadata",
    "timedApproval.chatGrantLabeling",
    "timedApproval.safeRequesterServiceMetadata",
    "timedApproval.credentialIsolation",
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


def _safe_public_id(value: str, prefix: str = "") -> bool:
    raw = value.strip()
    if prefix and not raw.startswith(prefix):
        return False
    return bool(raw) and all(ch.isalnum() or ch in {"-", "_"} for ch in raw)


def _android_video_e2e_gate(source: dict[str, str]) -> StoreGateCheck:
    status = source.get("AIBENCHIE_ANDROID_VIDEO_E2E_STATUS", "").strip().lower()
    if not status:
        return StoreGateCheck(
            status="skipped",
            evidence=["real Android video provider E2E remains optional; mock video Store baseline is covered"],
            failures=[],
            warnings=["ANDROID_OON_VIDEO_REAL_PROVIDER_SKIPPED"],
            required=False,
            configured=False,
            provider_kind="local-video-engine",
        )

    store_job_id = source.get("AIBENCHIE_ANDROID_VIDEO_E2E_STORE_JOB_ID", "")
    artifact_id = source.get("AIBENCHIE_ANDROID_VIDEO_E2E_ARTIFACT_ID", "")
    mime_type = source.get("AIBENCHIE_ANDROID_VIDEO_E2E_MIME", "")
    saved_to_device = _truthy(source.get("AIBENCHIE_ANDROID_VIDEO_E2E_SAVED_TO_DEVICE", ""))
    player_opened = _truthy(source.get("AIBENCHIE_ANDROID_VIDEO_E2E_PLAYER", ""))
    failures: list[str] = []
    if status != "passed":
        failures.append("ANDROID_OON_VIDEO_E2E_NOT_PASSED")
    if not _safe_public_id(store_job_id, "storejob-"):
        failures.append("ANDROID_OON_VIDEO_E2E_STORE_JOB_ID_INVALID")
    if not _safe_public_id(artifact_id):
        failures.append("ANDROID_OON_VIDEO_E2E_ARTIFACT_ID_INVALID")
    if not mime_type.startswith("video/"):
        failures.append("ANDROID_OON_VIDEO_E2E_MIME_INVALID")
    if not player_opened:
        failures.append("ANDROID_OON_VIDEO_E2E_PLAYER_NOT_CONFIRMED")
    if not saved_to_device:
        failures.append("ANDROID_OON_VIDEO_E2E_SAVE_NOT_CONFIRMED")

    if failures:
        return StoreGateCheck(
            status="failed_non_blocking",
            evidence=["manual hosted Android video E2E evidence was supplied but incomplete"],
            failures=[],
            warnings=failures,
            required=False,
            configured=True,
            provider_kind="local-video-engine",
        )

    return StoreGateCheck(
        status="passed",
        evidence=[
            "manual hosted Android video E2E completed",
            "server NullBridge approval, connector execution, gallery, player, and MediaStore save verified",
        ],
        failures=[],
        required=False,
        configured=True,
        provider_kind="local-video-engine",
    )


def run_echolabs_store_check(env: dict[str, str] | None = None) -> EchoLabsStoreResult:
    source = dict(os.environ if env is None else env)
    wrapper = _find_repo(source, "AIBENCHIE_NULLXOID_WRAPPER_REPO", ("../Felnx/NullXoid/.NullXoid", "../.NullXoid"))
    nullbridge = _find_repo(source, "AIBENCHIE_NULLBRIDGE_REPO", ("../NullBridge", "NullBridge"))
    android = _find_repo(source, "AIBENCHIE_ANDROID_REPO", ("../NullXoidAndroid", "NullXoidAndroid"))
    windows = _find_repo(source, "AIBENCHIE_WINDOWS_REPO", ("../AiAssistant", "AiAssistant"))

    repos = {
        "wrapper": str(wrapper or ""),
        "nullbridge": str(nullbridge or ""),
        "android": str(android or ""),
        "windows": str(windows or ""),
    }
    gates: dict[str, StoreGateCheck] = {}

    wrapper_catalog = _read(wrapper / "backend" / "store_catalog.py") if wrapper else ""
    wrapper_main = _read(wrapper / "backend" / "main.py") if wrapper else ""
    wrapper_service = _read(wrapper / "backend" / "store_service.py") if wrapper else ""
    wrapper_jobs = _read(wrapper / "backend" / "store_jobs.py") if wrapper else ""
    wrapper_ui = _read(wrapper / "frontend" / "src" / "App.jsx") if wrapper else ""
    wrapper_store_prompt = _read(wrapper / "frontend" / "src" / "lib" / "storeAssistantPrompt.js") if wrapper else ""
    wrapper_test = _read(wrapper / "backend" / "tests" / "test_store_alpha.py") if wrapper else ""
    wrapper_async_test = _read(wrapper / "backend" / "tests" / "test_store_async_jobs.py") if wrapper else ""
    nullbridge_api = _read(nullbridge / "backend" / "scripts" / "nullbridge_api.py") if nullbridge else ""
    nullbridge_tests = _read(nullbridge / "backend" / "tests" / "test_nullbridge_generic_approval_routing.py") if nullbridge else ""
    nullbridge_android_api = _read(nullbridge / "frontend" / "app" / "src" / "main" / "java" / "com" / "nullxoid" / "nullbridge" / "data" / "remote" / "NullBridgeApi.kt") if nullbridge else ""
    nullbridge_android_dtos = _read(nullbridge / "frontend" / "app" / "src" / "main" / "java" / "com" / "nullxoid" / "nullbridge" / "data" / "remote" / "NullBridgeDtos.kt") if nullbridge else ""
    nullbridge_android_models = _read(nullbridge / "frontend" / "app" / "src" / "main" / "java" / "com" / "nullxoid" / "nullbridge" / "domain" / "NullBridgeModels.kt") if nullbridge else ""
    nullbridge_android_repo = _read(nullbridge / "frontend" / "app" / "src" / "main" / "java" / "com" / "nullxoid" / "nullbridge" / "data" / "repository" / "NullBridgeRepositoryImpl.kt") if nullbridge else ""
    nullbridge_android_permissions = _read(nullbridge / "frontend" / "app" / "src" / "main" / "java" / "com" / "nullxoid" / "nullbridge" / "presentation" / "PermissionsComponents.kt") if nullbridge else ""
    nullbridge_android_formatters = _read(nullbridge / "frontend" / "app" / "src" / "main" / "java" / "com" / "nullxoid" / "nullbridge" / "presentation" / "GrantUiFormatters.kt") if nullbridge else ""
    android_models = _read(android / "app" / "src" / "main" / "java" / "com" / "nullxoid" / "android" / "data" / "model" / "Models.kt") if android else ""
    android_api = _read(android / "app" / "src" / "main" / "java" / "com" / "nullxoid" / "android" / "data" / "api" / "NullXoidApi.kt") if android else ""
    android_repo = _read(android / "app" / "src" / "main" / "java" / "com" / "nullxoid" / "android" / "data" / "repo" / "NullXoidRepository.kt") if android else ""
    android_settings = _read(android / "app" / "src" / "main" / "java" / "com" / "nullxoid" / "android" / "data" / "prefs" / "SettingsStore.kt") if android else ""
    android_vm = _read(android / "app" / "src" / "main" / "java" / "com" / "nullxoid" / "android" / "ui" / "NullXoidViewModel.kt") if android else ""
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

    async_markers = [
        "STORE_JOB_STATES",
        "pending_approval",
        "queued_connector",
        "running_provider",
        "uploading_artifact",
        "/api/store/jobs/{store_job_id}",
        "storeJobId",
    ]
    async_missing = _has_all(wrapper_jobs + wrapper_main + wrapper_service + android_models + android_api + android_vm, async_markers)
    gates["androidOutOfNetwork.asyncJobs"] = _gate(
        not async_missing and "test_async_store_action_returns_store_job_without_provider_execution" in wrapper_async_test,
        ["wrapper async Store job contract", "Android Store job DTO/API/polling"],
        [f"ANDROID_OON_ASYNC_MISSING:{item}" for item in async_missing]
        + (
            []
            if "test_async_store_action_returns_store_job_without_provider_execution" in wrapper_async_test
            else ["ANDROID_OON_ASYNC_TEST_MISSING"]
        ),
    )

    connector_markers = [
        "/api/creative-worker/register",
        "/api/creative-worker/heartbeat",
        "/api/creative-worker/jobs/next",
        "/api/creative-worker/jobs/{store_job_id}/claim",
        "/api/creative-worker/jobs/{store_job_id}/artifact",
        "/api/creative-worker/jobs/{store_job_id}/complete",
        "/api/creative-worker/jobs/{store_job_id}/fail",
        "lease_job",
    ]
    connector_missing = _has_all(wrapper_main + wrapper_service + wrapper_jobs, connector_markers)
    gates["androidOutOfNetwork.connectorRegistration"] = _gate(
        not connector_missing and "test_connector_claim_upload_complete_produces_sanitized_gallery" in wrapper_async_test,
        ["Creative Worker Connector polling endpoints", "connector lease/upload/complete test"],
        [f"CREATIVE_WORKER_CONNECTOR_MISSING:{item}" for item in connector_missing]
        + (
            []
            if "test_connector_claim_upload_complete_produces_sanitized_gallery" in wrapper_async_test
            else ["CREATIVE_WORKER_CONNECTOR_TEST_MISSING"]
        ),
    )

    gates["androidOutOfNetwork.approvedImageGeneration"] = _gate(
        "test_connector_claim_upload_complete_produces_sanitized_gallery" in wrapper_async_test
        and LOCAL_IMAGE_CAPABILITY in wrapper_async_test,
        ["approved image job connector E2E contract"],
        [] if LOCAL_IMAGE_CAPABILITY in wrapper_async_test else ["ANDROID_OON_IMAGE_APPROVAL_TEST_MISSING"],
    )

    gates["androidOutOfNetwork.approvedVideoGeneration"] = _android_video_e2e_gate(source)

    gates["androidOutOfNetwork.nonAdminSelfApprovalDenied"] = _gate(
        "test_non_admin_self_approval_is_rejected_but_admin_same_phone_is_allowed" in wrapper_async_test
        and "REQUESTER_NOT_AUTHORIZED" in wrapper_service + wrapper_async_test,
        ["non-admin self-approval denial policy test"],
        []
        if "test_non_admin_self_approval_is_rejected_but_admin_same_phone_is_allowed" in wrapper_async_test
        else ["NON_ADMIN_SELF_APPROVAL_TEST_MISSING"],
    )

    gates["androidOutOfNetwork.adminSamePhoneApprovalAllowed"] = _gate(
        "test_non_admin_self_approval_is_rejected_but_admin_same_phone_is_allowed" in wrapper_async_test
        and '"admin"' in wrapper_service + wrapper_async_test,
        ["admin same-phone approval policy test"],
        []
        if "test_non_admin_self_approval_is_rejected_but_admin_same_phone_is_allowed" in wrapper_async_test
        else ["ADMIN_SAME_PHONE_APPROVAL_TEST_MISSING"],
    )

    artifact_download_missing = _has_all(android_api + android_repo, ["getBytes", "/artifacts/$artifactId", "storeArtifactBytes"])
    gates["androidOutOfNetwork.artifactDownload"] = _gate(
        not artifact_download_missing,
        ["Android authenticated artifact download path"],
        [f"ANDROID_ARTIFACT_DOWNLOAD_MISSING:{item}" for item in artifact_download_missing],
    )

    save_missing = _has_all(android_vm + android_screen, ["saveStoreArtifactToDevice", "MediaStore", "Save to device"])
    gates["androidOutOfNetwork.saveToDevice"] = _gate(
        not save_missing,
        ["Android MediaStore save-to-device action"],
        [f"ANDROID_SAVE_TO_DEVICE_MISSING:{item}" for item in save_missing],
    )

    android_oon_leaks = _scan_files(
        [
            android / "app" / "src" / "main" / "java" / "com" / "nullxoid" / "android" / "data" / "model" / "Models.kt",
            android / "app" / "src" / "main" / "java" / "com" / "nullxoid" / "android" / "ui" / "NullXoidViewModel.kt",
            android / "app" / "src" / "main" / "java" / "com" / "nullxoid" / "android" / "ui" / "store" / "StoreScreen.kt",
        ]
        if android
        else []
    )
    gates["androidOutOfNetwork.credentialIsolation"] = _gate(
        not android_oon_leaks and "CREATIVE_WORKER_TOKEN" not in android_models + android_api + android_repo + android_vm + android_screen,
        ["Android out-of-network client surface credential scan"],
        [f"ANDROID_OON_LEAK:{item}" for item in android_oon_leaks]
        + (
            []
            if "CREATIVE_WORKER_TOKEN" not in android_models + android_api + android_repo + android_vm + android_screen
            else ["ANDROID_CREATIVE_WORKER_TOKEN_LEAK"]
        ),
    )

    timed_source = nullbridge_api + nullbridge_tests + wrapper_service + wrapper_async_test
    gates["timedApproval.thisJob"] = _gate(
        '"once"' in nullbridge_api
        and "assert list(api.APPROVAL_GRANTS.glob(\"grant-*.json\")) == []" in nullbridge_tests,
        ["per-job approval does not create reusable grant"],
        [] if nullbridge else ["NULLBRIDGE_REPO_MISSING"],
    )
    gates["timedApproval.timedGrant"] = _gate(
        all(marker in timed_source for marker in ["8h", "24h", "30d", "durationSeconds", "approval_grant_created"]),
        ["8h/24h/30d timed approval source and tests"],
        [f"TIMED_GRANT_MARKER_MISSING:{marker}" for marker in ["8h", "24h", "30d"] if marker not in timed_source],
    )
    gates["timedApproval.matchingImageSkipsApproval"] = _gate(
        "approvalSource" in wrapper_service + wrapper_async_test
        and "active_timed_grant" in wrapper_service + wrapper_async_test + nullbridge_api
        and "test_time_limited_approval_grant_queues_matching_image_request_without_new_approval" in nullbridge_tests,
        ["active image grant queues matching request without new approval"],
        [] if "active_timed_grant" in timed_source else ["TIMED_APPROVAL_SOURCE_MARKER_MISSING"],
    )
    gates["timedApproval.videoThisJob"] = _gate(
        "test_once_video_approval_does_not_create_reusable_grant" in nullbridge_tests
        and LOCAL_VIDEO_CAPABILITY in nullbridge_tests,
        ["per-job video approval does not create reusable grant"],
        [] if "test_once_video_approval_does_not_create_reusable_grant" in nullbridge_tests else ["VIDEO_THIS_JOB_TEST_MISSING"],
    )
    gates["timedApproval.videoTimedGrant"] = _gate(
        "test_time_limited_approval_grant_queues_matching_video_request_without_new_approval" in nullbridge_tests
        and all(marker in nullbridge_tests for marker in ["8h", "24h", "30d", "audioMode", "audioArtifactId"]),
        ["8h/24h/30d video timed grants cover profiles and safe audio modes"],
        [] if "test_time_limited_approval_grant_queues_matching_video_request_without_new_approval" in nullbridge_tests else ["VIDEO_TIMED_GRANT_TEST_MISSING"],
    )
    gates["timedApproval.matchingVideoSkipsApproval"] = _gate(
        "test_time_limited_approval_grant_queues_matching_video_request_without_new_approval" in nullbridge_tests
        and "active_timed_grant" in wrapper_service + wrapper_async_test + nullbridge_api
        and "test_video_job_exposes_recorded_voice_artifact_to_authorized_worker_only" in wrapper_async_test,
        ["active video grant queues matching request without new approval"],
        [] if "test_video_job_exposes_recorded_voice_artifact_to_authorized_worker_only" in wrapper_async_test else ["VIDEO_STORE_GRANT_TEST_MISSING"],
    )
    gates["timedApproval.videoGrantDoesNotAuthorizeImage"] = _gate(
        "test_video_grant_does_not_authorize_image_or_3d_or_other_requester_or_forged_grant_id" in nullbridge_tests
        and LOCAL_IMAGE_CAPABILITY in nullbridge_tests,
        ["video grant does not authorize image"],
        [] if "test_video_grant_does_not_authorize_image_or_3d_or_other_requester_or_forged_grant_id" in nullbridge_tests else ["VIDEO_CROSS_IMAGE_TEST_MISSING"],
    )
    gates["timedApproval.videoGrantDoesNotAuthorize3D"] = _gate(
        "test_video_grant_does_not_authorize_image_or_3d_or_other_requester_or_forged_grant_id" in nullbridge_tests
        and LOCAL_3D_CAPABILITY in nullbridge_tests,
        ["video grant does not authorize 3D"],
        [] if "test_video_grant_does_not_authorize_image_or_3d_or_other_requester_or_forged_grant_id" in nullbridge_tests else ["VIDEO_CROSS_3D_TEST_MISSING"],
    )
    gates["timedApproval.videoAudioArtifactIsolation"] = _gate(
        "test_video_audio_artifact_is_not_fetchable_before_approval_or_after_denial_or_expiry" in wrapper_async_test
        and "test_video_audio_artifact_requires_matching_authorized_worker_job" in wrapper_async_test
        and "worker_input_artifact" in wrapper_service
        and "audioArtifactId" in wrapper_async_test + wrapper_service,
        ["video audio artifacts are scoped to approved or grant-authorized worker jobs"],
        [] if "test_video_audio_artifact_is_not_fetchable_before_approval_or_after_denial_or_expiry" in wrapper_async_test else ["VIDEO_AUDIO_ARTIFACT_ISOLATION_TEST_MISSING"],
    )
    gates["timedApproval.crossCapabilityDenied"] = _gate(
        "test_image_grant_does_not_authorize_video_or_3d_or_forged_grant_id" in nullbridge_tests
        and LOCAL_VIDEO_CAPABILITY in nullbridge_tests
        and LOCAL_3D_CAPABILITY in nullbridge_tests,
        ["image grant does not authorize video/3D"],
        [] if "test_image_grant_does_not_authorize_video_or_3d_or_forged_grant_id" in nullbridge_tests else ["TIMED_APPROVAL_CROSS_CAPABILITY_TEST_MISSING"],
    )
    gates["timedApproval.expiredGrantRequiresApproval"] = _gate(
        "test_expired_time_limited_approval_grant_does_not_bypass_new_approval" in nullbridge_tests
        and "2000-01-01T00:00:00+00:00" in nullbridge_tests,
        ["expired timed grant requires approval again"],
        [] if "test_expired_time_limited_approval_grant_does_not_bypass_new_approval" in nullbridge_tests else ["TIMED_APPROVAL_EXPIRY_TEST_MISSING"],
    )
    gates["timedApproval.replayDoesNotExtendGrant"] = _gate(
        "test_replayed_approval_decision_does_not_extend_timed_grant" in nullbridge_tests
        and "DECISION_REPLAYED" in nullbridge_tests,
        ["replayed approval does not extend grant"],
        [] if "test_replayed_approval_decision_does_not_extend_timed_grant" in nullbridge_tests else ["TIMED_APPROVAL_REPLAY_TEST_MISSING"],
    )
    gates["timedApproval.revokeGrant"] = _gate(
        "def revoke_approval_grant" in nullbridge_api
        and 'POST /grants/{grantId}/revoke' in nullbridge_api
        and "revokedAt" in nullbridge_api
        and "revokedBy" in nullbridge_api
        and "test_revoke_active_image_grant_requires_approval_again_and_is_idempotent" in nullbridge_tests
        and "test_revoke_active_video_grant_requires_approval_again" in nullbridge_tests,
        ["admin can revoke image and video timed grants"],
        [] if "def revoke_approval_grant" in nullbridge_api else ["TIMED_APPROVAL_REVOKE_API_MISSING"],
    )
    gates["timedApproval.revokedGrantRequiresApproval"] = _gate(
        "read_approval_grant" in nullbridge_api
        and "revokedAt" in nullbridge_api
        and "test_revoke_active_image_grant_requires_approval_again_and_is_idempotent" in nullbridge_tests
        and "test_revoke_active_video_grant_requires_approval_again" in nullbridge_tests
        and "test_revoke_does_not_cancel_already_queued_job_and_next_matching_job_requires_approval" in nullbridge_tests,
        ["revoked grants no longer bypass approval and do not cancel already queued jobs"],
        [] if "test_revoke_does_not_cancel_already_queued_job_and_next_matching_job_requires_approval" in nullbridge_tests else ["REVOKED_GRANT_AUTHORIZATION_TEST_MISSING"],
    )
    gates["timedApproval.grantUpdate"] = _gate(
        "def update_approval_grant" in nullbridge_api
        and 'POST /grants/{grantId}/update' in nullbridge_api
        and "ApprovalGrantUpdateRequestDto" in nullbridge_android_dtos + nullbridge_android_api + nullbridge_android_repo
        and "updateGrantDuration" in nullbridge_android_permissions + nullbridge_android_repo,
        ["admin can update active grant duration from API and Android Permissions"],
        [] if "def update_approval_grant" in nullbridge_api else ["GRANT_UPDATE_API_MISSING"],
    )
    gates["timedApproval.grantUpdatePreservesScope"] = _gate(
        "test_grant_update_changes_duration_from_server_time_and_preserves_scope" in nullbridge_tests
        and "after[\"scope\"] == before[\"scope\"]" in nullbridge_tests
        and "expiresAt" in nullbridge_api
        and "updatedBy" in nullbridge_api,
        ["grant update recalculates expiry and preserves requester/service/capability scope"],
        [] if "test_grant_update_changes_duration_from_server_time_and_preserves_scope" in nullbridge_tests else ["GRANT_UPDATE_PRESERVE_SCOPE_TEST_MISSING"],
    )
    gates["timedApproval.revokedGrantUpdateDenied"] = _gate(
        "test_grant_update_denies_revoked_and_expired_grants" in nullbridge_tests
        and "GRANT_REVOKED" in nullbridge_api + nullbridge_tests
        and "GRANT_EXPIRED" in nullbridge_api + nullbridge_tests,
        ["revoked and expired grants cannot be updated"],
        [] if "test_grant_update_denies_revoked_and_expired_grants" in nullbridge_tests else ["GRANT_UPDATE_DENIAL_TEST_MISSING"],
    )
    gates["timedApproval.grantListSafeMetadata"] = _gate(
        "def list_approval_grants" in nullbridge_api
        and "def get_approval_grant_metadata" in nullbridge_api
        and "safe_approval_grant_metadata" in nullbridge_api
        and "includeExpired" in nullbridge_api
        and "includeRevoked" in nullbridge_api
        and "serviceId" in nullbridge_api
        and "targetRole" in nullbridge_api
        and "test_grant_list_detail_returns_safe_metadata_and_filters_inactive_by_default" in nullbridge_tests,
        ["grant list/detail API exposes safe metadata and filters inactive grants by default"],
        [] if "safe_approval_grant_metadata" in nullbridge_api else ["GRANT_LIST_SAFE_METADATA_MISSING"],
    )
    gates["timedApproval.chatGrantLabeling"] = _gate(
        "Chat access for this requester" in nullbridge_api + nullbridge_android_formatters
        and "test_model3d_and_chat_grants_have_safe_friendly_labels" in nullbridge_tests,
        ["chat grants are labeled Chat access, not generation"],
        [] if "Chat access for this requester" in nullbridge_api + nullbridge_android_formatters else ["CHAT_GRANT_LABEL_MISSING"],
    )
    gates["timedApproval.safeRequesterServiceMetadata"] = _gate(
        all(marker in nullbridge_api + nullbridge_android_models + nullbridge_android_permissions for marker in ["serviceId", "serviceName", "platform", "targetRole", "requesterHash"])
        and "test_grant_list_detail_returns_safe_metadata_and_filters_inactive_by_default" in nullbridge_tests,
        ["safe requester/service owner metadata is exposed and displayed"],
        [f"SAFE_REQUESTER_METADATA_MISSING:{marker}" for marker in ["serviceId", "serviceName", "platform", "targetRole", "requesterHash"] if marker not in nullbridge_api + nullbridge_android_models + nullbridge_android_permissions],
    )
    safe_grant_start = nullbridge_api.find("def safe_approval_grant(")
    safe_grant_source = nullbridge_api[safe_grant_start : nullbridge_api.find("def redacted_payload_fields")] if safe_grant_start >= 0 else ""
    gates["timedApproval.credentialIsolation"] = _gate(
        "scope" not in safe_grant_source
        and "auth" not in safe_grant_source
        and "test_image_grant_does_not_authorize_video_or_3d_or_forged_grant_id" in nullbridge_tests
        and "approvalGrant" in wrapper_service,
        ["safe grant metadata and no client-facing secret markers"],
        [] if "scope" not in safe_grant_source else ["TIMED_APPROVAL_SCOPE_LEAK"],
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
