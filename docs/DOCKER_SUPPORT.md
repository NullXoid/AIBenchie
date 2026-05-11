# Docker Support Status

Status: coming soon. Docker is not a supported EchoLabs Suite deployment path yet.

The current release path is still repo-native: each surface runs its own local release gate, AIBenchie verifies the suite verdict, and release packages are attested before deployment. Do not advertise Docker, Docker Compose, or container images as production-ready until this document changes status and a Docker-specific AIBenchie gate passes.

## Current Boundary

- No tracked `Dockerfile`, `docker-compose.yml`, or published container image is part of the supported suite.
- Docker commands in outside notes are experimental operator work only.
- Existing release gates remain authoritative: EchoLabs web, Android, Desktop, NullBridge, and AIBenchie Universal E2E.
- Provider tokens, service credentials, private hostnames, E2EE recovery material, and release signing secrets must stay in runtime secret storage, never in images or compose files.

## Required Before Support

- A minimal multi-service topology for EchoLabs web, wrapper/backend, NullBridge, AIBenchie, and optional model/media runtimes.
- Explicit persistent volumes for VaultEcho/E2EE data, artifacts, logs, and AIBenchie evidence, with backup and restore notes.
- Resource Manager limits for CPU, memory, disk, generated output, logs, caches, and long-running media/model jobs.
- GPU/runtime profiles for Ollama, llama.cpp, ComfyUI, image/video/3D generation, and CPU-only fallback behavior.
- Network policy for local-only services, public API routes, CORS, HTTPS, websocket/SSE streaming, and Android/Companion remote access.
- Passkey/OIDC setup guidance for containerized callback URLs and Android Digital Asset Links.
- AIBenchie Docker gate. The current `--docker-support` gate only enforces the guarded "not supported yet" boundary; the future supported-mode gate must build the stack, run health/features, chat stream, notification, E2EE, release evidence, and no-secret checks.
- Release attestation for container images, including image digest, SBOM, signature evidence, and provenance.

## Supported-Mode Proof Contract

The tracked template at `configs/aibenchie_docker_support.example.json` documents the private proof shape. It is intentionally marked as a template and does not make Docker supported.

When a private runner has a real container stack, validate ignored runtime evidence with:

```powershell
python aibenchie_local.py --docker-support-proof .suite/local/aibenchie/docker-support.json --json
```

The proof verifier requires supported status, image digests, health checks, resource limits, persistent volumes, runtime secret paths, network policy, suite release gate evidence, Docker supported-mode gate evidence, and secret-scan evidence. It rejects template proof files and secret-like fields.

## Non-Goals For v1

- Containerizing Android builds as the default release path.
- Bundling local LLM weights, Comfy models, private datasets, or user artifacts into images.
- Shipping a one-command public compose file that silently enables privileged host mounts.
- Replacing platform-native dev and release gates before Docker has equivalent AIBenchie coverage.

## Future Acceptance

Docker support can move from coming soon to supported only when:

- `docker compose up` or an equivalent documented command starts the supported local stack from a clean checkout.
- The container stack passes the normal suite release gate plus the Docker-specific AIBenchie gate in supported mode.
- Secrets are supplied only through documented runtime secret paths.
- Persistent data survives container recreation.
- The docs clearly separate local development, private deployment, and public release-image use.
