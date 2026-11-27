"""Run Batch B and repeat the Kubernetes suite after a completed baseline experiment."""
import argparse
import json
import subprocess
from pathlib import Path

import yaml


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", required=True, help="directory name on the evaluation PVC")
    parser.add_argument("--reader", required=True, help="pod mounting the results and data PVCs read-only")
    args = parser.parse_args()
    if not args.experiment.replace("-", "").isalnum():
        parser.error("Use a directory name containing only letters, numbers and hyphens")
    root = Path(__file__).resolve().parents[1]
    dest = root / "eval/results" / args.experiment
    dest.mkdir(exist_ok=True)
    volume = "/results/" + args.experiment

    def kubectl(*cmd, resource=None):
        full = ["kubectl", "-n", "rahbar", *cmd]
        proc = subprocess.run(full, input=json.dumps(resource) if resource else None,
                              capture_output=True, text=True, encoding="utf-8")
        proc.check_returncode()
        return proc.stdout

    def export(remote, local):
        data = json.loads(kubectl("exec", args.reader, "--", "cat", remote))
        (dest / local).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return data

    def measure(job, name):
        job["metadata"]["name"] = name
        (dest / (name + "-manifest.json")).write_text(json.dumps(job, indent=2))
        kubectl("create", "-f", "-", resource=job)
        import time
        while True:
            status = json.loads(kubectl("get", "job/" + name, "-o", "json"))["status"]
            terminal = [c["type"] for c in status.get("conditions", [])
                        if c["status"] == "True" and c["type"] in {"Complete", "Failed"}]
            if terminal:
                break
            time.sleep(20)
        (dest / (name + "-status.json")).write_text(json.dumps(status, indent=2))
        (dest / (name + "-logs.txt")).write_text(kubectl("logs", "job/" + name, "--all-containers=true"),
                                                  encoding="utf-8")
        return terminal[0]

    def validate(suite):
        if len(suite["runs"]) != 2:
            raise ValueError("Two complete baseline and follow-up repetitions are required")
        for run in suite["runs"]:
            answers = run["end_to_end"]
            if not answers["evaluation_complete"] or len(answers["rows"]) != suite["golden_questions"]:
                raise ValueError("Incomplete end-to-end evaluation")

    before = export(volume + "/eval-results.json", "eval-results.json")
    validate(before)
    pre = export("/data/index-state.json", "before-index.json")
    batch = json.loads((root / "k8s/assignment03/batch-b.json").read_text())
    label = args.experiment + "-ingest"
    if measure(batch, label) != "Complete":
        raise RuntimeError("Batch B ingestion failed. Inspect the saved Job log.")
    post = export("/data/index-state.json", "after-index.json")
    if pre["documents"] == post["documents"]:
        raise ValueError("The ingestion Job made no change to the indexed documents")
    job = yaml.safe_load((root / "k8s/eval-job.yaml").read_text())
    container = job["spec"]["template"]["spec"]["containers"][0]
    container["args"][0] = (container["args"][0].replace("/results/part-b-baseline.json",
                                                        volume + "/eval-results-answers-run-1.json")
                            .replace("/results/eval-results.json", volume + "/after-b.json")
                            .replace(" --bootstrap-baseline", ""))
    measure(job, args.experiment + "-after")
    after = export(volume + "/after-b.json", "after-b.json")
    validate(after)
    if before["seed"] != after["seed"] or before["configuration"] != after["configuration"]:
        raise ValueError("Seed or pipeline configuration changed")
    deltas = []
    for left, right in zip(before["runs"], after["runs"]):
        if left["end_to_end"]["dataset_sha256"] != right["end_to_end"]["dataset_sha256"]:
            raise ValueError("Golden set changed")
        result = {}
        for section, a, b in [
            ("module", left["module"], right["module"]),
            ("component", left["component"]["baseline"], right["component"]["baseline"]),
            ("noise", left["component"]["noise_test"]["metrics"], right["component"]["noise_test"]["metrics"]),
            ("end_to_end", left["end_to_end"], right["end_to_end"]),
        ]:
            result[section] = {k: b[k] - v for k, v in a.items()
                               if type(v) in (float, int) and type(b.get(k)) in (float, int)}
        deltas.append(result)
    (dest / "batch-b-drift.json").write_text(json.dumps(deltas, indent=2) + "\n")


if __name__ == "__main__":
    main()
