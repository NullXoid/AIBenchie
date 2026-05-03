from __future__ import annotations

import json
from pathlib import Path

import aibenchie_local
from aibenchie import echolabs_store


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _fixture_repos(tmp_path: Path) -> dict[str, str]:
    wrapper = tmp_path / "wrapper"
    android = tmp_path / "android"
    windows = tmp_path / "windows"
    _write(
        wrapper / "backend" / "store_catalog.py",
        """
LOCAL_IMAGE_STUDIO_ID = "local-image-studio"
LOCAL_IMAGE_STUDIO_CAPABILITY = "suite.media.image.generate"
LOCAL_IMAGE_STUDIO_ACTION = "media.image.generate.local"
LOCAL_VIDEO_STUDIO_ID = "local-video-studio"
LOCAL_VIDEO_STUDIO_CAPABILITY = "suite.media.video.generate"
LOCAL_VIDEO_STUDIO_ACTION = "media.video.generate.local"
LOCAL_3D_STUDIO_ID = "local-3d-studio"
LOCAL_3D_STUDIO_CAPABILITY = "suite.media.model3d.generate"
LOCAL_3D_STUDIO_ACTION = "media.model3d.generate.local"
MANIFEST = {"name": "Local Image Studio", "categoryLabel": "Creative Workflows", "visibility": "local-debug", "platforms": ["web", "android", "windows"], "requiresApproval": True}
VIDEO_MANIFEST = {"name": "Local Video Studio", "id": LOCAL_VIDEO_STUDIO_ID, "capability": LOCAL_VIDEO_STUDIO_CAPABILITY, "action": LOCAL_VIDEO_STUDIO_ACTION, "providerKinds": ["mock-video", "local-video-engine"]}
MODEL3D_MANIFEST = {"name": "Local 3D Studio", "id": LOCAL_3D_STUDIO_ID, "capability": LOCAL_3D_STUDIO_CAPABILITY, "action": LOCAL_3D_STUDIO_ACTION, "providerKinds": ["mock-3d", "local-3d-engine"], "formats": ["glb", "gltf"]}
""",
    )
    _write(
        wrapper / "backend" / "store_service.py",
        """
async def assistant_context(addon_id):
    return {"contextVersion": "store-assistant.v1", "privacy": {"providerConfigVisibleToClient": False}}

async def run_action():
    await nullbridge_adapter.submit_approval_route({})
    await provider.submitJob({"mediaKind": "video", "format": "glb"})
    return {"storeJobId": "storejob-safe", "artifactId": "safe", "thumbnailUrl": "/artifacts/safe/thumb", "posterUrl": "/artifacts/safe/thumb", "modelPreviewUrl": "/artifacts/safe", "durationMs": 4000, "mimeType": "model/gltf-binary"}

async def worker_register(): pass
async def worker_next_job(): pass
async def worker_claim_job(): pass
""",
    )
    _write(
        wrapper / "backend" / "store_jobs.py",
        """
STORE_JOB_STATES = {"pending_approval", "queued_connector", "running_provider", "uploading_artifact"}
def lease_job(): pass
""",
    )
    _write(
        wrapper / "backend" / "main.py",
        """
@app.get("/api/store/addons/{addon_id}/assistant-context")
async def store_addon_assistant_context(addon_id):
    return {"ok": True, "context": await store_service.assistant_context(addon_id)}
@app.get("/api/store/jobs/{store_job_id}")
async def store_job_status(store_job_id): pass
@app.post("/api/creative-worker/register")
async def creative_worker_register(): pass
@app.post("/api/creative-worker/heartbeat")
async def creative_worker_heartbeat(): pass
@app.get("/api/creative-worker/jobs/next")
async def creative_worker_next_job(): pass
@app.post("/api/creative-worker/jobs/{store_job_id}/claim")
async def creative_worker_claim_job(): pass
@app.post("/api/creative-worker/jobs/{store_job_id}/artifact")
async def creative_worker_upload_artifact(): pass
@app.post("/api/creative-worker/jobs/{store_job_id}/complete")
async def creative_worker_complete_job(): pass
@app.post("/api/creative-worker/jobs/{store_job_id}/fail")
async def creative_worker_fail_job(): pass
""",
    )
    _write(
        wrapper / "backend" / "creative_provider.py",
        """
def provider_config_from_env(): pass
class LocalImageEngineProvider: pass
CREATIVE_REAL_PROVIDER_SMOKE_REQUIRED = "CREATIVE_REAL_PROVIDER_SMOKE_REQUIRED"
""",
    )
    _write(
        wrapper / "frontend" / "src" / "App.jsx",
        '"/api/store/catalog"; "/api/store/addons/${selectedStoreAddonId}/assistant-context"; "Creative Workflows"; "local-image-studio"; "suite.media.image.generate"; "media.image.generate.local"; "local-video-studio"; "suite.media.video.generate"; "media.video.generate.local"; "local-3d-studio"; "suite.media.model3d.generate"; "media.model3d.generate.local"; buildStoreAssistantSystemPrompt();',
    )
    _write(
        wrapper / "frontend" / "src" / "lib" / "storeAssistantPrompt.js",
        """
export function buildLocalImageStudioRequirementsAnswer() {
  return "authenticated wrapper app wrapper backend NullBridge approval connector mock provider baseline configured local image engine private artifacts sanitized IDs and thumbnail routes";
}
export function buildStoreAddonRequirementsAnswer() {
  return "Local Video Studio Local 3D Studio backend-only provider adapter NullBridge approval private artifacts GLB/glTF";
}
export function buildStoreAssistantSystemPrompt() {
  return "Do not invent provider behavior unless the Store context explicitly says a remote or cloud provider is active. backend-only provider adapter NullBridge approval private artifacts Local Video Studio Local 3D Studio";
}
""",
    )
    _write(
        wrapper / "backend" / "tests" / "test_store_alpha.py",
        """
def test_unsupported_capability_denies(): pass
def test_denied_expired_pending_approval_does_not_call_provider(): pass
def test_approved_calls_provider_once(): pass
def test_approved_generation_calls_mock_provider_once(): pass
def test_store_approved_mock_video_and_3d_call_provider_once(): pass
def test_store_denied_video_and_3d_approval_does_not_call_provider(): pass
def test_gallery_hides_private_path(): pass
def test_gallery_hides_private_artifact_path(): pass
def test_gallery_hides_private_artifact_path(): pass
# private artifact path
def test_store_public_surfaces_do_not_leak_fake_prompt_or_provider_secrets(): pass
def test_store_assistant_context_returns_safe_grounding_without_backend_secrets(): pass
""",
    )
    _write(
        wrapper / "backend" / "tests" / "test_store_async_jobs.py",
        """
def test_async_store_action_returns_store_job_without_provider_execution(): pass
def test_connector_claim_upload_complete_produces_sanitized_gallery(): pass
def test_non_admin_self_approval_is_rejected_but_admin_same_phone_is_allowed():
    assert "suite.media.image.generate"
    assert "REQUESTER_NOT_AUTHORIZED"
    assert "admin"
""",
    )
    _write(
        android / "app" / "src" / "main" / "java" / "com" / "nullxoid" / "android" / "data" / "model" / "Models.kt",
        '"Creative Workflows"; "local-image-studio"; "suite.media.image.generate"; "media.image.generate.local"; "local-video-studio"; "suite.media.video.generate"; "media.video.generate.local"; "local-3d-studio"; "suite.media.model3d.generate"; "media.model3d.generate.local"; "storeJobId";',
    )
    _write(
        android / "app" / "src" / "main" / "java" / "com" / "nullxoid" / "android" / "data" / "api" / "NullXoidApi.kt",
        '"storeJobId"; "/api/store/jobs/{store_job_id}"; getBytes();',
    )
    _write(
        android / "app" / "src" / "main" / "java" / "com" / "nullxoid" / "android" / "data" / "repo" / "NullXoidRepository.kt",
        'storeArtifactBytes(); "/artifacts/$artifactId";',
    )
    _write(
        android / "app" / "src" / "main" / "java" / "com" / "nullxoid" / "android" / "data" / "prefs" / "SettingsStore.kt",
        '"active_store_job_id"; "active_store_addon_id";',
    )
    _write(
        android / "app" / "src" / "main" / "java" / "com" / "nullxoid" / "android" / "ui" / "NullXoidViewModel.kt",
        '"storeJobId"; "pending_approval"; "queued_connector"; "running_provider"; "uploading_artifact"; saveStoreArtifactToDevice(); MediaStore;',
    )
    _write(
        android / "app" / "src" / "main" / "java" / "com" / "nullxoid" / "android" / "ui" / "store" / "StoreScreen.kt",
        '"Creative Workflows"; "local-image-studio"; "suite.media.image.generate"; "media.image.generate.local"; "local-video-studio"; "suite.media.video.generate"; "media.video.generate.local"; "local-3d-studio"; "suite.media.model3d.generate"; "media.model3d.generate.local"; "Save to device";',
    )
    _write(
        android / "app" / "src" / "test" / "java" / "com" / "nullxoid" / "android" / "data" / "model" / "StoreCatalogContractTest.kt",
        '"Creative Workflows"; "local-image-studio"; "suite.media.image.generate"; "media.image.generate.local"; "local-video-studio"; "suite.media.video.generate"; "media.video.generate.local"; "local-3d-studio"; "suite.media.model3d.generate"; "media.model3d.generate.local";',
    )
    _write(
        windows / "src" / "bridge" / "echolabs_store_adapter.cpp",
        '"EchoLabsStoreAdapter"; "Creative Workflows"; "local-image-studio"; "suite.media.image.generate"; "local-video-studio"; "suite.media.video.generate"; "local-3d-studio"; "suite.media.model3d.generate";',
    )
    _write(
        windows / "src" / "bridge" / "echolabs_store_adapter.h",
        "class EchoLabsStoreAdapter {};",
    )
    _write(
        windows / "tests" / "unit" / "echolabs_store_adapter_test.cpp",
        '"EchoLabsStoreAdapter"; "Creative Workflows"; "local-image-studio"; "suite.media.image.generate"; "local-video-studio"; "suite.media.video.generate"; "local-3d-studio"; "suite.media.model3d.generate";',
    )
    return {
        "AIBENCHIE_NULLXOID_WRAPPER_REPO": str(wrapper),
        "AIBENCHIE_ANDROID_REPO": str(android),
        "AIBENCHIE_WINDOWS_REPO": str(windows),
    }


def test_echolabs_store_gate_passes_with_safe_cross_platform_fixtures(tmp_path):
    result = echolabs_store.run_echolabs_store_check(env=_fixture_repos(tmp_path)).as_dict()

    assert result["ok"] is True
    assert result["blockingFailures"] == []
    assert set(result["echolabsStore"]) == set(echolabs_store.STORE_SECTIONS)
    assert result["echolabsStore"]["credentialIsolation"]["status"] == "passed"
    assert result["echolabsStore"]["realProviderSmoke"]["status"] == "skipped"
    assert result["echolabsStore"]["localVideoStudio"]["status"] == "passed"
    assert result["echolabsStore"]["local3DStudio"]["status"] == "passed"
    assert result["echolabsStore"]["videoApprovedGeneration"]["status"] == "passed"
    assert result["echolabsStore"]["model3DApprovedGeneration"]["status"] == "passed"
    assert result["echolabsStore"]["realProviderSmoke.video"]["status"] == "skipped"
    assert result["echolabsStore"]["realProviderSmoke.model3d"]["status"] == "skipped"
    assert result["echolabsStore"]["storeAssistant.contextEndpoint"]["status"] == "passed"
    assert result["echolabsStore"]["storeAssistant.groundingPrompt"]["status"] == "passed"
    assert result["echolabsStore"]["storeAssistant.noHostedCloudFalseClaim"]["status"] == "passed"
    assert result["echolabsStore"]["storeAssistant.secretLeakCheck"]["status"] == "passed"
    assert result["echolabsStore"]["realProviderSmoke"]["required"] is False
    assert result["echolabsStore"]["realProviderSmoke"]["configured"] is False


def test_echolabs_store_gate_fails_client_secret_leak(tmp_path):
    env = _fixture_repos(tmp_path)
    app = Path(env["AIBENCHIE_NULLXOID_WRAPPER_REPO"]) / "frontend" / "src" / "App.jsx"
    app.write_text(app.read_text(encoding="utf-8") + "\nNULLBRIDGE_SERVICE_TOKEN=leak", encoding="utf-8")

    result = echolabs_store.run_echolabs_store_check(env=env).as_dict()

    assert result["ok"] is False
    assert any("credentialIsolation" in failure for failure in result["blockingFailures"])


def test_echolabs_store_real_provider_failure_is_non_blocking_by_default(tmp_path, monkeypatch):
    env = _fixture_repos(tmp_path)
    env.update(
        {
            "CREATIVE_PROVIDER": "local-image-engine",
            "CREATIVE_PROVIDER_BASE_URL": "http://127.0.0.1:9",
        }
    )
    monkeypatch.setattr(echolabs_store, "_provider_health", lambda *_args, **_kwargs: (False, "PROVIDER_UNAVAILABLE"))

    result = echolabs_store.run_echolabs_store_check(env=env).as_dict()

    smoke = result["echolabsStore"]["realProviderSmoke"]
    assert result["ok"] is True
    assert result["blockingFailures"] == []
    assert smoke["status"] == "failed_non_blocking"
    assert smoke["configured"] is True
    assert smoke["errorCode"] == "PROVIDER_UNAVAILABLE"


def test_echolabs_store_real_provider_failure_blocks_when_required(tmp_path, monkeypatch):
    env = _fixture_repos(tmp_path)
    env.update(
        {
            "CREATIVE_PROVIDER": "local-image-engine",
            "CREATIVE_PROVIDER_BASE_URL": "http://127.0.0.1:9",
            "CREATIVE_REAL_PROVIDER_SMOKE_REQUIRED": "1",
        }
    )
    monkeypatch.setattr(echolabs_store, "_provider_health", lambda *_args, **_kwargs: (False, "PROVIDER_UNAVAILABLE"))

    result = echolabs_store.run_echolabs_store_check(env=env).as_dict()

    smoke = result["echolabsStore"]["realProviderSmoke"]
    assert result["ok"] is False
    assert any("realProviderSmoke" in failure for failure in result["blockingFailures"])
    assert smoke["status"] == "failed_blocking"
    assert smoke["required"] is True


def test_echolabs_store_real_provider_passes_when_configured_and_healthy(tmp_path, monkeypatch):
    env = _fixture_repos(tmp_path)
    env.update(
        {
            "CREATIVE_PROVIDER": "local-image-engine",
            "CREATIVE_PROVIDER_BASE_URL": "http://127.0.0.1:8188",
        }
    )
    monkeypatch.setattr(echolabs_store, "_provider_health", lambda *_args, **_kwargs: (True, ""))

    result = echolabs_store.run_echolabs_store_check(env=env).as_dict()

    smoke = result["echolabsStore"]["realProviderSmoke"]
    assert result["ok"] is True
    assert smoke["status"] == "passed"
    assert smoke["configured"] is True
    assert smoke["providerKind"] == "local-image-engine"


def test_echolabs_store_cli_outputs_json(monkeypatch, capsys):
    class FakeResult:
        def as_dict(self):
            return {
                "ok": True,
                "blockingFailures": [],
                "echolabsStore": {"webCatalog": {"status": "passed", "evidence": []}},
                "repos": {},
            }

    monkeypatch.setattr(aibenchie_local, "run_echolabs_store_from_env", lambda: FakeResult())

    code = aibenchie_local.main(["--echolabs-store", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["ok"] is True
    assert payload["echolabsStore"]["webCatalog"]["status"] == "passed"
