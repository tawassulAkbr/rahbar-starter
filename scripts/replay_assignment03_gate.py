"""Replay a measured candidate under two thresholds in an isolated ConfigMap."""
import json
import subprocess
from pathlib import Path
from uuid import uuid4

import yaml


def main():
    root = Path(__file__).resolve().parents[1]
    name = "gate-replay-" + uuid4().hex[:8]
    evidence = root / "eval/results/assignment03-verification" / name
    evidence.mkdir()

    def kubectl(*args, resource=None):
        cmd = ["kubectl", "-n", "rahbar", *args]
        result = subprocess.run(cmd, text=True, capture_output=True,
                                input=json.dumps(resource) if resource else None)
        with (evidence / "terminal.txt").open("a", encoding="utf-8") as log:
            print("$", subprocess.list2cmdline(cmd), file=log)
            if resource:
                print(json.dumps(resource), file=log)
            print(result.stdout + result.stderr, file=log)
        result.check_returncode()
        return result.stdout

    policy = json.loads(kubectl("get", "configmap", "rahbar-config", "-o", "json"))["data"]
    config = {"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": name},
              "data": {k: v for k, v in policy.items() if k.startswith("GATE_")}}
    job = yaml.safe_load((root / "k8s/eval-job.yaml").read_text())
    container = job["spec"]["template"]["spec"]["containers"][0]
    container["envFrom"] = [{"configMapRef": {"name": name}}]
    container["command"] = ["python", "-c"]
    container["args"] = ["""
import hashlib, json, os, sys
from pathlib import Path
from run_eval import gate
def read(name):
    data = Path('/results', name + '-answers-run-1.json').read_bytes()
    result = json.loads(data)
    assert result['evaluation_complete']
    print(name, hashlib.sha256(data).hexdigest())
    return result
baseline = read('eval-results')
candidate = read('eval-candidate-results')
assert candidate['dataset_sha256'] == baseline['dataset_sha256']
errors = gate(candidate, baseline)
print(json.dumps(dict(threshold=os.environ['GATE_FAITHFULNESS_MIN'],
                      faithfulness=candidate['faithfulness'], failures=errors)))
sys.exit(bool(errors))
"""]
    kubectl("create", "-f", "-", resource=config)
    try:
        for label, condition in [("release", "failed"), ("experiment", "complete")]:
            if label == "experiment":
                kubectl("patch", "configmap", name, "--type=merge", "-p",
                        json.dumps({"data": {"GATE_FAITHFULNESS_MIN": "0.65"}}))
            job_name = name + "-" + label
            job["metadata"]["name"] = job_name
            kubectl("create", "-f", "-", resource=job)
            kubectl("wait", "--for=condition=" + condition, "job/" + job_name, "--timeout=180s")
            kubectl("logs", "job/" + job_name)
            kubectl("get", "pods", "-l", "job-name=" + job_name, "-o",
                    "custom-columns=IMAGE_ID:.status.containerStatuses[0].imageID")
    finally:
        kubectl("delete", "configmap", name)
    print(evidence)


if __name__ == "__main__":
    main()
