# Android Real-Device UX Proof - 2026-05-11

## Result

The Android real-device UX proof passed for the EchoLabs Suite release checkpoint.

## Scope

- Platform: Android
- Package: `com.nullxoid.android`
- App version: `0.1.93`
- Runtime: `llamacpp` / `Qwen/Qwen3-4B-GGUF` / `ct729-text-8081`
- Workflows proven: sign-in and chat
- Proof id: `android-real-device-ux-20260511T131112Z`
- Proof validation: 14 checks passed, 0 failed
- Suite gate result: 8 passing surfaces, 0 failed

## Privacy Boundary

The proof uses a hashed device identifier and public-safe metadata only. Raw device serials, screenshots, local proof bundles, encrypted full reports, and local keys remain ignored runtime artifacts.

## Verification Commands

```powershell
adb devices
python aibenchie_local.py --android-real-device-ux-preflight --json
python aibenchie_local.py --emit-android-real-device-ux-proof --real-device-ux-signin-passed --real-device-ux-chat-passed --real-device-ux-runtime-provider llamacpp --real-device-ux-runtime-model "Qwen/Qwen3-4B-GGUF" --real-device-ux-runtime-endpoint-label ct729-text-8081 --real-device-ux-capture-screenshot --json
python aibenchie_local.py --real-device-ux-proof .suite\local\aibenchie\android-real-device-ux.json --json
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\echolabs_suite_release_gate.ps1 -GenerateAndroidRealDeviceUXProof -AndroidRealDeviceUXSigninPassed -AndroidRealDeviceUXChatPassed -RealDeviceUXRuntimeProvider llamacpp -RealDeviceUXRuntimeModel "Qwen/Qwen3-4B-GGUF" -RealDeviceUXRuntimeEndpointLabel ct729-text-8081
```

## Release Evidence

The public EchoLabs web evidence was refreshed from the sanitized AIBenchie summary. The website evidence now reports:

- Latest verdict: `pass`
- Suite gate: `8/8`
- Real-device UX: `pass`
- Real-device proof id: `android-real-device-ux-20260511T131112Z`

## Runtime Notes

The proof was regenerated after RuntimeEcho was moved off the temporary workstation Ollama endpoint and onto the dedicated CT729 llama.cpp text runtime:

- CT729 `llama-server.service`: port `8080`, `Qwen/Qwen3-VL-8B-Instruct-GGUF`, vision/VL runtime.
- CT729 `llama-server-text.service`: port `8081`, `Qwen/Qwen3-4B-GGUF`, normal text chat runtime.
- CT400 RuntimeEcho default: `http://192.168.1.244:8081`, model `Qwen/Qwen3-4B-GGUF`.

The physical Android chat path returned a visible response through the CT729 text runtime and no longer exposes the VL model as the normal-chat default.

## Deployment Smoke

Local production preview passed for `/aibenchie`, `/aibenchie/latest-verdict.json`, and `/aibenchie/release-evidence.json`.

Canonical public deployment passed on `https://www.echolabs.diy` after the public-site deploy path was corrected.

- `https://www.echolabs.diy/aibenchie`: `200`
- Public route verification: 7 app routes and 8 content routes passed
- `https://www.echolabs.diy/content/verdicts/aibenchie-latest-verdict.json`: suite gate `8/8`
- `https://www.echolabs.diy/content/verdicts/aibenchie-release-evidence.json`: real-device UX `pass`

The older `https://echolabs.netlify.app` route is not the canonical deployment for this evidence and should not be used as the release smoke target.

