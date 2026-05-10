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

## AIBenchie Evidence Gate

The budget gate checks disk/path growth by default:

```text
python aibenchie_local.py --resource-budget --json
```

Runtime enforcement evidence is supplied separately from ignored local or deployment output. Start from:

```text
configs/echolabs_resource_manager_runtime.example.json
```

Then require the runtime proof:

```text
python aibenchie_local.py --resource-budget --resource-manager-evidence path/to/ignored-resource-runtime.json --resource-manager-require-runtime --json
```

The runtime evidence must prove:

- leases are approved and bounded by duration, memory, cleanup, and profile caps
- every lease has a unique id, known profile, capability, and trace id
- heavy work requires a lease
- missing, expired, mismatched, and over-parallel leases are denied
- cleanup is enabled and has recent success evidence
- expired leases and temporary artifacts are cleaned up
- cleanup emits an audit event
- pressure snapshots are low/normal/ready, not high/critical/blocked
- pressure snapshots include a sample time, known profile, active leases, and queued jobs
- active leases and queued jobs do not exceed profile parallelism
- no tokens, client secrets, private keys, or service credentials are present
