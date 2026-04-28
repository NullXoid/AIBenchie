from __future__ import annotations

import json
from pathlib import Path

import aibenchie_local
from aibenchie import secure_signin_setup


PUBLIC_API = "https://api.echolabs.diy/nullxoid"
PUBLIC_ORIGIN = "https://api.echolabs.diy"


def write_policies(root: Path) -> None:
    policy_root = root / ".suite" / "policies"
    policy_root.mkdir(parents=True, exist_ok=True)
    (policy_root / "auth-policy.json").write_text(
        json.dumps(
            {
                "primary_user_auth": "passkey",
                "allowed_user_auth_methods": [
                    "passkey",
                    "oidc_pkce",
                    "hardware_security_key",
                    "password_fallback_mfa",
                ],
                "frontend_token_storage": {
                    "website": "http_only_secure_samesite_cookie",
                    "website_wrapper": "http_only_secure_samesite_cookie_or_os_secure_storage",
                    "windows": "windows_credential_manager",
                    "android": "android_keystore",
                    "ios": "keychain",
                },
                "session_requirements": {
                    "short_lived": True,
                    "refresh_rotation": True,
                    "logout_revokes_server_session": True,
                },
                "nullbridge_auth_boundary": "platform_backends_only",
                "service_auth_boundary": "backend_to_nullbridge_only",
                "forbidden_controls": [
                    "frontend_nullbridge_service_credentials",
                    "tokens_in_urls",
                    "browser_localstorage_auth_tokens",
                    "password_only_admin",
                    "android_direct_nullbridge_privileged_route",
                    "shared_default_admin_credentials",
                ],
                "admin_requirements": [
                    "hardware_key_for_admin",
                    "hardware_key_for_release",
                    "hardware_key_for_breakglass",
                ],
            }
        ),
        encoding="utf-8",
    )
    (policy_root / "setup-policy.json").write_text(
        json.dumps(
            {
                "setup_mode": "guided_ui_first",
                "cli_required_for_standard_setup": False,
                "personal_config_storage": "ignored_local_addon",
                "save_personal_credentials": False,
                "validate_before_save": True,
                "export_redacted_support_bundle": True,
                "steps": [
                    {"id": "choose_source_provider", "label": "Source", "requires_cli": False, "stores_secret": False},
                    {"id": "choose_auth_method", "label": "Sign in", "requires_cli": False, "stores_secret": False},
                    {"id": "connect_backend", "label": "Backend", "requires_cli": False, "stores_secret": False},
                    {"id": "choose_privacy_level", "label": "Privacy", "requires_cli": False, "stores_secret": False},
                    {"id": "choose_resource_profile", "label": "Resources", "requires_cli": False, "stores_secret": False},
                    {"id": "validate_routes", "label": "Validate", "requires_cli": False, "stores_secret": False},
                    {"id": "run_aibenchie_gates", "label": "AIBenchie", "requires_cli": False, "stores_secret": False},
                ],
            }
        ),
        encoding="utf-8",
    )


def write_android_fixture(root: Path) -> None:
    files = {
        "README.md": "Hosted API uses passkeys through Android Credential Manager.\n",
        "docs/PASSKEY_AUTH_ANDROID.md": (
            "Use Credential Manager for passkeys.\n"
            "OIDC Authorization Code with PKCE is allowed.\n"
            "Password sign-in remains a development or migration fallback only.\n"
            "Store refresh material in Android Keystore.\n"
        ),
        "app/src/main/java/com/nullxoid/android/ui/auth/LoginScreen.kt": (
            'Modifier.testTag("login-passkey")\n'
            'Text("Sign in with passkey")\n'
            'Modifier.testTag("login-oidc")\n'
            'Text("Continue with OIDC")\n'
            'Text("Password fallback is for development or migration only.")\n'
        ),
        "app/build.gradle.kts": (
            'implementation("androidx.credentials:credentials:1.3.0")\n'
            'implementation("androidx.credentials:credentials-play-services-auth:1.3.0")\n'
        ),
        "app/src/main/AndroidManifest.xml": (
            '<category android:name="android.intent.category.BROWSABLE" />\n'
            '<data android:scheme="nullxoid" android:host="auth" android:path="/oidc/callback" />\n'
        ),
        "app/src/main/java/com/nullxoid/android/MainActivity.kt": (
            "onNewIntent\n"
            "NullXoidApp(app = app, oidcRedirect = oidcRedirect)\n"
        ),
        "app/src/main/java/com/nullxoid/android/ui/NullXoidNavHost.kt": (
            "vm.loginWithPasskey(context)\n"
            "vm::startOidcSignIn\n"
            "vm.completeOidcSignIn\n"
        ),
        "app/src/main/java/com/nullxoid/android/ui/NullXoidViewModel.kt": (
            "loginWithPasskey\n"
            "startOidcSignIn\n"
            "completeOidcSignIn\n"
            "nullxoid://auth/oidc/callback\n"
            "OIDC state mismatch\n"
        ),
        "app/src/main/java/com/nullxoid/android/data/auth/NativeAuthCoordinator.kt": (
            "CredentialManager\n"
            "GetPublicKeyCredentialOption\n"
            "PublicKeyCredential\n"
            "authenticationResponseJson\n"
            "codeChallenge\n"
            "codeVerifier\n"
        ),
        "app/src/main/java/com/nullxoid/android/data/auth/Pkce.kt": (
            'CHALLENGE_METHOD = "S256"\n'
            'MessageDigest.getInstance("SHA-256")\n'
            "Base64.getUrlEncoder().withoutPadding()\n"
        ),
        "app/src/main/java/com/nullxoid/android/data/api/NullXoidApi.kt": (
            'data class LoginRequest(val username: String, val password: String)\n'
            '"/auth/login"\n'
            '"/auth/passkey/options"\n'
            '"/auth/passkey/complete"\n'
            '"/auth/oidc/start"\n'
            '"/auth/oidc/complete"\n'
        ),
        "app/src/main/java/com/nullxoid/android/data/repo/NullXoidRepository.kt": "NativeAuthCoordinator\n",
        "app/src/main/java/com/nullxoid/android/data/model/Models.kt": (
            "PasskeyOptionsResponse\n"
            "OidcStartRequest\n"
            "OidcCompleteRequest\n"
        ),
        "app/src/test/java/com/nullxoid/android/data/auth/PkceTest.kt": "challengeMatchesRfc7636Example\n",
    }
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def write_wrapper_fixture(root: Path) -> None:
    files = {
        "backend/main.py": (
            'features = {\n'
            '    "auth_primary_method": "passkey",\n'
            '    "auth_allowed_methods": ["passkey", "oidc_pkce", "session_cookie"],\n'
            '    "auth_native_ceremony_endpoints": True,\n'
            '    "/auth/passkey/options": True,\n'
            '    "/auth/passkey/complete": True,\n'
            '    "/auth/oidc/start": True,\n'
            '    "/auth/oidc/complete": True,\n'
            '    "auth_token_storage": "http_only_secure_samesite_cookie",\n'
            '    "auth_password_fallback": "migration_only_mfa_required",\n'
            '    "setup_mode": "guided_ui_first",\n'
            '    "setup_cli_required": False,\n'
            '}\n'
        ),
        "backend/tests/test_auth_json_contract.py": (
            "def test_health_features_advertises_passkey_guided_setup_contract():\n"
            "    assert 'auth_primary_method'\n"
            "    assert 'auth_allowed_methods'\n"
            "    assert 'auth_native_ceremony_endpoints'\n"
            "    assert 'setup_cli_required'\n"
            "def test_native_auth_ceremony_endpoints_fail_json_until_provider_configured():\n"
            "    assert 'provider_not_configured'\n"
        ),
    }
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def fake_features_request(origin, path, **kwargs):
    assert origin == PUBLIC_ORIGIN
    assert path == "/nullxoid/health/features"
    return (
        200,
        "application/json",
        json.dumps(
            {
                "auth_primary_method": "passkey",
                "auth_allowed_methods": ["passkey", "oidc_pkce", "session_cookie"],
                "auth_token_storage": "http_only_secure_samesite_cookie",
                "auth_password_fallback": "migration_only_mfa_required",
                "auth_native_ceremony_endpoints": True,
                "auth_passkey_provider_configured": False,
                "auth_oidc_provider_configured": False,
                "setup_mode": "guided_ui_first",
                "setup_cli_required": False,
                "nullbridge_credentials_in_frontend": False,
            }
        ),
    )


def test_secure_signin_setup_gate_passes(monkeypatch, tmp_path):
    aibenchie_root = tmp_path / "AIBenchie"
    android_root = tmp_path / "NullXoidAndroid"
    wrapper_root = tmp_path / "Felnx" / "NullXoid" / ".NullXoid"
    write_policies(aibenchie_root)
    write_android_fixture(android_root)
    write_wrapper_fixture(wrapper_root)
    monkeypatch.setattr(secure_signin_setup, "request_raw", fake_features_request)

    result = secure_signin_setup.run_secure_signin_setup_check(
        root=aibenchie_root,
        android_repo=android_root,
        wrapper_repo=wrapper_root,
    )

    assert result.ok is True
    assert {check.name for check in result.checks} >= {
        "auth_policy",
        "setup_policy",
        "android_secure_signin_files",
        "wrapper_secure_signin_files",
        "hosted_features:/nullxoid/health/features",
    }


def test_secure_signin_setup_gate_fails_without_android_passkey_ui(monkeypatch, tmp_path):
    aibenchie_root = tmp_path / "AIBenchie"
    android_root = tmp_path / "NullXoidAndroid"
    wrapper_root = tmp_path / "Felnx" / "NullXoid" / ".NullXoid"
    write_policies(aibenchie_root)
    write_android_fixture(android_root)
    write_wrapper_fixture(wrapper_root)
    (android_root / "app/src/main/java/com/nullxoid/android/ui/auth/LoginScreen.kt").write_text(
        'Text("Sign in")\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(secure_signin_setup, "request_raw", fake_features_request)

    result = secure_signin_setup.run_secure_signin_setup_check(
        root=aibenchie_root,
        android_repo=android_root,
        wrapper_repo=wrapper_root,
    )

    assert result.ok is False
    failures = {check.name: check.failure for check in result.checks if not check.ok}
    assert failures["app/src/main/java/com/nullxoid/android/ui/auth/LoginScreen.kt:content"] == "missing_required_text"


def test_secure_signin_setup_gate_fails_when_hosted_features_return_html(monkeypatch, tmp_path):
    aibenchie_root = tmp_path / "AIBenchie"
    android_root = tmp_path / "NullXoidAndroid"
    wrapper_root = tmp_path / "Felnx" / "NullXoid" / ".NullXoid"
    write_policies(aibenchie_root)
    write_android_fixture(android_root)
    write_wrapper_fixture(wrapper_root)
    monkeypatch.setattr(
        secure_signin_setup,
        "request_raw",
        lambda *args, **kwargs: (200, "text/html", "<!DOCTYPE html><html>fallback</html>"),
    )

    result = secure_signin_setup.run_secure_signin_setup_check(
        root=aibenchie_root,
        android_repo=android_root,
        wrapper_repo=wrapper_root,
    )

    assert result.ok is False
    failures = {check.name: check.failure for check in result.checks if not check.ok}
    assert failures["hosted_features:/nullxoid/health/features"] == "nullxoid_health_features_returned_html"


def test_secure_signin_setup_cli_outputs_json(monkeypatch, capsys):
    class FakeResult:
        ok = True

        def as_dict(self):
            return {
                "ok": True,
                "root": "C:/repo",
                "android_repo": "C:/android",
                "wrapper_repo": "C:/wrapper",
                "public_api": PUBLIC_API,
                "origin": PUBLIC_ORIGIN,
                "base_path": "/nullxoid",
                "checks": [],
            }

    monkeypatch.setattr(aibenchie_local, "run_secure_signin_setup_from_env", lambda: FakeResult())

    code = aibenchie_local.main(["--secure-signin-setup", "--json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["public_api"] == PUBLIC_API
