from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


ANDROID_ONBOARDING_E2E_SCHEMA = "aibenchie.android-onboarding-e2e.v1"
DEFAULT_ANDROID_ONBOARDING_E2E_OUTPUT = Path(".suite/local/aibenchie/android-onboarding-e2e.json")

ONBOARDING_SCREEN = Path("app/src/main/java/com/nullxoid/android/ui/onboarding/OnboardingScreen.kt")
VIEW_MODEL = Path("app/src/main/java/com/nullxoid/android/ui/NullXoidViewModel.kt")
NAV_HOST = Path("app/src/main/java/com/nullxoid/android/ui/NullXoidNavHost.kt")
MAIN_ACTIVITY = Path("app/src/main/java/com/nullxoid/android/MainActivity.kt")
MANIFEST = Path("app/src/main/AndroidManifest.xml")
ONBOARDING_TEST = Path("app/src/test/java/com/nullxoid/android/ui/OnboardingUxTest.kt")
RELEASE_GATE = Path("scripts/android_release_gate.ps1")
SETUP_QR_DOC = Path("docs/NULLBRIDGE_SETUP_QR.md")
README = Path("README.md")


@dataclass(frozen=True)
class AndroidOnboardingCheck:
    name: str
    status: str
    required: bool
    summary: str
    failure: str = ""
    detail: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status in {"pass", "skip"}

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "ok": self.ok,
            "required": self.required,
            "summary": self.summary,
            "failure": self.failure,
            "detail": self.detail,
        }


def _check(
    name: str,
    status: str,
    summary: str,
    *,
    required: bool = True,
    failure: str = "",
    **detail: Any,
) -> AndroidOnboardingCheck:
    return AndroidOnboardingCheck(
        name=name,
        status=status,
        required=required,
        summary=summary,
        failure="" if status in {"pass", "skip"} else failure,
        detail={key: value for key, value in detail.items() if value not in ("", None, [], {})},
    )


def _git_value(root: Path, args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "unknown"


def _git_dirty(root: Path) -> bool | str:
    try:
        output = subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True, stderr=subprocess.DEVNULL)
    except Exception:
        return "unknown"
    return bool(output.strip())


def _repo_identity(root: Path) -> dict[str, Any]:
    return {
        "name": root.name,
        "path_label": root.name,
        "branch": _git_value(root, ["branch", "--show-current"]),
        "commit": _git_value(root, ["rev-parse", "HEAD"]),
        "dirty": _git_dirty(root),
    }


def _safe_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def _read_text(root: Path, relative_path: Path) -> str:
    path = root / relative_path
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _missing_needles(text: str, needles: list[str]) -> list[str]:
    return [needle for needle in needles if needle not in text]


def _class_fields(text: str, class_name: str) -> str:
    match = re.search(rf"data\s+class\s+{re.escape(class_name)}\s*\((.*?)\)\s*(?:\n|$)", text, re.DOTALL)
    return match.group(1) if match else ""


def _sequence_appears(text: str, first: str, second: str) -> bool:
    first_index = text.find(first)
    second_index = text.find(second)
    return first_index >= 0 and second_index >= 0 and first_index < second_index


def _gradle_command(root: Path) -> list[str]:
    gradlew_bat = root / "gradlew.bat"
    gradlew = root / "gradlew"
    executable = gradlew_bat if gradlew_bat.exists() else gradlew
    return [str(executable), ":app:testDebugUnitTest", "--tests", "com.nullxoid.android.ui.OnboardingUxTest"]


CommandRunner = Callable[[list[str], Path, int], subprocess.CompletedProcess[str]]


def _default_command_runner(command: list[str], cwd: Path, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_seconds,
        check=False,
    )


def _run_gradle_onboarding_test(
    root: Path,
    *,
    timeout_seconds: int,
    command_runner: CommandRunner | None,
) -> AndroidOnboardingCheck:
    command = _gradle_command(root)
    if not Path(command[0]).exists():
        return _check(
            "gradle_onboarding_test",
            "fail",
            "Focused Android onboarding unit test can run.",
            failure="gradle_wrapper_missing",
            command=command,
        )
    runner = command_runner or _default_command_runner
    try:
        result = runner(command, root, timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        return _check(
            "gradle_onboarding_test",
            "fail",
            "Focused Android onboarding unit test can run.",
            failure="gradle_timeout",
            command=command,
            timeout_seconds=timeout_seconds,
            stdout_tail=str(exc.stdout or "")[-1000:],
            stderr_tail=str(exc.stderr or "")[-1000:],
        )
    except Exception as exc:
        return _check(
            "gradle_onboarding_test",
            "fail",
            "Focused Android onboarding unit test can run.",
            failure="gradle_execution_failed",
            command=command,
            error=str(exc),
        )
    return _check(
        "gradle_onboarding_test",
        "pass" if result.returncode == 0 else "fail",
        "Focused Android onboarding unit test can run.",
        failure="gradle_test_failed",
        command=command,
        returncode=result.returncode,
        stdout_tail=str(result.stdout or "")[-1000:],
        stderr_tail=str(result.stderr or "")[-1000:],
    )


def run_android_onboarding_e2e(
    *,
    repo: str | Path,
    output: str | Path | None = None,
    run_gradle: bool = False,
    gradle_timeout_seconds: int = 240,
    command_runner: CommandRunner | None = None,
) -> dict[str, Any]:
    root = Path(repo).expanduser().resolve()
    checks: list[AndroidOnboardingCheck] = []

    checks.append(
        _check(
            "repo_exists",
            "pass" if root.exists() else "fail",
            "Android repository path is available.",
            failure="repo_missing",
            path=str(root),
        )
    )
    if not root.exists():
        payload = _payload(root, checks, run_gradle=run_gradle)
        return _write_payload(payload, output)

    required_files = [
        ONBOARDING_SCREEN,
        VIEW_MODEL,
        NAV_HOST,
        MAIN_ACTIVITY,
        MANIFEST,
        ONBOARDING_TEST,
        RELEASE_GATE,
    ]
    for relative_path in required_files:
        path = root / relative_path
        checks.append(
            _check(
                f"file:{relative_path.as_posix()}",
                "pass" if path.exists() else "fail",
                f"{relative_path.as_posix()} is present.",
                failure="required_file_missing",
                path=relative_path.as_posix(),
            )
        )

    onboarding = _read_text(root, ONBOARDING_SCREEN)
    view_model = _read_text(root, VIEW_MODEL)
    nav_host = _read_text(root, NAV_HOST)
    main_activity = _read_text(root, MAIN_ACTIVITY)
    manifest = _read_text(root, MANIFEST)
    onboarding_test = _read_text(root, ONBOARDING_TEST)
    release_gate = _read_text(root, RELEASE_GATE)
    setup_doc = _read_text(root, SETUP_QR_DOC)
    readme = _read_text(root, README)

    setup_qr_needles = [
        "rememberLauncherForActivityResult",
        "ScanContract",
        "ScanOptions.QR_CODE",
        "onboarding-scan-setup-qr",
        "Scan setup QR",
        "onApplySetupLink",
    ]
    missing_setup_qr = _missing_needles(onboarding, setup_qr_needles)
    checks.append(
        _check(
            "setup_qr_ui",
            "pass" if not missing_setup_qr else "fail",
            "Onboarding exposes a setup QR scanner that feeds the existing setup-link handler.",
            failure="setup_qr_ui_contract_missing",
            missing=missing_setup_qr,
        )
    )

    manual_needles = [
        "Backend address",
        "Save connection",
        "Check connection",
        "Outbound API",
        "Custom API",
        "Phone local",
    ]
    missing_manual = _missing_needles(onboarding, manual_needles)
    checks.append(
        _check(
            "manual_onboarding_preserved",
            "pass" if not missing_manual else "fail",
            "Manual backend onboarding remains available beside QR setup.",
            failure="manual_onboarding_regressed",
            missing=missing_manual,
        )
    )

    parser_needles = [
        "internal fun parseNullBridgeSetupLink",
        "scheme == \"nullxoid\"",
        "scheme == \"nullbridge\"",
        "host == \"setup.echolabs.diy\"",
        "host == \"www.echolabs.diy\"",
        "BackendEndpoint.normalize",
        "hasPairingToken",
        "applySetupLink",
    ]
    missing_parser = _missing_needles(view_model, parser_needles)
    checks.append(
        _check(
            "setup_link_parser",
            "pass" if not missing_parser else "fail",
            "Setup links accept approved QR/deep-link shapes and normalize the backend connection.",
            failure="setup_link_parser_contract_missing",
            missing=missing_parser,
        )
    )

    setup_link_fields = _class_fields(view_model, "NullBridgeSetupLink")
    stores_secret_token = bool(re.search(r"val\s+(token|pairingToken|pair|payload|code)\s*:", setup_link_fields))
    checks.append(
        _check(
            "setup_token_not_persisted_in_state",
            "pass" if setup_link_fields and not stores_secret_token else "fail",
            "Setup-link state stores only backend/source metadata and a token-present flag.",
            failure="setup_token_state_leak",
            fields=re.findall(r"val\s+([A-Za-z0-9_]+)\s*:", setup_link_fields),
        )
    )

    link_before_oidc = _sequence_appears(nav_host, "vm.applySetupLink(incomingUri.toString())", "vm.completeOidcSignIn(incomingUri)")
    nav_needles = [
        "incomingUri",
        "onIncomingUriConsumed",
        "onApplySetupLink = vm::applySetupLink",
    ]
    missing_nav = _missing_needles(nav_host, nav_needles)
    checks.append(
        _check(
            "incoming_link_dispatch",
            "pass" if not missing_nav and link_before_oidc else "fail",
            "Incoming setup links are dispatched before falling back to OIDC callback handling.",
            failure="incoming_link_dispatch_regressed",
            missing=missing_nav,
            setup_before_oidc=link_before_oidc,
        )
    )

    activity_needles = [
        "incomingUri = intent?.data",
        "onNewIntent",
        "incomingUri = intent.data",
        "onIncomingUriConsumed",
    ]
    missing_activity = _missing_needles(main_activity, activity_needles)
    checks.append(
        _check(
            "activity_deep_link_lifecycle",
            "pass" if not missing_activity else "fail",
            "Activity captures initial and resumed deep links for Compose navigation.",
            failure="activity_deep_link_lifecycle_missing",
            missing=missing_activity,
        )
    )

    manifest_needles = [
        'android:host="auth"',
        'android:path="/oidc/callback"',
        'android:host="setup"',
        'android:host="pair"',
        'android:scheme="nullbridge"',
        'android:host="setup.echolabs.diy"',
        'android:host="www.echolabs.diy"',
        'android:autoVerify="true"',
    ]
    missing_manifest = _missing_needles(manifest, manifest_needles)
    checks.append(
        _check(
            "manifest_deep_links",
            "pass" if not missing_manifest else "fail",
            "Android manifest keeps OIDC and adds approved setup QR/deep-link routes.",
            failure="manifest_deep_link_contract_missing",
            missing=missing_manifest,
        )
    )

    test_needles = [
        "setupLinksCanSeedConnectionWithoutReplacingManualOnboarding",
        "setupLinkParserRejectsUnrelatedUrls",
        "androidManifestKeepsSetupQrAsAdditiveDeepLink",
        "parseNullBridgeSetupLink",
        "setup.echolabs.diy",
    ]
    missing_tests = _missing_needles(onboarding_test, test_needles)
    if 'android:host="auth"' not in onboarding_test and 'android:host=\\"auth\\"' not in onboarding_test:
        missing_tests.append('android:host="auth"')
    checks.append(
        _check(
            "onboarding_unit_contract",
            "pass" if not missing_tests else "fail",
            "Android unit tests cover setup QR/link behavior and OIDC preservation.",
            failure="onboarding_unit_contract_missing",
            missing=missing_tests,
        )
    )

    checks.append(
        _check(
            "android_release_gate_includes_onboarding",
            "pass" if "com.nullxoid.android.ui.OnboardingUxTest" in release_gate else "fail",
            "Android release gate runs the onboarding UX contract.",
            failure="onboarding_test_not_release_blocking",
        )
    )

    doc_status = "pass" if "NullBridge setup QR" in setup_doc and "manual backend setup" in setup_doc else "fail"
    readme_status = "pass" if "NullBridge setup QR" in readme else "fail"
    checks.append(
        _check(
            "setup_qr_docs",
            "pass" if doc_status == "pass" and readme_status == "pass" else "fail",
            "Setup QR behavior is documented without replacing manual setup.",
            failure="setup_qr_docs_missing",
            doc_path=SETUP_QR_DOC.as_posix(),
            readme_mentions=readme_status == "pass",
        )
    )

    if run_gradle:
        checks.append(
            _run_gradle_onboarding_test(
                root,
                timeout_seconds=gradle_timeout_seconds,
                command_runner=command_runner,
            )
        )
    else:
        checks.append(
            _check(
                "gradle_onboarding_test",
                "skip",
                "Focused Android onboarding unit test was not requested.",
                required=False,
            )
        )

    payload = _payload(root, checks, run_gradle=run_gradle)
    return _write_payload(payload, output)


def _payload(root: Path, checks: list[AndroidOnboardingCheck], *, run_gradle: bool) -> dict[str, Any]:
    required_failures = [check for check in checks if check.required and not check.ok]
    warnings = [check for check in checks if check.status == "warn"]
    verdict = "fail" if required_failures else ("warn" if warnings else "pass")
    return {
        "schema": ANDROID_ONBOARDING_E2E_SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "ok": not required_failures,
        "verdict": verdict,
        "repo": _repo_identity(root) if root.exists() else {"name": root.name, "path_label": root.name, "dirty": "unknown"},
        "contract": {
            "name": "NullXoid Android onboarding setup QR",
            "manual_setup_required": True,
            "setup_qr_required": True,
            "oidc_callback_required": True,
            "pairing_token_policy": "presence_flag_only_until_backend_redeem_exists",
            "gradle_requested": run_gradle,
        },
        "summary": {
            "checks_total": len(checks),
            "required_failures": len(required_failures),
            "warnings": len(warnings),
            "passed": len([check for check in checks if check.status == "pass"]),
            "skipped": len([check for check in checks if check.status == "skip"]),
        },
        "checks": [check.as_dict() for check in checks],
    }


def _write_payload(payload: dict[str, Any], output: str | Path | None) -> dict[str, Any]:
    if output:
        output_path = Path(output).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        payload["output"] = str(output_path.resolve())
    return payload
