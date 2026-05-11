# EchoLabs App Release Checkpoint - 2026-05-11

Status: release gates pass; package shape is locally verified. AIBenchie remains the suite tester/release gate and is not published as a downloadable standalone product for this app release.

## Source Snapshot

| Repo | Branch | Commit | Notes |
| --- | --- | --- | --- |
| `echolabs-site` | `main` | `b6c44bc6ded730fb23e8e890e288bab92ede1f14` | Public site; hosted API E2E evidence refreshed after this snapshot. |
| `NullXoid-live` | `main` | `d1679ea41ebe6a907cb800777c647453b7e7901a` | Web app / NullXoid shell; hosted API E2E evidence refreshed after this snapshot. |
| `NullXoidAndroid` | `main` | `7f6cc678614e1a2445f9ba4d0669b0db8e670031` | Android app version `0.1.92`. |
| `AiAssistant` | `main` | `f3dc1add61010c9b1e0196c79c4fafb90ed6adcb` | Desktop / LV7 client. |
| `NullBridge/backend` | `main` | `1e84cce2fa5ec23563ebbe5b4acd4f03a45f209e` | BridgeEcho / NullBridge backend. |
| `AIBenchie` | `main` | `47d9c511c7f51b80388514c918207dd6f73cfbaf` | Tester/release gate docs include frontend scope. |

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
| `nullxoid-companion.apk` | `61c9bb2bfc12dc33f1da506724fbdb784695537bab47920956330b7c9ba863ea` |
| `echolabs-public-site.zip` | `fdd53aca3b7ae4a01602e0cd609ce80406a1f2830b208a14b2235d2e3f8ce2db` |

The local package proof used an ephemeral validation secret and key id `local-validation-key`. It proves package shape, manifest, SBOM, digest, and verifier behavior. It is not a production signing secret.

## Android Release State

| Item | Value |
| --- | --- |
| Application ID | `com.nullxoid.android` |
| Version code | `92` |
| Version name | `0.1.92` |
| Device-tested APK | `app\build\outputs\apk\debug\app-debug.apk` |
| Device-tested APK SHA-256 | `61c9bb2bfc12dc33f1da506724fbdb784695537bab47920956330b7c9ba863ea` |
| Debug signer SHA-256 | `67c1a0b4f47e9937a18e687d45b1fbc5d5936f3a50422deb6e7a3d820fcb53ab` |
| Release build output | `app\build\outputs\apk\release\app-release-unsigned.apk` |
| Release unsigned APK SHA-256 | `a67e5b7a9b0062117557d5098f896e808bc160f161a46dc8ae695a3b331b8ef1` |

The current Android foothold channel is the signed debug/prerelease update path. A production/store-style Android release still needs real signing credentials configured through `NULLXOID_SIGNING_STORE_FILE`, `NULLXOID_SIGNING_STORE_PASSWORD`, `NULLXOID_SIGNING_KEY_ALIAS`, and `NULLXOID_SIGNING_KEY_PASSWORD`, then a signed release artifact should be rebuilt and re-attested.

## Release Interpretation

- EchoLabs/NullXoid app release posture is green for the current prerelease/foothold channel.
- AIBenchie is active as the tester and release gate.
- AIBenchie standalone product downloads remain deferred until after app release/deployment is stable.
- Docker remains explicitly not supported as a release target.
- Android production signing is the main blocker for a store-style release artifact, but not for the current debug/prerelease foothold channel.
