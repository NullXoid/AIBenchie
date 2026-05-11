# Android Real-Device UX Proof - 2026-05-11

## Result

The Android real-device UX proof passed for the EchoLabs Suite release checkpoint.

## Scope

- Platform: Android
- Package: `com.nullxoid.android`
- App version: `0.1.92`
- Workflows proven: sign-in and chat
- Proof id: `android-real-device-ux-20260511T095838Z`
- Proof validation: 13 checks passed, 0 failed
- Suite gate result: 8 passing surfaces, 0 failed

## Privacy Boundary

The proof uses a hashed device identifier and public-safe metadata only. Raw device serials, screenshots, local proof bundles, encrypted full reports, and local keys remain ignored runtime artifacts.

## Verification Commands

```powershell
adb devices
python aibenchie_local.py --android-real-device-ux-preflight --json
python aibenchie_local.py --emit-android-real-device-ux-proof --real-device-ux-signin-passed --real-device-ux-chat-passed --real-device-ux-capture-screenshot --json
python aibenchie_local.py --real-device-ux-proof .suite\local\aibenchie\android-real-device-ux.json --json
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\echolabs_suite_release_gate.ps1
```

## Release Evidence

The public EchoLabs web evidence was refreshed from the sanitized AIBenchie summary. The website evidence now reports:

- Latest verdict: `pass`
- Suite gate: `8/8`
- Real-device UX: `pass`
- Real-device proof id: `android-real-device-ux-20260511T095838Z`

## Deployment Smoke

Local production preview passed for `/aibenchie`, `/aibenchie/latest-verdict.json`, and `/aibenchie/release-evidence.json`.

Canonical public deployment passed on `https://www.echolabs.diy` after the public-site deploy path was corrected.

- `https://www.echolabs.diy/aibenchie`: `200`
- Public route verification: 7 app routes and 8 content routes passed
- `https://www.echolabs.diy/content/verdicts/aibenchie-latest-verdict.json`: suite gate `8/8`
- `https://www.echolabs.diy/content/verdicts/aibenchie-release-evidence.json`: real-device UX `pass`

The older `https://echolabs.netlify.app` route is not the canonical deployment for this evidence and should not be used as the release smoke target.
