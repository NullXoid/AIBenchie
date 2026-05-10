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
- UX lane command/manual target foundation.
- Unified verdict with lane, target, evidence, and summary data.

Next adapters should add Playwright, ADB, desktop automation, SSE/WebSocket streams, artifact capture, screenshot capture, and JUnit/HTML reporters without changing the manifest or verdict contract.
