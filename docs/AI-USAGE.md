# AI usage

This repository was developed with assistance from AI coding tools for
repository inspection, test diagnosis, documentation drafting, and small
implementation edits. AI output was treated as a draft: maintainers checked
claims against source files, Kubernetes manifests, captured evidence, and the
assignment requirements before committing it.

| Tool | What it wrote or shaped | What we changed afterwards, and why |
| --- | --- | --- |
| Codex (GPT-5) | Inspected the repository, diagnosed test and type-check gaps, drafted ADRs/engineering notes/README text, and helped shape the Phase 5 evidence runbook. | Maintainers verified every implementation against the code and manifests, corrected unsafe assumptions, kept retrieved text delimited as untrusted evidence, and ran tests, lint, and the submission checker. |
| Antigravity | Used as a second AI-assisted review pass for documentation structure, operational-readiness wording, and the final checklist. | Maintainers accepted only recommendations that matched repository evidence; no generated claim was treated as runtime evidence, a benchmark result, or a security decision without human verification. |

## Human review and lessons learned

The maintainers selected the shipped chunking defaults, provider boundary,
readiness semantics, cache invalidation strategy, and Kubernetes resource
settings. AI suggestions were useful for finding omissions in the seven
engineering-note questions and for turning operational commands into a
repeatable runbook, but they could not substitute for a live cluster capture.
The main lesson was to separate reproducible fixture measurements from
production claims: `docs/evidence/` contains captured cluster output, while
`docs/PIPELINE.md` labels offline fixture measurements and their limitations.
