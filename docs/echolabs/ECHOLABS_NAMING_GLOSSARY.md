# EchoLabs Suite Naming Glossary

This glossary is the source of truth for product and architecture names while the repos keep their current names.

| Name | Meaning | Scope |
| --- | --- | --- |
| EchoLabs Suite | The full product family. | Web, Android, Desktop, services, validation. |
| EchoLabs | The web shell / OS-like lab interface. | Primary user-facing web app. |
| NullXoid | The assistant / agent identity. | Chat, agent actions, tool use. |
| NullXoid Chat | The default installed assistant app. | Normal one-model chat flow. |
| CoreEcho | Auth, users, workspaces, projects, chats, permissions, settings. | System authority. |
| RuntimeEcho | Model inventory, model policy, provider adapters, routing, LV7 hooks. | Model/runtime layer. |
| VaultEcho | Saved chats, artifacts, attachments, galleries, E2EE persistence. | Storage and memory layer. |
| AddonEcho | Add-on manifests, installs, dependencies, route/intent permissions. | Modular add-on layer. |
| StudioEcho | Image, video, 3D, Comfy workflows, media job queues. | Creative/media workflows. |
| Command Center Codex | Coding workspace and developer workflow surface. | Project control, code actions, repo flows. |
| Canvas | Preview, playback, artifact, and generated app display surface. | Usually embedded inside CCC. |
| BridgeEcho | Admin and service bridge. | Admin-only UI, service identity, route policy, grants, audit. |
| AIBenchie | External validation harness. | Release gates and contract/security tests, surfaced but not bundled as a user suite app. |
| LV7 | Experimental two-pass runtime mode. | Desktop-local/runtime experiment until mature. |

Rules:

- Do not rename repos yet.
- Do not break current public routes during the migration.
- Use EchoLabs/CoreEcho/RuntimeEcho/etc. in docs, UI labels, and comments before broad code/module renames.
- Normal NullXoid Chat uses one selected text model.
- LV7 is the only current two-pass path.
- BridgeEcho is not normal chat and must remain admin/service-only.
