# CI/CD

RAHBAR has two GitHub Actions workflows:

- `.github/workflows/ci.yml` runs for pull requests targeting `main`, pushes to
  `dev`, and manual dispatches. It gates Ruff/mypy, the 60% coverage test run,
  Kustomize/kubeconform validation, multi-architecture image builds, Trivy
  scans, and a Kind fixture integration job.
- `.github/workflows/cd.yml` runs only for pushes to `main` (or manual dispatch).
  Tests must pass before Buildx publishes the API, indexer, and UI images to
  Docker Hub with the immutable `${{ github.sha }}` tag. Deployment then updates
  staging and checks API/UI rollouts and the real Ingress endpoints.

## Local validation

```bash
source .venv/bin/activate
python -m pytest -q
ruff check .
mypy api/ indexer/
python -m compileall -q api indexer corpus eval scripts
python -m pip check
```

The workflow additionally requires Docker Buildx, Kustomize, kubeconform, Trivy,
and Kind. The local Kind overlay is `k8s/overlays/ci`; it mounts
`eval/fixtures`, runs the real indexer module, and uses only the deterministic
CI embedding service in `scripts/ci_embedding_stub.py`. Production manifests
are not changed for this test dependency.

## Evaluation baseline

The evaluator supports the required command:

```bash
python eval/run_eval.py --api http://localhost:8000 --fixtures
```

It enforces recall@5 regression of at most 5%, 100% abstention for abstention
questions, and at least 95% citation validity. The committed
`eval/baseline.json` records the deterministic fixture contract used by the
submission gate. A live Kind run should refresh it with
`python eval/run_eval.py --fixtures --update-baseline` when the fixture
retrieval implementation changes; the provenance note in the file makes that
refresh requirement explicit.

The full university-corpus evaluation uses `eval/golden.yaml` and writes
`eval/results.json`. `eval/baseline.json` may only be created by
`python eval/run_eval.py --api <running-api> --update-baseline` after a genuine
end-to-end run; the runner records the dataset hash, timestamp, configuration,
per-question responses, and aggregate/category metrics. Missing services or a
failed quality gate never produce a baseline.

## GitHub secrets

Configure these under **Settings → Secrets and variables → Actions**:

- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN`
- `STAGING_KUBECONFIG`
- `STAGING_INGRESS_URL`

No secret values belong in the repository or workflow files.

Development and coverage tools are pinned in `requirements-dev.txt`, separate
from the runtime requirements used by the API and indexer images.

## Branch protection evidence

Protect `main` with pull requests and require the `lint`, `test`, `manifests`,
`build`, `scan`, and `e2e-eval` checks before merging. Require reviews according
to the repository policy and dismiss stale approvals when appropriate. A genuine
GitHub settings screenshot must be captured manually at
`docs/evidence/branch-protection.png`; no placeholder image is included.
