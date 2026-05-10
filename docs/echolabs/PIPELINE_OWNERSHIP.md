# EchoLabs Suite Pipeline Ownership

Every route or workflow should name its owner, callers, touched modules, writes, emitted events, and access rules.

## Normal Chat

```yaml
pipeline: normal_chat
owner: CoreEcho
callers:
  - EchoLabs
  - NullXoid Android
  - Desktop
routes:
  - POST /chat/stream
  - POST /api/chats/{chat_id}/runs
touches:
  - RuntimeEcho
  - VaultEcho
writes:
  - chat_run
  - message
  - run_event
emits:
  - run.started
  - message.delta
  - run.completed
access:
  roles:
    - user
    - beta_user
    - admin
    - beta_admin
model_policy:
  normal_chat_models: one selected text-chat model
  blocked_for_text_chat:
    - VL / vision
    - embedding
    - image/video generation
    - TTS/STT/audio
  two_pass_exception: Desktop LV7 only
```

## Model And Runtime Management

```yaml
pipeline: model_runtime_management
owner: RuntimeEcho
callers:
  - EchoLabs
  - NullXoid Android
  - Desktop
routes:
  - GET /models
  - GET /api/llms/providers
  - GET /api/llms/providers/{provider}/health
  - GET /api/llms/providers/{provider}/models
  - POST /api/llms/providers/{provider}/warm
  - GET /api/llms/models
  - GET /api/llms/profiles
  - POST /api/llms/test
compatibility_routes:
  - /api/ollama/*
providers:
  - ollama
  - llamacpp
  - hosted
  - openai_compatible
  - local_echo
touches:
  - CoreEcho for auth/admin checks
writes:
  - model_profile
  - provider_health
  - warm_state
emits:
  - runtime.provider.checked
  - runtime.model.warmed
access:
  model_select:
    - user
    - beta_user
    - admin
    - beta_admin
  provider_manage:
    - admin
    - beta_admin
```

## Speech To Speech

```yaml
pipeline: speech_to_speech
owner: CoreEcho
callers:
  - EchoLabs
  - NullXoid Android
touches:
  - RuntimeEcho
  - VaultEcho
flow:
  - STT captures user speech
  - CoreEcho creates a normal NullXoid run
  - RuntimeEcho streams one selected text-chat model
  - TTS speaks final user-visible text
  - optional auto-listen resumes after TTS
writes:
  - transcript
  - chat_run
  - message
events:
  - voice.stt.started
  - voice.stt.failed
  - run.started
  - voice.tts.started
  - voice.interrupted
fallbacks:
  - STT failure leaves text composer editable
  - model failure skips TTS
  - TTS failure keeps text response visible
rules:
  - interrupt cancels STT/TTS and active stream
  - push-to-talk and hands-free are separate modes
  - TTS must not speak fenced code blocks by default
```

## StudioEcho Media

```yaml
pipeline: studio_media
owner: StudioEcho
callers:
  - EchoLabs
  - NullXoid Android
touches:
  - AddonEcho
  - RuntimeEcho
  - VaultEcho
  - Canvas
routes:
  - /api/store/*
  - /api/studio/*
writes:
  - media_job
  - artifact
  - gallery_item
emits:
  - studio.job.created
  - studio.job.updated
  - artifact.ready
3d_rules:
  - source-image-to-GLB outputs must be gallery-safe artifacts
  - material map confidence must be visible in metadata
  - fallback labels must explain missing normal/roughness/depth maps
```

## CCC And Canvas

```yaml
pipeline: ccc_canvas
owner: Command Center Codex
callers:
  - EchoLabs
touches:
  - CoreEcho
  - RuntimeEcho
  - VaultEcho
  - Canvas
writes:
  - project_command
  - artifact
  - canvas_file
emits:
  - ccc.command.started
  - ccc.command.completed
  - canvas.preview.updated
rules:
  - CCC owns coding workflows
  - Canvas is the display/preview panel inside CCC until it needs standalone use
```

## BridgeEcho

```yaml
pipeline: bridgeecho
owner: BridgeEcho
callers:
  human_admin:
    - EchoLabs admin console
  service:
    - registered service accounts
touches:
  - CoreEcho
  - service registry
  - route policy
  - grant store
routes:
  - /api/bridge/*
  - /api/nullbridge/*
writes:
  - route_grant
  - approval
  - audit_event
emits:
  - bridge.route.approved
  - bridge.route.denied
  - bridge.audit.created
access:
  console_roles:
    - admin
    - beta_admin
  blocked_console_roles:
    - user
    - beta_user
    - guest
  service_requirements:
    - service identity
    - registry membership
    - signed envelope
    - route policy approval
rules:
  - BridgeEcho is not normal chat
  - service routing must not depend on human user roles
```

## Release Readiness

```yaml
pipeline: release_readiness
owner: AIBenchie
surface: EchoLabs readiness dashboard
touches:
  - CoreEcho
  - RuntimeEcho
  - VaultEcho
  - StudioEcho
  - BridgeEcho
  - Android
  - Desktop
gates:
  - auth
  - E2EE
  - chat stream
  - model policy
  - media
  - CCC
  - Canvas
  - Android
  - BridgeEcho
  - AIBenchie hosted/security/privacy
rule: AIBenchie stays external, but EchoLabs may surface latest verdicts.
```
