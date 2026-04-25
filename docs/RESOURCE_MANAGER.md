# Resource Manager

AIBenchie and the wider NullXoid suite must treat CPU, GPU, memory, storage, network, battery, and long-running jobs as governed resources.

The Resource Manager is a control layer, not another heavy runtime. Any expensive action must request a bounded lease before it starts.

```text
frontend -> platform backend -> NullBridge -> Resource Manager -> approved work
```

## Rules

- Default deny when no platform profile exists.
- Heavy work requires a resource lease.
- No unlimited CPU, memory, network, duration, or parallel jobs.
- Mobile profiles use strict memory, duration, and battery-aware limits.
- LV7 orchestration is queued and leased to prevent runaway tool loops.
- AIBenchie benchmark mode is explicit and bounded.
- Denied work degrades gracefully by queueing, reducing concurrency, or routing remote only when policy allows.

## Lease Shape

```json
{
  "capability": "model.inference",
  "profile": "windows",
  "max_memory_mb": 4096,
  "max_cpu_percent": 60,
  "max_duration_seconds": 300,
  "priority": "interactive",
  "trace_id": "trc_example"
}
```

## Platform Intent

```text
Website:
  no heavy local jobs

Website Wrapper:
  richest local profile, but capped

Windows:
  local model/tool work, capped

Android / iOS:
  strict mobile limits, remote or queued fallback

LV7:
  orchestration queue, no unlimited loops

AIBenchie:
  benchmark mode only with explicit budget
```

The canonical policy lives in:

```text
.suite/policies/resource-policy.json
```
