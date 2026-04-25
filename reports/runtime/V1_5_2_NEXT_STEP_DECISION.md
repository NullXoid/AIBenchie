# V1.5.2 Next Step Decision

- Accepted checkpoint remains `models/adapters/lv7_sft_smoke_v1_0_5/`.
- This milestone records the narrow runtime SFT repair training run only; it does not promote the candidate, rerun wrapper packaging, or reopen DPO.
- The candidate repair adapter cleared exact eval at `11/11` with no regressions vs accepted `v1.0.5`.
- Runtime candidate bridge still required: `True` because `v1.4.3` ingests only the accepted checkpoint identity.
- The next executable milestone is `LV7 v1.5.3 - Candidate Runtime Recheck Bridge`.

V1_5_2_CANDIDATE_READY_FOR_RUNTIME_BRIDGE
