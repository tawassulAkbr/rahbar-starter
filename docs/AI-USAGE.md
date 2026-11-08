# AI usage

This repository was developed with assistance from AI coding tools for
repository inspection, test diagnosis, documentation drafting, and small
implementation edits. AI output was treated as a draft: maintainers checked
claims against source files, Kubernetes manifests, captured evidence, and the
assignment requirements before committing it.

| Tool | What it wrote or shaped | What we changed afterwards, and why |
| --- | --- | --- |
| Codex (GPT-5) | Inspected the repository, diagnosed test and type-check gaps, drafted ADRs/engineering notes/README text, and helped shape the Phase 5 evidence runbook. | Maintainers verified every implementation against the code and manifests, corrected unsafe assumptions, kept retrieved text delimited as untrusted evidence, and ran tests, lint, and the submission checker. |
| Antigravity (Gemini 3.8 Flash) | Conducted comprehensive phase verification against the assignment, diagnosed and resolved static typing issue in `api/app/services/answer.py`, executed end-to-end linting (`ruff`), strict type checking (`mypy`), test coverage suites (`pytest`), manifest validations (`kubectl kustomize`), executed the 166-check automated submission linter, updated final documentation, and completed branch integration and artifact captures. | Maintainers verified the type-narrowing fix in `_exact_policy_answer` handling to maintain zero runtime regressions, ensured test coverage exceeded the 60% requirement (reaching 79.38%), confirmed all 166 mechanical checks pass cleanly, and validated documentation integrity. |

## Human review and lessons learned

The maintainers selected the shipped chunking defaults, provider boundary,
readiness semantics, cache invalidation strategy, and Kubernetes resource
settings. AI suggestions were useful for finding omissions in the seven
engineering-note questions and for turning operational commands into a
repeatable runbook, but they could not substitute for a live cluster capture.
The main lesson was to separate reproducible fixture measurements from
production claims: `docs/evidence/` contains captured cluster output, while
`docs/PIPELINE.md` labels offline fixture measurements and their limitations.
All code and configuration changes were validated through automated test gates
and mechanical checks prior to final merging into the `main` branch.
