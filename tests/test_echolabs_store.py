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
MANIFEST = {"name": "Local Image Studio", "categoryLabel": "Creative Workflows", "visibility": "local-debug", "platforms": ["web", "android", "windows"], "requiresApproval": True}
""",
    )
    _write(
        wrapper / "backend" / "store_service.py",
        """
async def run_action():
    await nullbridge_adapter.submit_approval_route({})
    await provider.submitJob({})
    return {"artifactId": "safe", "thumbnailUrl": "/artifacts/safe/thumb"}
""",
    )
    _write(
        wrapper / "frontend" / "src" / "App.jsx",
        '"/api/store/catalog"; "Creative Workflows"; "local-image-studio"; "suite.media.image.generate"; "media.image.generate.local";',
    )
    _write(
        wrapper / "backend" / "tests" / "test_store_alpha.py",
        """
def test_unsupported_capability_denies(): pass
def test_denied_expired_pending_approval_does_not_call_provider(): pass
def test_approved_calls_provider_once(): pass
def test_approved_generation_calls_mock_provider_once(): pass
def test_gallery_hides_private_path(): pass
def test_gallery_hides_private_artifact_path(): pass
def test_gallery_hides_private_artifact_path(): pass
# private artifact path
def test_store_public_surfaces_do_not_leak_fake_prompt_or_provider_secrets(): pass
""",
    )
    _write(
        android / "app" / "src" / "main" / "java" / "com" / "nullxoid" / "android" / "data" / "model" / "Models.kt",
        '"Creative Workflows"; "local-image-studio"; "suite.media.image.generate"; "media.image.generate.local";',
    )
    _write(
        android / "app" / "src" / "main" / "java" / "com" / "nullxoid" / "android" / "ui" / "store" / "StoreScreen.kt",
        '"Creative Workflows"; "local-image-studio"; "suite.media.image.generate"; "media.image.generate.local";',
    )
    _write(
        android / "app" / "src" / "test" / "java" / "com" / "nullxoid" / "android" / "data" / "model" / "StoreCatalogContractTest.kt",
        '"Creative Workflows"; "local-image-studio"; "suite.media.image.generate"; "media.image.generate.local";',
    )
    _write(
        windows / "src" / "bridge" / "echolabs_store_adapter.cpp",
        '"EchoLabsStoreAdapter"; "Creative Workflows"; "local-image-studio"; "suite.media.image.generate";',
    )
    _write(
        windows / "src" / "bridge" / "echolabs_store_adapter.h",
        "class EchoLabsStoreAdapter {};",
    )
    _write(
        windows / "tests" / "unit" / "echolabs_store_adapter_test.cpp",
        '"EchoLabsStoreAdapter"; "Creative Workflows"; "local-image-studio"; "suite.media.image.generate";',
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


def test_echolabs_store_gate_fails_client_secret_leak(tmp_path):
    env = _fixture_repos(tmp_path)
    app = Path(env["AIBENCHIE_NULLXOID_WRAPPER_REPO"]) / "frontend" / "src" / "App.jsx"
    app.write_text(app.read_text(encoding="utf-8") + "\nNULLBRIDGE_SERVICE_TOKEN=leak", encoding="utf-8")

    result = echolabs_store.run_echolabs_store_check(env=env).as_dict()

    assert result["ok"] is False
    assert any("credentialIsolation" in failure for failure in result["blockingFailures"])


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
