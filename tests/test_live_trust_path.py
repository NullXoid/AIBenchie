from __future__ import annotations

import json
from pathlib import Path

import pytest

from aibenchie import live_trust_path


def test_live_trust_path_helpers_do_not_enable_without_explicit_env(monkeypatch):
    monkeypatch.delenv("AIBENCHIE_LIVE_TRUST_PATH", raising=False)
    assert live_trust_path.enabled() is False


def test_live_service_secret_config_is_json_only(monkeypatch):
    monkeypatch.setenv("AIBENCHIE_LIVE_NULLBRIDGE_SERVICE_JWT_SECRETS", '{"android_backend":"secret"}')
    assert live_trust_path.service_secrets() == {"android_backend": "secret"}

    monkeypatch.setenv("AIBENCHIE_LIVE_NULLBRIDGE_SERVICE_JWT_SECRETS", "android_backend=secret")
    with pytest.raises(ValueError, match="must be JSON"):
        live_trust_path.service_secrets()


def test_live_route_check_builds_signed_backend_envelope(monkeypatch):
    captured = {}

    def fake_request_json(method, url, *, body=None, headers=None, timeout=8):
        captured["method"] = method
        captured["url"] = url
        captured["body"] = json.loads(json.dumps(body))
        captured["headers"] = dict(headers or {})
        return 202, {"accepted": True}

    monkeypatch.setattr(live_trust_path, "request_json", fake_request_json)
    status, body = live_trust_path.route_check(
        base_url="http://127.0.0.1:18880",
        caller="android_backend",
        secret=("android-service-" + "jwt-secret-" + "000001"),
        target_role="primary_api",
        capability="chat.stream",
        platform="android",
    )

    assert status == 202
    assert body["accepted"] is True
    assert captured["method"] == "POST"
    assert captured["url"] == "http://127.0.0.1:18880/bridge/requests"
    assert captured["headers"]["X-NullBridge-Service"] == "android_backend"
    assert captured["headers"]["Authorization"].startswith("Bearer ")
    assert captured["body"]["actingUser"]["platform"] == "android"
    assert captured["body"]["actingUser"]["userId"] == "aibenchie_live_user"


def test_streamlit_exposes_public_safe_trust_smoke_button():
    text = (Path(__file__).resolve().parents[1] / "streamlit_app.py").read_text(encoding="utf-8")
    assert "Trust Fabric Smoke Test" in text
    assert "run_local_trust_path" in text
    assert "temporary generated service secrets" in text
    assert "AIBENCHIE_LIVE_NULLBRIDGE_SERVICE_JWT_SECRETS" not in text
    assert "st.secrets" not in text


def test_streamlit_exposes_nullprivacy_foundation_without_saved_keys():
    text = (Path(__file__).resolve().parents[1] / "streamlit_app.py").read_text(encoding="utf-8")
    assert "NullPrivacy Foundation" in text
    assert "run_e2ee_storage_proof" in text
    assert "temporary generated keys" in text
    assert "PRIVATE_KEY" not in text


@pytest.mark.skipif(not live_trust_path.enabled(), reason="set AIBENCHIE_LIVE_TRUST_PATH=1 to run live stack probes")
def test_live_nullbridge_trust_path_allows_and_denies_expected_routes():
    base_url = live_trust_path.live_nullbridge_url()
    secrets = live_trust_path.service_secrets()
    if not base_url or not secrets:
        pytest.skip("set AIBENCHIE_LIVE_NULLBRIDGE_URL and AIBENCHIE_LIVE_NULLBRIDGE_SERVICE_JWT_SECRETS")

    status, body = live_trust_path.health(base_url)
    assert status == 200, body
    assert body.get("ok") is True

    status, body = live_trust_path.route_check(
        base_url=base_url,
        caller="android_backend",
        secret=secrets["android_backend"],
        target_role="primary_api",
        capability="chat.stream",
        platform="android",
    )
    assert status == 202, body
    assert body.get("accepted") is True

    status, body = live_trust_path.route_check(
        base_url=base_url,
        caller="android_backend",
        secret=secrets["android_backend"],
        target_role="codex_tools",
        capability="codex.run",
        platform="android",
    )
    assert status == 403, body
    assert body.get("errorCode") in {"bridge.route_denied", "bridge.no_target"}


@pytest.mark.skipif(not live_trust_path.enabled(), reason="set AIBENCHIE_LIVE_TRUST_PATH=1 to run live stack probes")
def test_live_wrapper_backend_greeting_if_configured():
    wrapper_url = live_trust_path.live_wrapper_url()
    if not wrapper_url:
        pytest.skip("set AIBENCHIE_LIVE_WRAPPER_URL")
    status, body = live_trust_path.wrapper_greeting(wrapper_url)
    assert status == 200, body
    assert body.get("ok") is True
    assert "Hello" in str(body.get("message") or "")
