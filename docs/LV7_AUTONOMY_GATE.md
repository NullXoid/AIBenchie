# Lv-7 Autonomy Gate

AIBenchie validates Lv-7 autonomy evidence with:

```powershell
python -m aibenchie.lv7_autonomy_gate path\to\lv7-autonomy-evidence.json
```

The input must be `lv7.autonomy_evidence.v1` produced by Lv-7, for example:

```powershell
python -m lv7_autonomy.evidence --output reports\lv7-autonomy-evidence.json
```

Or run the cross-repo proof in one command from AIBenchie:

```powershell
python scripts\run_lv7_autonomy_gate.py --lv7-root C:\Users\kasom\projects\Lv-7
```

The integrated runner records local resource telemetry while evidence is generated. It samples CPU usage, memory usage, and GPU usage when `nvidia-smi` is available, then prints a peak summary.

## Credential Note For Agents

This gate is deterministic and credential-free. It uses mock/resource/presence/Forgejo fixtures and does not require live Forgejo tokens, Android credentials, NullBridge service secrets, provider tokens, or signing material.

When an agent is checking credentials, it should still run this gate even if live credentials are missing. Missing credentials should only block credentialed live-route gates, not the Lv-7 autonomy evidence gate.

Generated evidence should be written under ignored runtime paths such as:

```text
_validation/lv7-autonomy-evidence.json
_validation/lv7-autonomy-resource-telemetry.json
```

The gate requires:

- evidence schema is `lv7.autonomy_evidence.v1`
- evidence reports `ok: true` and `verdict: pass`
- required signal types are present:
  - `resource.pressure`
  - `presence.changed`
  - `forgejo.pr_status`
- every scenario has a `lv7.loop_trace.v1`
- each trace contains signal, facts, state, attention, intent, policy, and action primitives
- approval-required or medium+ risk intents are routed to `ask` and `pending_approval`
- sleep intents do not create external actions

Run local tests with:

```powershell
python training\run_test_suite.py --suite lv7_autonomy --no-record -- -q
```
