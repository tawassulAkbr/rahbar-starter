"""Export actual cluster outputs and persistent evidence without rewriting results."""
import json
import argparse
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--out', type=Path, default=Path('eval/results') / ('assignment03-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')))
args = parser.parse_args()
OUT = ROOT / args.out
OUT.mkdir(parents=True, exist_ok=True)


def capture(name, args):
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    (OUT / f"{name}.txt").write_text(
        "$ " + subprocess.list2cmdline(args) + "\n" + result.stdout + result.stderr
        + f"\nExit code: {result.returncode}\n", encoding="utf-8")
    print(f"{name}: exit={result.returncode}", flush=True)
    return result


capture("cluster", ["kubectl", "get", "all,pvc,configmap,cronjob,job", "-n", "rahbar"])
capture("resources", ["kubectl", "top", "pods", "-n", "rahbar"])
capture("docker", ["docker", "info", "--format", "memory={{.MemTotal}} cpus={{.NCPU}}"])
for job in ("indexer-job", "assignment03-unchanged", "assignment03-unchanged-final", "assignment03-audit", "assignment03-audit-final", "assignment03-batch-b", "assignment03-seed-candidate", "eval-job", "eval-candidate-job"):
    capture(job + '-status', ['kubectl', 'get', 'job/' + job, '-n', 'rahbar', '-o', 'json'])
    capture(job, ["kubectl", "logs", "job/" + job, "-n", "rahbar", "--all-containers=true", "--pod-running-timeout=5s"])

for source, destination in [("/results/.", OUT / "volume"), ("/data/reports/.", OUT / "verification")]:
    destination.mkdir(exist_ok=True)
    capture("export-" + destination.name, ["kubectl", "cp", "-n", "rahbar",
        "assignment03-reader:" + source, destination.relative_to(ROOT).as_posix()])
trace = capture("export-traces", ["kubectl", "exec", "assignment03-reader", "-n", "rahbar",
                                  "--", "cat", "/traces/traces.jsonl"])
if trace.returncode == 0:
    (ROOT / 'traces' / (OUT.name + '.jsonl')).write_text(trace.stdout, encoding="utf-8")
state = capture("index-state", ["kubectl", "exec", "assignment03-reader", "-n", "rahbar",
                                "--", "cat", "/data/index-state.json"])
if state.returncode == 0:
    (OUT / "index-state.json").write_text(state.stdout, encoding="utf-8")
(OUT / "provenance.json").write_text(json.dumps({
    "captured_at": datetime.now(timezone.utc).isoformat(),
    "members": [{"name": "Tawassul Akbar", "roll": "24I-3100"},
                {"name": "Ayesha Anjum", "roll": "24I-3171"}],
    "human_question_writing_and_synthetic_review": "Labels exist in the dataset; actual authorship and personal review must be confirmed by both members.",
    "note": "Nonzero command outputs are retained as failures, not reported as completed checks.",
}, indent=2) + "\n", encoding="utf-8")
