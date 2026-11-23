# Phase 3 Member 2 checklist

Phase 3 is implemented on the existing
`feature/assignment-03-phase1-integrated` branch. No new branch was created.

## C1 - change experiment

The selected change is retrieval `TOP_K`: baseline `5`, candidate `4`.
The Phase 2 component baseline showed recall@5 of approximately `0.963` and
the noise test showed measurable degradation, so this experiment tests whether
slightly reducing retrieval context preserves quality.

Run:

```text
python eval/change_experiment.py --candidate-top-k 4 --out eval/results/change-topk4.json
```

The output compares module, component, and end-to-end results and includes the
candidate image and collection handoff.

## C2 - release gate

Thresholds are in [`eval/gate.json`](../eval/gate.json):

- recall@5 drop <= `0.05`, matching the frozen Phase 0 budget;
- faithfulness >= `0.90`;
- p95 latency <= `2.0` ms for the deterministic local reference;
- abstention correctness >= baseline and `1.0`.

Apply the gate:

```text
python eval/gate.py --experiment eval/results/change-topk4.json --config eval/gate.json --out eval/results/gate-pass.json
```

The deliberately bad candidate is `TOP_K=1`:

```text
python eval/change_experiment.py --candidate-top-k 1 --candidate-image rahbar-indexer:phase3-topk1 --out eval/results/change-topk1.json
python eval/gate.py --experiment eval/results/change-topk1.json --config eval/gate.json --out eval/results/gate-fail.json
```

Expected exit codes are `0` for the passing candidate and `1` for the bad
candidate. Both result files are committed as evidence.

## C3 - rollout handoff

[`eval/release-handoff.json`](../eval/release-handoff.json) records:

- candidate image: `rahbar-indexer:phase3-topk4`;
- collection: `rahbar`;
- pinned embedding model: `nomic-embed-text`;
- pinned dimension: `768`;
- build/load commands for Member 1.

The same candidate values are available in the base ConfigMap as
`CANDIDATE_IMAGE`, `CANDIDATE_COLLECTION`, and `CANDIDATE_TOP_K`. The gate
threshold keys are also wired to the Phase 3 values.

## Acceptance evidence

- [x] Baseline/candidate tables cover all three levels.
- [x] Passing candidate gate result is committed.
- [x] Failing candidate gate result is committed.
- [x] Thresholds are justified from Phase 0/2 measurements.
- [x] Candidate image and collection handoff is committed.

The results use the deterministic local Phase 2 reference harness. A live
Chroma/API run remains required before a production rollout.
