# Elabs Suite Release Gates

Run this from the AIBenchie repo before a release handoff:

```powershell
.\scripts\echolabs_suite_release_gate.ps1 -DesktopIncludeUi -BridgeFull
```

The default report is written to:

```text
_validation/echolabs_suite_gate_latest.json
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

For reconciled or multiple checkouts, select `-WebRepository`,
`-AndroidRepository`, `-DesktopRepository`, `-BridgeRepository`, and
`-Lv7Repository` explicitly. Relative paths resolve under `-SuiteRoot`; the report
records the resolved directories. Multiple web checkouts block implicit selection.
Each selected repository must provide the gate command listed below. In particular,
a backend/frontend-layout candidate without `release:gate` must use its pinned
release-preparation workflow, not silently substitute an older web-shell checkout.

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
| AIBenchie deploy plan proof | `python aibenchie_local.py --verify-deploy-plan --deploy-plan <path> --json` | Required unless explicitly skipped for a partial diagnostic run. A missing file blocks before tests run. |
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

Release interpretation (corrected 2026-09-14):

- `pass` / exit 0 means all required selected commands ran successfully, with
  desktop UI and full bridge checks included. It is not deployment authorization.
  `coverage_complete` is true only in that case; `deployment_authorized` is always
  false in this execution report. Separately bind current evidence and actual
  built artifact hashes to the candidate before approving any deployment.
- Any `-Skip*`, omitted desktop UI, or omitted full bridge check produces
  `incomplete` / exit 2, with explicit `SKIPPED` entries. Even an all-skipped run
  cannot report success. Partial diagnostic runs remain available.
- Missing deployment proof, missing device proof (unless being generated), missing
  repositories, and ambiguous web selection produce `blocked` / exit 2 before
  surface commands run. Disappearing inputs or command failures cannot leave a
  previous successful report in place. A new run first records `running`.
- Deploy-plan validation checks structure and public safety; it does not prove
  artifact existence, that hashes match this candidate, or backup restoration.
  Previously saved local proof is not automatically current evidence.
- Real-device proof is required for full coverage. Use `-AndroidRealDeviceUXPreflight`
  when diagnosing readiness; preflight is not sign-in/chat proof. Generate proof
  only after actually completing the reported workflows, with the existing explicit
  sign-in/chat confirmation flags. A screenshot hash is supporting evidence, not
  a substitute for those checks. No physical-device result is asserted by the
  runner's synthetic regression tests.
- Any gate fails: fix that surface first, then rerun the failed surface gate before rerunning the suite gate.
- Docker support is coming soon, but Docker is not a supported release target yet. The current AIBenchie `--docker-support` gate enforces that guarded boundary and blocks tracked Docker entrypoints before supported-mode Docker exists. A future Docker path must evolve that gate before container images or Compose files are advertised as production-ready.
- The JSON report uses schema `echolabs.suite-release-gate.v1`; consumers must honor
  `blocked`, `incomplete`, and `running`, not display them as a release pass.
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
