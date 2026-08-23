# Elabs Suite Release Gates

Run this from the AIBenchie repo before a release handoff:

```powershell
.\scripts\echolabs_suite_release_gate.ps1
```

The default report is written to:

```text
_validation/Elabs_suite_gate_latest.json
```

The Universal E2E verdict is written beside it:

```text
_validation/aibenchie_universal_e2e_latest.json
```

To explicitly verify the public hosted API route, run:

```powershell
.\scripts\Elabs_hosted_api_e2e.ps1
```

That wrapper sets `AIBENCHIE_BACKEND_URL` to `https://api.elabs.test/nullxoid` unless overridden and writes `_validation/aibenchie_hosted_api_e2e_latest.json`.

The script auto-detects the parent workspace when AIBenchie is checked out next to the Elabs repos. Use `-SuiteRoot` for a different layout:

```powershell
.\scripts\echolabs_suite_release_gate.ps1 -SuiteRoot <workspace>
```

Use `-ReportPath` to write a separate handoff artifact:

```powershell
.\scripts\echolabs_suite_release_gate.ps1 -ReportPath _validation/Elabs_suite_gate_2026-05-09.json
```

The suite gate runs each surface-owned gate in order:

| Surface | Command | Purpose |
| --- | --- | --- |
| Elabs web shell | `npm run release:gate` | Add-on manifests, readiness policy, AIBenchie security gates, NullXoid UI verification, build, dependency audit. |
| NullXoid Android | `.\scripts\android_release_gate.ps1` | Model policy, chat/store contracts, 3D prerelease polish, E2EE, NullBridge adapter, product IA, debug APK build. |
| AIBenchie Android onboarding E2E | `python aibenchie_local.py --android-onboarding-e2e --android-onboarding-repo <NullXoidAndroid> --json` | Release-blocking onboarding setup QR/deep-link contract. Verifies manual setup stays available, QR setup is additive, OIDC is preserved, and the Android release gate includes onboarding coverage. |
| NullXoid Desktop | `.\scripts\desktop_release_gate.ps1` | Desktop model policy regression, unit tests, bridge tests, smoke tests. |
| BridgeEcho / NullBridge backend | `.\scripts\nullbridge_release_gate.ps1` | Service bridge compliance, approval routing, trust fabric, signed envelopes, observability redaction. |
| AIBenchie Universal API/UX E2E | `python aibenchie_local.py --universal-e2e ... --universal-e2e-lane all --json` | Standalone manifest-driven API and UX validation across BridgeEcho, web, Android, and desktop surfaces. |
| AIBenchie deploy plan proof | `python aibenchie_local.py --verify-deploy-plan --deploy-plan <path> --json` | Optional local deploy-plan proof. Runs only when the ignored local deploy plan exists unless `-DeployPlanPath` points elsewhere. |
| Distribution hygiene | `python aibenchie_local.py --distribution-hygiene --distribution-hygiene-root <repo> --json` | Blocks private runtime data, raw owner media/transcripts, secrets, signing material, and local distribution metadata leaks across available suite repos. |

Useful options:

```powershell
.\scripts\echolabs_suite_release_gate.ps1 -SkipAndroid
.\scripts\echolabs_suite_release_gate.ps1 -SkipDesktop
.\scripts\echolabs_suite_release_gate.ps1 -SkipUniversalE2E
.\scripts\echolabs_suite_release_gate.ps1 -SkipDeployPlan
.\scripts\echolabs_suite_release_gate.ps1 -DesktopIncludeUi
.\scripts\echolabs_suite_release_gate.ps1 -BridgeFull
.\scripts\echolabs_suite_release_gate.ps1 -DeployPlanPath .suite\local\aibenchie\deploy-plan.json
.\scripts\echolabs_suite_release_gate.ps1 -SkipDistributionHygiene
.\scripts\echolabs_suite_release_gate.ps1 -SkipWeb -SkipAndroid -SkipDesktop -SkipBridge -SkipUniversalE2E -SkipDeployPlan -SkipDockerSupport -AndroidRealDeviceUXPreflight
.\scripts\echolabs_suite_release_gate.ps1 -GenerateAndroidRealDeviceUXProof -AndroidRealDeviceUXSigninPassed -AndroidRealDeviceUXChatPassed -RealDeviceUXRuntimeProvider llamacpp -RealDeviceUXRuntimeModel "Qwen/Qwen3-4B-GGUF" -RealDeviceUXRuntimeEndpointLabel ct729-text-8081 -CaptureAndroidRealDeviceUXScreenshot
```

Release interpretation:

- All default gates pass: the suite is locally stable for handoff.
- Optional UI/full backend gates pass: stronger local confidence before packaging.
- Optional deploy-plan proof passes: ignored local deploy evidence is well-formed and public-safe enough to feed release evidence.
- Optional real-device UX proof passes: ignored physical-device evidence is public-safe and includes required workflows such as Android sign-in and chat. Use `-AndroidRealDeviceUXPreflight` when diagnosing device readiness; it only checks hashed adb/package state and does not create release proof. Add `-RealDeviceUXAdbSerial <adb-serial>` when multiple adb devices are attached. The suite gate also runs this preflight before `-GenerateAndroidRealDeviceUXProof`. Use proof generation only with explicit `-AndroidRealDeviceUXSigninPassed` and `-AndroidRealDeviceUXChatPassed` operator confirmation after those workflows have passed on the connected adb device. Add `-RealDeviceUXRuntimeProvider`, `-RealDeviceUXRuntimeModel`, and `-RealDeviceUXRuntimeEndpointLabel` so Android chat results can be traced to a specific model/runtime. Add `-CaptureAndroidRealDeviceUXScreenshot` to store an ignored local screenshot artifact and record only its hash in the proof.
- Any gate fails: fix that surface first, then rerun the failed surface gate before rerunning the suite gate.
- Docker support is coming soon, but Docker is not a supported release target yet. The current AIBenchie `--docker-support` gate enforces that guarded boundary and blocks tracked Docker entrypoints before supported-mode Docker exists. A future Docker path must evolve that gate before container images or Compose files are advertised as production-ready.
- The JSON report uses schema `Elabs.suite-release-gate.v1` and is suitable for AIBenchie ingestion or Elabs readiness display.
- Each surface entry includes stable machine fields for dashboards and AIBenchie ingestion:

```json
{
  "id": "echolabs_web",
  "name": "Elabs web shell",
  "owner": "Elabs / NullXoid Chat",
  "status": "PASS",
  "duration_ms": 12000,
  "command": "npm run release:gate",
  "working_directory": "NullXoid-live"
}
```

Elabs' AIBenchie verdict exporter accepts both this lowercase shape and older reports that used `Name`, `Status`, and `DurationMs`.
