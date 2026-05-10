# AIBenchie Universal E2E

AIBenchie Universal E2E is the standalone API and UX validation layer.

It is intentionally manifest-driven so AIBenchie can test EchoLabs, another web app, an Android app, a desktop app, a backend service, or a CLI without hardcoding product-specific assumptions into the runner.

## Lanes

```text
API E2E
  -> validates service contracts directly
  -> uses HTTP/SSE/WebSocket/shell adapters
  -> proves schemas, status, permissions, latency, and event behavior

UX E2E
  -> validates user workflows
  -> uses Playwright, ADB, desktop automation, or command adapters
  -> proves a real user can complete the task
```

Both lanes emit the same verdict schema:

```text
aibenchie.universal-e2e.verdict.v1
```

## EchoLabs API Example

```powershell
$env:AIBENCHIE_BACKEND_URL="http://127.0.0.1:8090"
python aibenchie_local.py --universal-e2e --universal-e2e-manifest configs/echolabs_universal_e2e.json --universal-e2e-lane api --json
```

For a hosted backend, set `AIBENCHIE_BACKEND_URL` to the hosted API origin.

Add `--universal-e2e-output _validation/aibenchie_universal_e2e_latest.json` to persist the verdict as a release artifact.

For the current public EchoLabs API route, use:

```powershell
.\scripts\echolabs_hosted_api_e2e.ps1
```

This defaults to `https://api.echolabs.diy/nullxoid` and writes `_validation/aibenchie_hosted_api_e2e_latest.json`.

The EchoLabs API lane also runs the BridgeEcho/NullBridge release gate through `scripts/nullbridge_release_gate.ps1`. Set `AIBENCHIE_ECHOLABS_BRIDGE_ROOT` when the NullBridge backend checkout is outside the default sibling `NullBridge/backend` path. The hosted HTTP target is optional by default so local API contract validation can run without a live deployment.

## EchoLabs UX Example

```powershell
$env:AIBENCHIE_ECHOLABS_WEB_ROOT="C:\Users\kasom\projects\NullXoid-live"
python aibenchie_local.py --universal-e2e --universal-e2e-manifest configs/echolabs_universal_e2e.json --universal-e2e-lane ux --json
```

The EchoLabs UX lane keeps the web shell build and NullXoid UI contract checks through `npm run verify:nullxoid`, then adds an optional `web_browser` target for the Playwright-style browser workflow. When Playwright is installed, the browser target builds the web app, serves the static output, opens `/nullxoid`, verifies visible user-facing text, and captures screenshot, HTML, and trace evidence. When Playwright is not installed, the optional target skips cleanly and the existing command target remains the required compatibility gate.

The same UX lane also runs the Android release gate through `scripts/android_release_gate.ps1`. Set `AIBENCHIE_ECHOLABS_ANDROID_ROOT` when the Android checkout is outside the default sibling `NullXoidAndroid` path.

It also runs the desktop release gate through `scripts/desktop_release_gate.ps1`. Set `AIBENCHIE_ECHOLABS_DESKTOP_ROOT` when the desktop checkout is outside the default sibling `AiAssistant` path.

## Manifest Shape

```json
{
  "schema": "aibenchie.universal-e2e.manifest.v1",
  "id": "my-program",
  "lanes": {
    "api": {
      "targets": [
        {
          "id": "backend",
          "adapter": "http",
          "base_url": "${ENV:MY_BACKEND_URL:-}",
          "checks": [
            { "path": "/health", "expect_status": 200 }
          ]
        }
      ]
    },
    "ux": {
      "targets": [
        {
          "id": "web",
          "adapter": "command",
          "command": ["npm", "run", "e2e"]
        }
      ]
    }
  }
}
```

## Current Foundation

Implemented now:

- JSON/YAML manifest loading.
- Environment substitution with `${ENV:NAME:-fallback}`.
- API lane HTTP checks.
- EchoLabs BridgeEcho/NullBridge API command target.
- UX lane command/manual target foundation.
- EchoLabs web UX command target.
- Optional EchoLabs web browser UX target with screenshot, HTML, and trace evidence.
- EchoLabs Android UX command target.
- EchoLabs desktop UX command target.
- Unified verdict with lane, target, evidence, and summary data.

Next adapters should add required Playwright runner packaging, ADB, desktop automation, SSE/WebSocket streams, broader artifact capture, and JUnit/HTML reporters without changing the manifest or verdict contract.

The next paused implementation item is tracked in `docs/SUITE_PRIORITY_BACKLOG.md` under "Universal E2E Playwright Web UX Adapter" so automation can resume the browser UX work without chat context.
