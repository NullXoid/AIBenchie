# Router Evaluation Boundary

AIBenchie is not an intent router.

AIBenchie is the benchmark, testbed, release gate, approval-status system, and status marker for router candidates and other suite artifacts.

## Correct Boundary

```text
intent-router candidate
  -> emits route-style output
  -> AIBenchie evaluates gates and records status
  -> approved router candidate output may be consumed by a runtime bridge
  -> Lv-7 normalizes that output into lv7.intent.v1
  -> Lv-7 applies approval, MITM, and execution policy
```

## Terms To Use

- AIBenchie router evaluation suite
- AIBenchie router-evaluation gate
- router-under-test
- intent-router candidate
- AIBenchie-approved router candidate

## Terms To Avoid

- AIBenchie router
- AIBenchie router output

Those phrases collapse the benchmark system into the runtime component being tested. If output is discussed, call it router-under-test output, router candidate output, or output captured by AIBenchie during evaluation.

## Ownership

- AIBenchie owns benchmarks, holdouts, gates, scoring, release evidence, and approval status.
- The intent-router candidate owns route inference.
- Runtime bridges translate approved router-style output into runtime contracts.
- Lv-7 owns intent normalization, approval requirements, MITM review, and execution policy.
