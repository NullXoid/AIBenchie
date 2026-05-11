# EchoLabs Frontend Feature Matrix

This matrix defines the current release scope for each frontend. AIBenchie remains the tester and release gate for the suite, but it is not published as a downloadable user product in this release.

## Release Rule

- EchoLabs/NullXoid release is blocked by AIBenchie gates.
- EchoLabs/NullXoid release is not blocked by standalone AIBenchie productization.
- AIBenchie public evidence may be surfaced on EchoLabs pages.
- AIBenchie binaries/packages/downloads are deferred until the post-release productization lane.

## Frontend Ownership

| Frontend | Role | Current release features | Explicit non-goals for this release |
| --- | --- | --- | --- |
| EchoLabs public site | Public website, proof, release evidence, project documentation | Home, projects, blog, about, deep dives, public NullXoid route/fallback, AIBenchie evidence page, public route verification, deploy guard evidence | Normal chat runtime, model management, E2EE app state, CCC execution, admin service controls |
| EchoLabs / NullXoid web app | Main lab/OS shell and richest suite UI | NullXoid chat surface, release readiness, Backend Operations UI, Resource Manager visibility, AIBenchie gate surfacing, model policy signals, artifacts/gallery, media job contracts, 3D artifact handling, CCC/Canvas integration, add-on/readiness structures | Publishing AIBenchie as a user app, exposing BridgeEcho controls to normal users, replacing platform-native Android/Desktop clients |
| NullXoid Android | Mobile chat/media/runtime client | Login/onboarding, QR-first setup, passkey/OIDC structures, chat list/detail, health/settings, backend profile, model selection, embedded runtime concepts, store/gallery/jobs, image/video/3D entries, 3D fallback labels, update checks, E2EE saved-chat envelope support, real-device UX proof | Full CCC workspace, admin bridge console, downloadable AIBenchie product, desktop LV7 control surface |
| NullXoid Desktop / Windows | Native Windows chat/runtime/LV7 client | Authenticated shell, backend-backed model selection, chat streaming, model warm/status controls, chat management, settings dock, voice status/toggle, Codex Canvas shell, file/artifact shell, LV7 controls and two-pass runtime path | Full media/gallery parity, Canvas execution parity with web, Android-specific flows, standalone AIBenchie publishing |
| CCC / Canvas | Coding workspace and preview/display surface | Web-first CCC integration, Canvas display/artifact surface, desktop Canvas shell for files and artifacts | Treating Canvas as a fully separate app before it needs independent use, forcing CCC onto Android before a mobile coding UX is designed |
| Backend Operations / Admin | Read-only operational status and gated admin visibility | Health, deploy status, AIBenchie gates, resource pressure, Resource Manager proof, runtime status, notification proof, public-safe evidence | Normal-user BridgeEcho access, frontend storage of service credentials, secret exposure |
| AIBenchie evidence surface | Public release/test evidence display | Public-safe verdicts, scoreboards, Android real-device UX proof, hosted stack evidence, release-gate status | Downloadable standalone AIBenchie product, arbitrary third-party app testing as a public release feature |

## Remaining Product Gaps

| Gap | Primary frontend | Release posture |
| --- | --- | --- |
| Speech-to-speech UX | Web, Android, Desktop | Product polish lane; not a reason to restart the app. |
| 3D wrapping/material preview polish | Web, Android | Improve preview confidence, labels, and map/material handling. |
| CCC/Canvas maturity outside web | Desktop first, Android later only if justified | Keep web as the strongest CCC/Canvas surface for release. |
| Standalone AIBenchie product | AIBenchie | Post-release only; keep it as tester now, not a download. |

## Release Interpretation

The app release target is EchoLabs/NullXoid across public site, web app, Android, desktop, backend operations, CCC/Canvas, and public evidence. AIBenchie remains part of the release system because it tests and proves the suite, but standalone AIBenchie product packaging, downloads, and third-party onboarding are deferred.
