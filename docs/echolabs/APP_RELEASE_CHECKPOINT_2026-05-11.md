# EchoLabs App Release Checkpoint - 2026-05-11

Status: release gates pass; package shape is locally verified. AIBenchie remains the suite tester/release gate and is not published as a downloadable standalone product for this app release.

## Source Snapshot

| Repo | Branch | Commit | Notes |
| --- | --- | --- | --- |
| `echolabs-site` | `main` | `b6c44bc6ded730fb23e8e890e288bab92ede1f14` | Public site; hosted API E2E evidence refreshed after this snapshot. |
| `NullXoid-live` | `main` | `d1679ea41ebe6a907cb800777c647453b7e7901a` | Web app / NullXoid shell; hosted API E2E evidence refreshed after this snapshot. |
| `NullXoidAndroid` | `main` | `7f6cc678614e1a2445f9ba4d0669b0db8e670031` | Android app version `0.1.93` published as the current debug/prerelease foothold build. |
| `AiAssistant` | `main` | `f3dc1add61010c9b1e0196c79c4fafb90ed6adcb` | Desktop / LV7 client. |
| `NullBridge/backend` | `main` | `1e84cce2fa5ec23563ebbe5b4acd4f03a45f209e` | BridgeEcho / NullBridge backend. |
| `AIBenchie` | `main` | `47d9c511c7f51b80388514c918207dd6f73cfbaf` | Tester/release gate docs include frontend scope. |
| `.NullXoid` wrapper backend | `main` | `51bc3c222d5a0aa5af3167412379fa63539fca02` | Preserves the NullBridge `processed` result-status handling fix and unblocks wrapper deploy. |

## Gate Results

Full suite gate:

```powershell
.\scripts\echolabs_suite_release_gate.ps1
```

Result: `PASS`

Evidence path: `C:\Users\kasom\projects\_validation\echolabs_suite_gate_latest.json`

Surfaces:

| Surface | Result |
| --- | --- |
| EchoLabs web shell | PASS |
| NullXoid Android | PASS |
| NullXoid Desktop | PASS |
| BridgeEcho / NullBridge backend | PASS |
| AIBenchie Universal API/UX E2E | PASS |
| AIBenchie deploy plan proof | PASS |
| AIBenchie Docker support boundary | PASS |
| AIBenchie real-device UX proof | PASS |

Additional checks:

| Check | Result |
| --- | --- |
| Public route verification for `https://www.echolabs.diy` | PASS |
| Hosted API E2E for `https://api.echolabs.diy/nullxoid` | PASS |
| Android real-device UX preflight | PASS |
| Android release build | PASS, unsigned APK produced |

## Artifact Evidence

Local package evidence was generated under the ignored runtime path:

```text
AIBenchie\.suite\local\aibenchie\release-packages\release-artifacts.json
```

The package verifier passed with three required artifact kinds: `wrapper`, `android`, and `public`.

| Artifact | SHA-256 |
| --- | --- |
| `nullxoid-wrapper.zip` | `49d08dc8fc65a1837a6045f19c6896c49d5ad0ebcb58d3af4bcd0495f5ba0259` |
| `nullxoid-companion.apk` | `7ddfdc55791351ff001398c8da211e0686cff432b0d1ad86d14d2f079da52126` |
| `echolabs-public-site.zip` | `fdd53aca3b7ae4a01602e0cd609ce80406a1f2830b208a14b2235d2e3f8ce2db` |

The local package proof used an ephemeral validation secret and key id `local-validation-key`. It proves package shape, manifest, SBOM, digest, and verifier behavior. It is not a production signing secret.

## Android Release State

| Item | Value |
| --- | --- |
| Application ID | `com.nullxoid.android` |
| Version code | `93` |
| Version name | `0.1.93` |
| Device-tested APK | `app\build\outputs\apk\debug\app-debug.apk` |
| Device-tested APK SHA-256 | `7ddfdc55791351ff001398c8da211e0686cff432b0d1ad86d14d2f079da52126` |
| Debug signer SHA-256 | `67c1a0b4f47e9937a18e687d45b1fbc5d5936f3a50422deb6e7a3d820fcb53ab` |
| Release build output | `app\build\outputs\apk\release\app-release-unsigned.apk` |
| Release unsigned APK SHA-256 | `a67e5b7a9b0062117557d5098f896e808bc160f161a46dc8ae695a3b331b8ef1` |

The current Android foothold channel is the signed debug/prerelease update path. `v0.1.93` was published to Forgejo and `latest-debug` was moved to the same APK. The published `v0.1.93` and `latest-debug` assets both hash to `7ddfdc55791351ff001398c8da211e0686cff432b0d1ad86d14d2f079da52126` and target commit `7f6cc678614e1a2445f9ba4d0669b0db8e670031`.

The connected Android test phone was updated to `0.1.93`, and AIBenchie real-device preflight passed for `com.nullxoid.android` version `0.1.93`. Physical sign-in and chat were re-run after the RuntimeEcho model fix, and the current real-device UX proof is `android-real-device-ux-20260511T125801Z` for version `0.1.93`.

RuntimeEcho now routes normal hosted chat to CT729's dedicated llama.cpp text service at `http://192.168.1.244:8081` with `Qwen/Qwen3-4B-GGUF`. CT729's existing VL service remains separate on port `8080` for `Qwen/Qwen3-VL-8B-Instruct-GGUF`, so Android normal chat no longer defaults to a VL model.

A production/store-style Android release still needs real signing credentials configured through `NULLXOID_SIGNING_STORE_FILE`, `NULLXOID_SIGNING_STORE_PASSWORD`, `NULLXOID_SIGNING_KEY_ALIAS`, and `NULLXOID_SIGNING_KEY_PASSWORD`, then a signed release artifact should be rebuilt and re-attested.

## Wrapper Deploy State

The CT400 wrapper deploy service was blocked by a dirty staging/live backend checkout containing the NullBridge `processed` result-status fix. That patch was tested with:

```text
backend/tests/test_nullbridge_adapter.py: 12 passed
```

The fix was committed to `.NullXoid` as `51bc3c222d5a0aa5af3167412379fa63539fca02`, the live checkout was reset to that upstream commit after saving a patch backup under `/home/deploy/repo-backups/`, and `nullxoid-wrapper-deploy.service` now exits successfully. The backend was restarted after the deploy cleanup, and hosted API E2E passed again.

## Release Interpretation

- EchoLabs/NullXoid app release posture is green for the current prerelease/foothold channel.
- AIBenchie is active as the tester and release gate.
- AIBenchie standalone product downloads remain deferred until after app release/deployment is stable.
- Docker remains explicitly not supported as a release target.
- Android production signing is the main blocker for a store-style release artifact, but not for the current debug/prerelease foothold channel.

