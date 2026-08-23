from __future__ import annotations

import json
import subprocess
from pathlib import Path

import aibenchie_local
from aibenchie.android_onboarding_e2e import ANDROID_ONBOARDING_E2E_SCHEMA, run_android_onboarding_e2e


def write_android_fixture(repo: Path, *, omit_qr: bool = False, omit_oidc: bool = False) -> None:
    onboarding = repo / "app/src/main/java/com/nullxoid/android/ui/onboarding/OnboardingScreen.kt"
    view_model = repo / "app/src/main/java/com/nullxoid/android/ui/NullXoidViewModel.kt"
    nav_host = repo / "app/src/main/java/com/nullxoid/android/ui/NullXoidNavHost.kt"
    main_activity = repo / "app/src/main/java/com/nullxoid/android/MainActivity.kt"
    manifest = repo / "app/src/main/AndroidManifest.xml"
    onboarding_test = repo / "app/src/test/java/com/nullxoid/android/ui/OnboardingUxTest.kt"
    release_gate = repo / "scripts/android_release_gate.ps1"
    setup_doc = repo / "docs/NULLBRIDGE_SETUP_QR.md"
    readme = repo / "README.md"

    for path in [onboarding, view_model, nav_host, main_activity, manifest, onboarding_test, release_gate, setup_doc]:
        path.parent.mkdir(parents=True, exist_ok=True)

    qr_block = (
        "rememberLauncherForActivityResult(ScanContract())\n"
        "ScanOptions.QR_CODE\n"
        "modifier = Modifier.testTag(\"onboarding-scan-setup-qr\")\n"
        "Text(\"Scan setup QR\")\n"
        "onApplySetupLink\n"
    )
    onboarding.write_text(
        """
Backend address
Save connection
Check connection
Outbound API
Custom API
Phone local
""".strip()
        + ("\n" + qr_block if not omit_qr else "\n"),
        encoding="utf-8",
    )
    view_model.write_text(
        """
data class NullBridgeSetupLink(
    val backendUrl: String,
    val hasPairingToken: Boolean,
    val source: String
)

internal fun parseNullBridgeSetupLink(raw: String): NullBridgeSetupLink? {
    scheme == "nullxoid"
    scheme == "nullbridge"
    host == "setup.elabs.test"
    host == "www.elabs.test"
    BackendEndpoint.normalize(raw, SettingsStore.PUBLIC_BACKEND_URL)
    hasPairingToken
}

fun applySetupLink(raw: String): Boolean = parseNullBridgeSetupLink(raw) != null
""".strip(),
        encoding="utf-8",
    )
    nav_host.write_text(
        """
incomingUri
onIncomingUriConsumed
if (!vm.applySetupLink(incomingUri.toString())) {
    vm.completeOidcSignIn(incomingUri)
}
onApplySetupLink = vm::applySetupLink
""".strip(),
        encoding="utf-8",
    )
    main_activity.write_text(
        """
incomingUri = intent?.data
onIncomingUriConsumed
override fun onNewIntent(intent: Intent) {
    incomingUri = intent.data
}
""".strip(),
        encoding="utf-8",
    )
    manifest.write_text(
        """
<manifest>
  <activity>
    <intent-filter>
      <data android:host="auth" android:path="/oidc/callback" android:scheme="nullxoid" />
    </intent-filter>
    <intent-filter>
      <data android:host="setup" android:pathPrefix="/pair" android:scheme="nullxoid" />
      <data android:host="pair" android:scheme="nullxoid" />
      <data android:host="pair" android:scheme="nullbridge" />
    </intent-filter>
    <intent-filter android:autoVerify="true">
      <data android:host="setup.elabs.test" android:pathPrefix="/nullbridge/pair" android:scheme="https" />
      <data android:host="www.elabs.test" android:pathPrefix="/setup/nullbridge" android:scheme="https" />
    </intent-filter>
  </activity>
</manifest>
""".replace('android:host="auth"', "" if omit_oidc else 'android:host="auth"'),
        encoding="utf-8",
    )
    onboarding_test.write_text(
        """
setupLinksCanSeedConnectionWithoutReplacingManualOnboarding
setupLinkParserRejectsUnrelatedUrls
androidManifestKeepsSetupQrAsAdditiveDeepLink
parseNullBridgeSetupLink
setup.elabs.test
android:host="auth"
""".strip(),
        encoding="utf-8",
    )
    release_gate.write_text('"--tests", "com.nullxoid.android.ui.OnboardingUxTest"', encoding="utf-8")
    setup_doc.write_text(
        "NullBridge setup QR is additive and does not replace manual backend setup.\n",
        encoding="utf-8",
    )
    readme.write_text("NullBridge setup QR is documented.\n", encoding="utf-8")


def test_android_onboarding_e2e_passes_setup_contract(tmp_path):
    repo = tmp_path / "NullXoidAndroid"
    write_android_fixture(repo)
    output = tmp_path / "verdict.json"

    result = run_android_onboarding_e2e(repo=repo, output=output)
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert result["schema"] == ANDROID_ONBOARDING_E2E_SCHEMA
    assert result["ok"] is True
    assert result["verdict"] == "pass"
    assert result["contract"]["manual_setup_required"] is True
    assert payload["ok"] is True


def test_android_onboarding_e2e_fails_when_setup_qr_is_removed(tmp_path):
    repo = tmp_path / "NullXoidAndroid"
    write_android_fixture(repo, omit_qr=True)

    result = run_android_onboarding_e2e(repo=repo)
    checks = {check["name"]: check for check in result["checks"]}

    assert result["ok"] is False
    assert result["verdict"] == "fail"
    assert checks["setup_qr_ui"]["failure"] == "setup_qr_ui_contract_missing"


def test_android_onboarding_e2e_fails_when_oidc_callback_is_removed(tmp_path):
    repo = tmp_path / "NullXoidAndroid"
    write_android_fixture(repo, omit_oidc=True)

    result = run_android_onboarding_e2e(repo=repo)
    checks = {check["name"]: check for check in result["checks"]}

    assert result["ok"] is False
    assert checks["manifest_deep_links"]["failure"] == "manifest_deep_link_contract_missing"
    assert 'android:host="auth"' in checks["manifest_deep_links"]["detail"]["missing"]


def test_android_onboarding_e2e_can_run_gradle_with_fake_runner(tmp_path):
    repo = tmp_path / "NullXoidAndroid"
    write_android_fixture(repo)
    (repo / "gradlew.bat").write_text("@echo off\n", encoding="utf-8")

    def fake_runner(command: list[str], cwd: Path, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
        assert cwd == repo.resolve()
        assert timeout_seconds == 11
        assert command[1:] == [":app:testDebugUnitTest", "--tests", "com.nullxoid.android.ui.OnboardingUxTest"]
        return subprocess.CompletedProcess(command, 0, stdout="BUILD SUCCESSFUL", stderr="")

    result = run_android_onboarding_e2e(
        repo=repo,
        run_gradle=True,
        gradle_timeout_seconds=11,
        command_runner=fake_runner,
    )
    checks = {check["name"]: check for check in result["checks"]}

    assert result["ok"] is True
    assert checks["gradle_onboarding_test"]["status"] == "pass"


def test_android_onboarding_e2e_cli(capsys, monkeypatch, tmp_path):
    output = tmp_path / "onboarding.json"

    def fake_gate(**kwargs):
        assert kwargs["repo"] == "C:/repo"
        assert kwargs["output"] == str(output)
        assert kwargs["run_gradle"] is True
        assert kwargs["gradle_timeout_seconds"] == 99
        return {
            "schema": ANDROID_ONBOARDING_E2E_SCHEMA,
            "ok": True,
            "verdict": "pass",
            "repo": {"name": "repo", "branch": "main", "commit": "abcdef123456"},
            "contract": {"name": "NullXoid Android onboarding setup QR", "gradle_requested": True},
            "checks": [],
        }

    monkeypatch.setattr(aibenchie_local, "run_android_onboarding_e2e", fake_gate)

    exit_code = aibenchie_local.main(
        [
            "--android-onboarding-e2e",
            "--android-onboarding-repo",
            "C:/repo",
            "--android-onboarding-output",
            str(output),
            "--android-onboarding-run-gradle",
            "--android-onboarding-gradle-timeout",
            "99",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["schema"] == ANDROID_ONBOARDING_E2E_SCHEMA
    assert payload["ok"] is True
