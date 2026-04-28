from __future__ import annotations

import json
from pathlib import Path

import aibenchie_local
from aibenchie import companion_remote_backend
from aibenchie.hosted_nullxoid_stack import HostedStackResult, RouteResult


PUBLIC_API = "https://api.echolabs.diy/nullxoid"
PUBLIC_ORIGIN = "https://api.echolabs.diy"
FORGEJO_RELEASES = "git.echolabs.diy/api/v1/repos/EchoLabs/NullXoidAndroid/releases"


def write_android_fixture(root: Path, *, public_api: str = PUBLIC_API) -> None:
    files = {
        "README.md": (
            "# NullXoid Companion / Android\n\n"
            "Hosted API: the release-channel HTTPS API, currently "
            f"`{public_api}`.\n\n"
            "Production auth should use passkeys through Android Credential Manager.\n"
        ),
        "app/build.gradle.kts": (
            'val nullxoidPublicBackendUrl = providers.environmentVariable("NULLXOID_PUBLIC_BACKEND_URL")\n'
            f'    .orElse("{public_api}")\n'
            'buildConfigField("String", "PUBLIC_BACKEND_URL", "\"$nullxoidPublicBackendUrl\"")\n'
            f'val NULLXOID_APP_UPDATE_RELEASES_URL = "http://{FORGEJO_RELEASES}"\n'
            'buildConfigField("String", "APP_UPDATE_RELEASES_URL", "\"$appUpdateReleasesUrl\"")\n'
            'val NULLXOID_APP_UPDATE_FALLBACK_RELEASES_URL = "https://api.github.com/repos/NullXoid/NullXoidAndroid/releases"\n'
            'buildConfigField("String", "APP_UPDATE_FALLBACK_RELEASES_URL", "\"$appUpdateFallbackReleasesUrl\"")\n'
        ),
        "app/src/main/java/com/nullxoid/android/data/api/BackendEndpoint.kt": (
            "object BackendEndpoint {\n"
            f'    const val PUBLIC_ECHOLABS_URL = "{public_api}"\n'
            "    fun normalize(input: String) = if (input.startsWith(\"http\")) input else \"https://$input\"\n"
            "}\n"
        ),
        "app/src/main/java/com/nullxoid/android/data/prefs/SettingsStore.kt": (
            "class SettingsStore {\n"
            "    companion object {\n"
            "        val PUBLIC_BACKEND_URL = BackendEndpoint.PUBLIC_ECHOLABS_URL\n"
            "    }\n"
            "}\n"
        ),
        "app/src/main/java/com/nullxoid/android/data/update/AppUpdateChecker.kt": (
            "class AppUpdateChecker {\n"
            "    val primary = BuildConfig.APP_UPDATE_RELEASES_URL\n"
            "    val fallback = BuildConfig.APP_UPDATE_FALLBACK_RELEASES_URL\n"
            "    fun findApkDownloadUrl() = Unit\n"
            "}\n"
        ),
        "app/src/main/res/xml/network_security_config.xml": (
            "<network-security-config>\n"
            '    <base-config cleartextTrafficPermitted="false" />\n'
            '    <domain-config cleartextTrafficPermitted="true">\n'
            "        <domain>localhost</domain>\n"
            "        <domain>127.0.0.1</domain>\n"
            "    </domain-config>\n"
            "</network-security-config>\n"
        ),
        "app/src/test/java/com/nullxoid/android/data/api/BackendEndpointTest.kt": (
            "class BackendEndpointTest {\n"
            f'    val login = "{public_api}/auth/login"\n'
            f'    val normalized = "{public_api.removeprefix("https://")}"\n'
            "}\n"
        ),
    }
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def hosted_stack(ok: bool = True) -> HostedStackResult:
    return HostedStackResult(
        ok=ok,
        origin=PUBLIC_ORIGIN,
        base_path="/nullxoid",
        routes=[
            RouteResult(
                name="backend_health",
                status=200 if ok else 500,
                content_type="application/json",
                ok=ok,
                failure="" if ok else "backend_health_not_backend_json",
            )
        ],
    )


def test_companion_remote_backend_gate_passes_with_android_contract(monkeypatch, tmp_path):
    write_android_fixture(tmp_path)
    monkeypatch.setattr(companion_remote_backend, "run_hosted_nullxoid_stack_check", lambda **kwargs: hosted_stack())

    result = companion_remote_backend.run_companion_remote_backend_check(android_repo=tmp_path)

    assert result.ok is True
    assert result.public_api == PUBLIC_API
    assert {check.name for check in result.checks} >= {
        "android_repo_exists",
        "android_contract_files",
        "public_api_contract",
        "hosted_api_stack_contract",
    }


def test_companion_remote_backend_gate_fails_when_android_public_api_drifts(monkeypatch, tmp_path):
    write_android_fixture(tmp_path, public_api="https://old.example.invalid/nullxoid")
    monkeypatch.setattr(companion_remote_backend, "run_hosted_nullxoid_stack_check", lambda **kwargs: hosted_stack())

    result = companion_remote_backend.run_companion_remote_backend_check(android_repo=tmp_path)

    assert result.ok is False
    failures = {check.name: check.failure for check in result.checks if not check.ok}
    assert "README.md:content" in failures
    assert failures["README.md:content"] == "missing_required_text"


def test_companion_remote_backend_gate_fails_on_placeholder_or_http_public_api(monkeypatch, tmp_path):
    write_android_fixture(tmp_path, public_api="http://api.example.test/nullxoid")
    monkeypatch.setattr(companion_remote_backend, "run_hosted_nullxoid_stack_check", lambda **kwargs: hosted_stack())

    result = companion_remote_backend.run_companion_remote_backend_check(
        android_repo=tmp_path,
        public_api="http://api.example.test/nullxoid",
        origin="http://api.example.test",
    )

    assert result.ok is False
    failures = {check.name: check.failure for check in result.checks if not check.ok}
    assert "public_api_contract" in failures
    assert "public_api_must_be_https" in failures["public_api_contract"]
    assert "app/src/main/java/com/nullxoid/android/data/api/BackendEndpoint.kt:excludes" in failures


def test_companion_remote_backend_gate_requires_release_network_security(monkeypatch, tmp_path):
    write_android_fixture(tmp_path)
    (tmp_path / "app/src/main/res/xml/network_security_config.xml").write_text(
        "<network-security-config>\n"
        '    <base-config cleartextTrafficPermitted="true" />\n'
        "</network-security-config>\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(companion_remote_backend, "run_hosted_nullxoid_stack_check", lambda **kwargs: hosted_stack())

    result = companion_remote_backend.run_companion_remote_backend_check(android_repo=tmp_path)

    assert result.ok is False
    failures = {check.name: check.failure for check in result.checks if not check.ok}
    assert failures["app/src/main/res/xml/network_security_config.xml:content"] == "missing_required_text"


def test_companion_remote_backend_gate_fails_when_hosted_stack_fails(monkeypatch, tmp_path):
    write_android_fixture(tmp_path)
    monkeypatch.setattr(companion_remote_backend, "run_hosted_nullxoid_stack_check", lambda **kwargs: hosted_stack(False))

    result = companion_remote_backend.run_companion_remote_backend_check(android_repo=tmp_path)

    assert result.ok is False
    failures = {check.name: check.failure for check in result.checks if not check.ok}
    assert failures["hosted_api_stack_contract"] == "hosted_stack_failed"


def test_companion_remote_backend_cli_outputs_json(monkeypatch, capsys):
    class FakeResult:
        def as_dict(self):
            return {
                "ok": True,
                "android_repo": "C:/repo",
                "public_api": PUBLIC_API,
                "origin": PUBLIC_ORIGIN,
                "base_path": "/nullxoid",
                "checks": [],
                "hosted_stack": {},
            }

    monkeypatch.setattr(aibenchie_local, "run_companion_remote_backend_from_env", lambda: FakeResult())

    code = aibenchie_local.main(["--companion-remote-backend", "--json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["public_api"] == PUBLIC_API
