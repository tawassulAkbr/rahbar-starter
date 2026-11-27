# Branch-protection evidence

Assignment 03 evidence policy: terminal images produced by the old
`scripts/generate_screenshots.py` contained hard-coded output. They are
illustrations, not screenshots of executions, and must not be submitted as
run evidence. The updated report excludes them. Capture the complete terminal
window while running the commands in the root and Kubernetes READMEs. Include
both command and output, label A–F, and append genuine images to the report.
Machine-readable logs and results remain under `eval/results/` and `traces/`.

Capture the actual GitHub **Settings → Branches → Branch protection rules** view
for `main` after configuring pull-request protection and the required CI checks.
Save the genuine screenshot as `docs/evidence/branch-protection.png`.

This repository intentionally does not contain a generated or placeholder image.

## Assignment 03 screenshot checklist

Website: run `kubectl port-forward service/ui 18081:8081 -n rahbar`, keep it
running, and open http://localhost:18081. Capture the homepage, a supported
answer with citations and expanded retrieved passages, and an unsupported
question showing abstention. Website images are supplementary.

The assignment requires actual terminal screenshots showing BOTH command and
output, with the whole terminal window visible. Use Win+PrtScn or Windows
Snipping Tool in Window mode. Take multiple numbered images for long output.

| Label | Required screenshot |
| --- | --- |
| A1 | Batch B verification report: all four checks and reasons, including quarantined failures. |
| A2 | A second unchanged ingestion Job showing `embedded_chunks: 0`. |
| B | Completed three-level evaluation summary, including two-run metric differences. |
| C1 | Actual failed release gate with its threshold-failure reasons. |
| C2 | Actual passing release gate; do not label an unfinished run as passed. |
| D1 | One complete JSON trace record. |
| D2 | `python scripts/trace.py TRACE_ID --path traces/assignment03-final.jsonl` showing reconstructed prompt/context. |
| E1 | Coverage before adding questions: 80%, failing the 85% floor. |
| E2 | Coverage after six questions: 92.5%, passing. |
| F1 | `kubectl get all,pvc,configmap,cronjob,job -n rahbar`. |
| F2 | Logs and Complete status of the ingestion Job. |
| F3 | Logs and Complete status of the evaluation Job. |
| F4 | Gate outcome changing after a ConfigMap threshold edit, with the same image. |
| F5 | `kubectl rollout status` and `kubectl rollout undo`, followed by a NEW trace showing the restored collection/model version. |

Only capture B/C/F3/F4 once their runs actually finish. A failed Job is failure
evidence, not completion evidence. The current report/checklist identifies
pending checks. Append genuine screenshots to the report; the appendix does
not count toward its eight-page body limit. Do not use the old generated
terminal illustrations.
