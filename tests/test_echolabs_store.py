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
    nullbridge = tmp_path / "nullbridge"
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
    await provider.submitJob({"mediaKind": "video", "format": "glb", "sourceImageArtifactId": "artifact-safe-image"})
    return {"storeJobId": "storejob-safe", "artifactId": "safe", "thumbnailUrl": "/artifacts/safe/thumb", "posterUrl": "/artifacts/safe/thumb", "modelPreviewUrl": "/artifacts/safe", "durationMs": 4000, "mimeType": "model/gltf-binary"}

async def worker_register(): pass
async def worker_next_job(): pass
async def worker_claim_job(): pass
async def list_store_jobs(): return {"queueLane": "suite.media.image.generate", "queuePosition": 0, "canCancel": True, "cancelRequested": False, "events": []}
async def cancel_job(): pass
async def worker_progress(): pass
async def worker_cancel_request(): pass
async def worker_upload_artifact(): pass
async def worker_complete_job(): pass
def gallery(addon_id=None): pass
def worker_input_artifact():
    return {"audioArtifactId": "artifact-safe-voice", "sourceImageArtifactId": "artifact-safe-image"}
status = "CANCELLED"
SOURCE_IMAGE_REQUIRED = "SOURCE_IMAGE_REQUIRED"
""",
    )
    _write(
        wrapper / "backend" / "store_jobs.py",
        """
STORE_JOB_STATES = {"pending_approval", "queued_connector", "running_provider", "uploading_artifact"}
createdAt = "2026-05-05T00:00:00Z"
queuePosition = 0
cancelRequested = False
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
@app.get("/api/store/jobs")
async def store_jobs(): pass
@app.post("/api/store/jobs/{store_job_id}/cancel")
async def store_job_cancel(store_job_id): pass
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
@app.post("/api/creative-worker/jobs/{store_job_id}/progress")
async def creative_worker_progress(): pass
@app.get("/api/creative-worker/jobs/{store_job_id}/cancel-request")
async def creative_worker_cancel_request(): pass
""",
    )
    _write(
        wrapper / "backend" / "creative_provider.py",
        """
def provider_config_from_env(): pass
class LocalImageEngineProvider: pass
class DelayedCreativeProvider: pass
SOURCE_IMAGE_REQUIRED = "SOURCE_IMAGE_REQUIRED"
async def submit_model3d(imageBytes=None, imageFilename=None): pass
CREATIVE_PROVIDER_TEST_DELAY_MS = "CREATIVE_PROVIDER_TEST_DELAY_MS"
MAX_CREATIVE_PROVIDER_TEST_DELAY_MS = 120000
async def _sleep_test_delay(): pass
CREATIVE_REAL_PROVIDER_SMOKE_REQUIRED = "CREATIVE_REAL_PROVIDER_SMOKE_REQUIRED"
def cancel_prompt(): pass
""",
    )
    _write(
        wrapper / "backend" / "providers" / "comfyui.py",
        """
async def cancel_prompt(prompt_id, settings):
    await client.post("/interrupt")
    await client.post("/queue", json={"delete": [prompt_id]})
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
def _assert_valid_glb(): pass
def test_store_approved_mock_video_and_3d_call_provider_once(): pass
def test_store_denied_video_and_3d_approval_does_not_call_provider(): pass
def test_gallery_hides_private_path(): pass
def test_gallery_hides_private_artifact_path(): pass
def test_gallery_hides_private_artifact_path(): pass
# private artifact path
def test_store_public_surfaces_do_not_leak_fake_prompt_or_provider_secrets(): pass
def test_store_assistant_context_returns_safe_grounding_without_backend_secrets(): pass
def test_comfyui_cancel_prompt_calls_interrupt_and_queue_delete(): pass
def test_creative_provider_test_delay_env_parses_safely(): pass
def test_store_3d_generation_requires_source_image_before_approval(): pass
def test_real_3d_provider_receives_source_image(): pass
""",
    )
    _write(
        wrapper / "backend" / "tests" / "test_store_async_jobs.py",
        """
def test_async_store_action_returns_store_job_without_provider_execution(): pass
def test_connector_claim_upload_complete_produces_sanitized_gallery(): pass
def test_active_time_limited_approval_grant_queues_job_without_new_pending_approval():
    assert "approvalSource"
    assert "active_timed_grant"
def test_video_job_exposes_recorded_voice_artifact_to_authorized_worker_only():
    assert "active_timed_grant"
    assert "audioArtifactId"
def test_video_audio_artifact_is_not_fetchable_before_approval_or_after_denial_or_expiry():
    assert "audioArtifactId"
def test_video_audio_artifact_requires_matching_authorized_worker_job():
    assert "audioArtifactId"
def test_non_admin_self_approval_is_rejected_but_admin_same_phone_is_allowed():
    assert "suite.media.image.generate"
    assert "REQUESTER_NOT_AUTHORIZED"
    assert "admin"
def test_store_jobs_list_is_safe_active_only_and_fifo(): pass
def test_cancel_queued_job_is_idempotent_and_not_claimable(): pass
def test_cancel_pending_blocks_late_approval_from_queueing(): pass
def test_cancel_running_blocks_late_upload_and_complete(): pass
def test_cancel_authorization_rejects_unrelated_user(): pass
def test_slow_provider_delay_cancelled_connector_job_stores_no_artifact(): pass
def test_slow_provider_delay_keeps_two_job_queue_positions_observable(): pass
""",
    )
    _write(
        nullbridge / "backend" / "scripts" / "nullbridge_api.py",
        """
APPROVAL_GRANT_DURATIONS = {"once": 0, "8h": 28800, "24h": 86400, "30d": 2592000}
def create_approval_grant():
    record_event("nullbridge.approval_grant_created", durationSeconds=28800)
def queue_request_via_approval_grant():
    return {"approvalSource": "active_timed_grant"}
def safe_approval_grant(grant):
    return {"grantId": grant.get("grantId"), "duration": grant.get("duration"), "durationSeconds": grant.get("durationSeconds"), "expiresAt": grant.get("expiresAt")}
def safe_approval_grant_metadata(grant):
    return {"grantId": grant.get("grantId"), "displayId": "GRT-safe", "status": grant.get("status"), "serviceId": "store", "serviceName": "EchoLabs Store", "platform": "android", "targetRole": "store-generation", "addonId": "local-video-studio", "addonName": "Local Video Studio", "mediaKind": "video", "capability": "suite.media.video.generate", "action": "media.video.generate.local", "friendlyScope": "Local Video Studio video generation for this requester", "requesterHash": "req_safe", "approvedBy": "admin", "revokedBy": "admin", "duration": "8h", "durationSeconds": 28800, "createdAt": "2026-05-04T00:00:00Z", "expiresAt": "2026-05-04T08:00:00Z", "revokedAt": None}
def read_approval_grant(path):
    return None
def list_approval_grants(includeExpired=False, includeRevoked=False):
    return []
def get_approval_grant_metadata(grantId):
    return safe_approval_grant_metadata({"grantId": grantId})
def revoke_approval_grant(grantId, actor, auth=None):
    return {"grantId": grantId, "revokedAt": "2026-05-04T01:00:00Z", "revokedBy": actor}
def update_approval_grant(grantId, duration, actor, auth=None):
    return {"grantId": grantId, "expiresAt": "2026-05-04T09:00:00Z", "updatedBy": actor}
# GET /grants?includeExpired=&includeRevoked=
# GET /grants/{grantId}
# POST /grants/{grantId}/revoke
# POST /grants/{grantId}/update
class ApprovalGrantUpdateRequestDto: pass
def redacted_payload_fields(payload): pass
""",
    )
    _write(
        nullbridge / "backend" / "tests" / "test_nullbridge_generic_approval_routing.py",
        """
def test_approved_request_executes_exactly_once_and_can_be_delivered():
    assert list(api.APPROVAL_GRANTS.glob("grant-*.json")) == []
def test_time_limited_approval_grant_queues_matching_image_request_without_new_approval():
    assert "suite.media.image.generate"
def test_once_video_approval_does_not_create_reusable_grant():
    assert "suite.media.video.generate"
def test_time_limited_approval_grant_queues_matching_video_request_without_new_approval():
    assert "suite.media.video.generate"
    assert "audioMode"
    assert "audioArtifactId"
    assert "8h"
    assert "24h"
    assert "30d"
def test_video_grant_covers_safe_audio_modes():
    assert "audioMode"
def test_image_grant_does_not_authorize_video_or_3d_or_forged_grant_id():
    assert "suite.media.video.generate"
    assert "suite.media.model3d.generate"
def test_video_grant_does_not_authorize_image_or_3d_or_other_requester_or_forged_grant_id():
    assert "suite.media.image.generate"
    assert "suite.media.model3d.generate"
def test_expired_time_limited_approval_grant_does_not_bypass_new_approval():
    assert "2000-01-01T00:00:00+00:00"
def test_replayed_approval_decision_does_not_extend_timed_grant():
    assert "DECISION_REPLAYED"
def test_grant_list_detail_returns_safe_metadata_and_filters_inactive_by_default():
    assert "includeExpired"
    assert "includeRevoked"
def test_revoke_active_image_grant_requires_approval_again_and_is_idempotent():
    assert "revokedAt"
    assert "revokedBy"
def test_revoke_active_video_grant_requires_approval_again():
    assert "revokedAt"
def test_revoke_does_not_cancel_already_queued_job_and_next_matching_job_requires_approval():
    assert "queued"
def test_grant_update_changes_duration_from_server_time_and_preserves_scope():
    assert after["scope"] == before["scope"]
    assert "updatedBy"
    assert "expiresAt"
def test_grant_update_denies_revoked_and_expired_grants():
    assert "GRANT_REVOKED"
    assert "GRANT_EXPIRED"
def test_model3d_and_chat_grants_have_safe_friendly_labels():
    assert "Chat access for this requester"
""",
    )
    _write(
        nullbridge / "frontend" / "app" / "src" / "main" / "java" / "com" / "nullxoid" / "nullbridge" / "data" / "remote" / "NullBridgeDtos.kt",
        "ApprovalGrantUpdateRequestDto serviceId serviceName platform targetRole requesterHash",
    )
    _write(
        nullbridge / "frontend" / "app" / "src" / "main" / "java" / "com" / "nullxoid" / "nullbridge" / "data" / "remote" / "NullBridgeApi.kt",
        "ApprovalGrantUpdateRequestDto updateGrantDuration serviceId serviceName platform targetRole requesterHash",
    )
    _write(
        nullbridge / "frontend" / "app" / "src" / "main" / "java" / "com" / "nullxoid" / "nullbridge" / "domain" / "NullBridgeModels.kt",
        "serviceId serviceName platform targetRole requesterHash",
    )
    _write(
        nullbridge / "frontend" / "app" / "src" / "main" / "java" / "com" / "nullxoid" / "nullbridge" / "data" / "repository" / "NullBridgeRepositoryImpl.kt",
        "ApprovalGrantUpdateRequestDto updateGrantDuration serviceId serviceName platform targetRole requesterHash",
    )
    _write(
        nullbridge / "frontend" / "app" / "src" / "main" / "java" / "com" / "nullxoid" / "nullbridge" / "presentation" / "PermissionsComponents.kt",
        "updateGrantDuration serviceId serviceName platform targetRole requesterHash",
    )
    _write(
        nullbridge / "frontend" / "app" / "src" / "main" / "java" / "com" / "nullxoid" / "nullbridge" / "presentation" / "GrantUiFormatters.kt",
        "Chat access for this requester serviceId serviceName platform targetRole requesterHash",
    )
    _write(
        android / "app" / "src" / "main" / "java" / "com" / "nullxoid" / "android" / "data" / "model" / "Models.kt",
        '"Creative Workflows"; "local-image-studio"; "suite.media.image.generate"; "media.image.generate.local"; "local-video-studio"; "suite.media.video.generate"; "media.video.generate.local"; "local-3d-studio"; "suite.media.model3d.generate"; "media.model3d.generate.local"; "storeJobId"; StoreJobSummary; StoreJobsResponse;',
    )
    _write(
        android / "app" / "src" / "main" / "java" / "com" / "nullxoid" / "android" / "data" / "api" / "NullXoidApi.kt",
        '"storeJobId"; "/api/store/jobs/{store_job_id}"; "/api/store/jobs?activeOnly=$activeOnly"; "/api/store/jobs/${urlEncode(storeJobId)}/cancel"; getBytes(); storeJobs(activeOnly;',
    )
    _write(
        android / "app" / "src" / "main" / "java" / "com" / "nullxoid" / "android" / "data" / "repo" / "NullXoidRepository.kt",
        'storeArtifactBytes(); "/artifacts/$artifactId"; storeJobs(activeOnly; cancelStoreJob;',
    )
    _write(
        android / "app" / "src" / "main" / "java" / "com" / "nullxoid" / "android" / "data" / "prefs" / "SettingsStore.kt",
        '"active_store_job_id"; "active_store_addon_id";',
    )
    _write(
        android / "app" / "src" / "main" / "java" / "com" / "nullxoid" / "android" / "ui" / "NullXoidViewModel.kt",
        '"storeJobId"; "pending_approval"; "queued_connector"; "running_provider"; "uploading_artifact"; "sourceImageArtifactId"; "Choose a source image before generating a 3D model."; saveStoreArtifactToDevice(); MediaStore; MediaStore.Downloads.EXTERNAL_CONTENT_URI; Environment.DIRECTORY_DOWNLOADS; "model/gltf-binary"; storeJobs: List<StoreJobSummary>; repo.storeJobs(activeOnly = activeOnly, limit = 50); repo.cancelStoreJob(storeJobId); cancelStoreJob;',
    )
    _write(
        android / "app" / "src" / "main" / "java" / "com" / "nullxoid" / "android" / "ui" / "store" / "StoreScreen.kt",
        '"Creative Workflows"; "local-image-studio"; "suite.media.image.generate"; "media.image.generate.local"; "local-video-studio"; "suite.media.video.generate"; "media.video.generate.local"; "local-3d-studio"; "suite.media.model3d.generate"; "media.model3d.generate.local"; "3D model generation uses an image first."; "Choose image first"; "Save to device"; "3D preview not yet available";',
    )
    _write(
        android / "app" / "src" / "main" / "java" / "com" / "nullxoid" / "android" / "ui" / "store" / "StoreUiModels.kt",
        '"3D model"; item.format.ifBlank; "model/gltf-binary";',
    )
    _write(
        android / "app" / "src" / "main" / "java" / "com" / "nullxoid" / "android" / "ui" / "store" / "GalleryScreen.kt",
        '"3D"; StoreGalleryCard; "model/gltf-binary";',
    )
    _write(
        android / "app" / "src" / "main" / "java" / "com" / "nullxoid" / "android" / "ui" / "store" / "JobsScreen.kt",
        'class JobsScreen; Text("Jobs"); "Cancel this job?"; "No, keep job"; "Yes, cancel job"; "Queue #"; store-job-monitor-card;',
    )
    _write(
        android / "app" / "src" / "test" / "java" / "com" / "nullxoid" / "android" / "data" / "model" / "StoreAsyncJobContractTest.kt",
        '"StoreJobSummary"; "StoreJobsResponse"; "cancel_requested";',
    )
    _write(
        android / "app" / "src" / "test" / "java" / "com" / "nullxoid" / "android" / "ui" / "AndroidProductIaTest.kt",
        'const val Jobs = "jobs"; JobsScreen; "Cancel this job?"; "3D preview not yet available"; "Choose a source image before generating a 3D model."; "3D model generation uses an image first."; MediaStore.Downloads.EXTERNAL_CONTENT_URI; Environment.DIRECTORY_DOWNLOADS; "model/gltf-binary";',
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
        "AIBENCHIE_NULLBRIDGE_REPO": str(nullbridge),
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
    assert result["echolabsStore"]["model3DGallerySafeMetadata"]["status"] == "passed"
    assert result["echolabsStore"]["model3DRequiresSourceImage"]["status"] == "passed"
    assert result["echolabsStore"]["android3DModelCard"]["status"] == "passed"
    assert result["echolabsStore"]["android3DGlbSave"]["status"] == "passed"
    assert result["echolabsStore"]["realProviderSmoke.video"]["status"] == "skipped"
    assert result["echolabsStore"]["realProviderSmoke.model3d"]["status"] == "skipped"
    assert result["echolabsStore"]["androidOutOfNetwork.approvedVideoGeneration"]["status"] == "skipped"
    assert result["echolabsStore"]["storeAssistant.contextEndpoint"]["status"] == "passed"
    assert result["echolabsStore"]["storeAssistant.groundingPrompt"]["status"] == "passed"
    assert result["echolabsStore"]["storeAssistant.noHostedCloudFalseClaim"]["status"] == "passed"
    assert result["echolabsStore"]["storeAssistant.secretLeakCheck"]["status"] == "passed"
    assert result["echolabsStore"]["timedApproval.videoThisJob"]["status"] == "passed"
    assert result["echolabsStore"]["timedApproval.videoTimedGrant"]["status"] == "passed"
    assert result["echolabsStore"]["timedApproval.matchingVideoSkipsApproval"]["status"] == "passed"
    assert result["echolabsStore"]["timedApproval.videoGrantDoesNotAuthorizeImage"]["status"] == "passed"
    assert result["echolabsStore"]["timedApproval.videoGrantDoesNotAuthorize3D"]["status"] == "passed"
    assert result["echolabsStore"]["timedApproval.videoAudioArtifactIsolation"]["status"] == "passed"
    assert result["echolabsStore"]["timedApproval.revokeGrant"]["status"] == "passed"
    assert result["echolabsStore"]["timedApproval.revokedGrantRequiresApproval"]["status"] == "passed"
    assert result["echolabsStore"]["timedApproval.grantListSafeMetadata"]["status"] == "passed"
    assert result["echolabsStore"]["realProviderSmoke"]["required"] is False
    assert result["echolabsStore"]["realProviderSmoke"]["configured"] is False


def test_echolabs_store_android_video_e2e_manual_evidence_marks_passed(tmp_path):
    env = _fixture_repos(tmp_path)
    env.update(
        {
            "AIBENCHIE_ANDROID_VIDEO_E2E_STATUS": "passed",
            "AIBENCHIE_ANDROID_VIDEO_E2E_STORE_JOB_ID": "storejob-123",
            "AIBENCHIE_ANDROID_VIDEO_E2E_ARTIFACT_ID": "abc123",
            "AIBENCHIE_ANDROID_VIDEO_E2E_MIME": "video/mp4",
            "AIBENCHIE_ANDROID_VIDEO_E2E_PLAYER": "true",
            "AIBENCHIE_ANDROID_VIDEO_E2E_SAVED_TO_DEVICE": "true",
        }
    )

    result = echolabs_store.run_echolabs_store_check(env=env).as_dict()

    gate = result["echolabsStore"]["androidOutOfNetwork.approvedVideoGeneration"]
    assert result["ok"] is True
    assert gate["status"] == "passed"
    assert gate["configured"] is True
    assert gate["providerKind"] == "local-video-engine"


def _video_audio_prerelease_env(tmp_path: Path) -> dict[str, str]:
    env = _fixture_repos(tmp_path)
    env.update(
        {
            "AIBENCHIE_VIDEO_AUDIO_PRERELEASE_REQUIRED": "1",
            "AIBENCHIE_VIDEO_AUDIO_PRERELEASE_STATUS": "passed",
            "AIBENCHIE_VIDEO_AUDIO_PRERELEASE_EVIDENCE_DIR": str(tmp_path / "video-audio-evidence"),
            "AIBENCHIE_VIDEO_AUDIO_APK_VERSION": "0.9.0-prerelease",
            "AIBENCHIE_VIDEO_AUDIO_ANDROID_BUILD": "debug-123",
            "AIBENCHIE_VIDEO_AUDIO_AUTO_STORE_JOB_ID": "storejob-auto-123",
            "AIBENCHIE_VIDEO_AUDIO_AUTO_ARTIFACT_ID": "artifactauto",
            "AIBENCHIE_VIDEO_AUDIO_AUTO_APPROVAL_EVENT_ID": "approval-auto",
            "AIBENCHIE_VIDEO_AUDIO_AUTO_MIME": "video/mp4",
            "AIBENCHIE_VIDEO_AUDIO_AUTO_VIDEO_STREAMS": "1",
            "AIBENCHIE_VIDEO_AUDIO_AUTO_AUDIO_STREAMS": "1",
            "AIBENCHIE_VIDEO_AUDIO_AUTO_VIDEO_DURATION_MS": "5000",
            "AIBENCHIE_VIDEO_AUDIO_AUTO_AUDIO_DURATION_MS": "5050",
            "AIBENCHIE_VIDEO_AUDIO_AUTO_MAX_VOLUME_DB": "-12",
            "AIBENCHIE_VIDEO_AUDIO_AUTO_PLAYER": "true",
            "AIBENCHIE_VIDEO_AUDIO_AUTO_SAVED_TO_DEVICE": "true",
            "AIBENCHIE_VIDEO_AUDIO_AUTO_DEVICE": "Samsung S23 FE",
            "AIBENCHIE_VIDEO_AUDIO_RECORDED_STORE_JOB_ID": "storejob-recorded-123",
            "AIBENCHIE_VIDEO_AUDIO_RECORDED_ARTIFACT_ID": "artifactrecorded",
            "AIBENCHIE_VIDEO_AUDIO_RECORDED_APPROVAL_EVENT_ID": "approval-recorded",
            "AIBENCHIE_VIDEO_AUDIO_RECORDED_MIME": "video/mp4",
            "AIBENCHIE_VIDEO_AUDIO_RECORDED_VIDEO_STREAMS": "1",
            "AIBENCHIE_VIDEO_AUDIO_RECORDED_AUDIO_STREAMS": "1",
            "AIBENCHIE_VIDEO_AUDIO_RECORDED_VIDEO_DURATION_MS": "5000",
            "AIBENCHIE_VIDEO_AUDIO_RECORDED_AUDIO_DURATION_MS": "4900",
            "AIBENCHIE_VIDEO_AUDIO_RECORDED_MAX_VOLUME_DB": "-9",
            "AIBENCHIE_VIDEO_AUDIO_RECORDED_PLAYER": "true",
            "AIBENCHIE_VIDEO_AUDIO_RECORDED_SAVED_TO_DEVICE": "true",
            "AIBENCHIE_VIDEO_AUDIO_RECORDED_DEVICE": "Samsung Galaxy A17",
        }
    )
    return env


def _video_audio_device_proof(tmp_path: Path) -> Path:
    proof = {
        "schema": "aibenchie.video_audio_prerelease_device_proof.v1",
        "testOrder": ["S23 FE", "A17"],
        "devices": [
            {
                "serialAlias": "R5CWA36MWSF",
                "label": "S23 FE",
                "results": [
                    {
                        "mode": "auto_generated",
                        "storeJobId": "storejob-s23-auto",
                        "artifactId": "artifact-s23-auto",
                        "approvalEventId": "approval-s23-auto",
                        "androidPlayerProof": True,
                        "savedToDevice": True,
                    },
                    {
                        "mode": "recorded_voice",
                        "storeJobId": "storejob-s23-recorded",
                        "artifactId": "artifact-s23-recorded",
                        "approvalEventId": "approval-s23-recorded",
                        "androidPlayerProof": True,
                        "savedToDevice": True,
                    },
                ],
            },
            {
                "serialAlias": "R5GYC1KBN7T",
                "label": "A17",
                "results": [
                    {
                        "mode": "auto_generated",
                        "storeJobId": "storejob-a17-auto",
                        "artifactId": "artifact-a17-auto",
                        "approvalEventId": "approval-a17-auto",
                        "androidPlayerProof": True,
                        "savedToDevice": True,
                    },
                    {
                        "mode": "recorded_voice",
                        "storeJobId": "storejob-a17-recorded",
                        "artifactId": "artifact-a17-recorded",
                        "approvalEventId": "approval-a17-recorded",
                        "androidPlayerProof": True,
                        "savedToDevice": True,
                    },
                ],
            },
        ],
    }
    path = tmp_path / "device-proof.json"
    path.write_text(json.dumps(proof), encoding="utf-8")
    return path


def test_echolabs_store_video_audio_prerelease_skips_without_required_evidence(tmp_path):
    result = echolabs_store.run_echolabs_store_check(env=_fixture_repos(tmp_path)).as_dict()

    gate = result["echolabsStore"]["androidOutOfNetwork.videoAudioPrerelease"]
    assert result["ok"] is True
    assert gate["status"] == "skipped"
    assert gate["required"] is False
    assert gate["configured"] is False


def test_echolabs_store_video_audio_prerelease_required_evidence_blocks_when_missing(tmp_path):
    env = _fixture_repos(tmp_path)
    env["AIBENCHIE_VIDEO_AUDIO_PRERELEASE_REQUIRED"] = "1"

    result = echolabs_store.run_echolabs_store_check(env=env).as_dict()

    gate = result["echolabsStore"]["androidOutOfNetwork.videoAudioPrerelease"]
    assert result["ok"] is False
    assert gate["status"] == "failed_blocking"
    assert any(
        failure == "androidOutOfNetwork.videoAudioPrerelease:VIDEO_AUDIO_PRERELEASE_EVIDENCE_MISSING"
        for failure in result["blockingFailures"]
    )


def test_echolabs_store_video_audio_prerelease_passes_and_writes_evidence_bundle(tmp_path):
    env = _video_audio_prerelease_env(tmp_path)
    env["AIBENCHIE_VIDEO_AUDIO_DEVICE_PROOF_PATH"] = str(_video_audio_device_proof(tmp_path))
    env["AIBENCHIE_VIDEO_AUDIO_EXPECTED_DEVICE_COUNT"] = "2"

    result = echolabs_store.run_echolabs_store_check(env=env).as_dict()

    gate = result["echolabsStore"]["androidOutOfNetwork.videoAudioPrerelease"]
    evidence_dir = Path(env["AIBENCHIE_VIDEO_AUDIO_PRERELEASE_EVIDENCE_DIR"])
    verdict = json.loads((evidence_dir / "video_audio_prerelease_verdict.json").read_text(encoding="utf-8"))
    evidence = json.loads((evidence_dir / "video_audio_prerelease_evidence.json").read_text(encoding="utf-8"))
    assert result["ok"] is True
    assert gate["status"] == "passed"
    assert gate["required"] is True
    assert gate["configured"] is True
    assert verdict["ok"] is True
    assert evidence["schema"] == "aibenchie.video_audio_prerelease_evidence.v1"
    assert [mode["mode"] for mode in evidence["modes"]] == ["auto_generated", "recorded_voice"]
    assert evidence["androidPlayerProof"] is True
    assert evidence["androidSaveProof"] is True
    assert len(evidence["deviceProof"]["devices"]) == 2


def test_echolabs_store_video_audio_prerelease_blocks_missing_expected_device_proof(tmp_path):
    env = _video_audio_prerelease_env(tmp_path)
    env["AIBENCHIE_VIDEO_AUDIO_EXPECTED_DEVICE_COUNT"] = "2"

    result = echolabs_store.run_echolabs_store_check(env=env).as_dict()

    gate = result["echolabsStore"]["androidOutOfNetwork.videoAudioPrerelease"]
    assert result["ok"] is False
    assert gate["status"] == "failed_blocking"
    assert any(
        failure == "androidOutOfNetwork.videoAudioPrerelease:DEVICE_PROOF_MISSING"
        for failure in result["blockingFailures"]
    )


def test_echolabs_store_video_audio_prerelease_blocks_silent_audio(tmp_path):
    env = _video_audio_prerelease_env(tmp_path)
    env["AIBENCHIE_VIDEO_AUDIO_AUTO_MAX_VOLUME_DB"] = "-90"

    result = echolabs_store.run_echolabs_store_check(env=env).as_dict()

    gate = result["echolabsStore"]["androidOutOfNetwork.videoAudioPrerelease"]
    assert result["ok"] is False
    assert gate["status"] == "failed_blocking"
    assert any(
        failure == "androidOutOfNetwork.videoAudioPrerelease:auto_generated:AUDIO_EFFECTIVELY_SILENT"
        for failure in result["blockingFailures"]
    )


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
