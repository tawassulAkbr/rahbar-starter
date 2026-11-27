"""Prepare repeatable Kubernetes evidence Jobs from the checked-in manifests."""
import copy
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "k8s" / "assignment03"
OUT.mkdir(exist_ok=True)
IMAGE = "rahbar-indexer:a03-20261126"


def save(name, resource):
    (OUT / f"{name}.json").write_text(json.dumps(resource, indent=2) + "\n", encoding="utf-8")


base = yaml.safe_load((ROOT / "k8s/base/indexer-job.yaml").read_text())
for item in base["spec"]["template"]["spec"]["initContainers"] + base["spec"]["template"]["spec"]["containers"]:
    item["image"] = IMAGE

for label, collection in [("unchanged", "rahbar"), ("seed-candidate", "rahbar-candidate")]:
    job = copy.deepcopy(base)
    job["metadata"]["name"] = f"assignment03-{label}"
    container = job["spec"]["template"]["spec"]["containers"][0]
    container["env"] = [{"name": "CHROMA_COLLECTION", "value": collection}]
    if label == "seed-candidate":
        container["env"].append({"name": "INDEX_STATE_FILE", "value": "/data/candidate-index-state.json"})
    save(label, job)

batch = copy.deepcopy(base)
batch["metadata"]["name"] = "assignment03-batch-b"
batch["spec"]["template"]["spec"]["initContainers"].append({
    "name": "stage-batch-b", "image": IMAGE, "command": ["python", "-c", "\n".join([
        "import json, shutil", "from pathlib import Path",
        "from pipeline.run import _front_matter",
        "root=Path('/data/corpus'); index=root/'raw/_index.json'",
        "entries=json.loads(index.read_text()); known={e['file'] for e in entries}",
        "for source in sorted(Path('/corpus/batch-b').iterdir()):",
        "    if source.name=='MANIFEST.md' or source.name in known: continue",
        "    shutil.copy2(source,index.parent/source.name)",
        "    meta=_front_matter(source) if source.suffix=='.md' else {}",
        "    entries.append({'file':source.name,'doc_version':meta.get('doc_version','unknown'),'superseded':False})",
        "index.write_text(json.dumps(entries))",
    ])], "volumeMounts": [{"name": "data-lake", "mountPath": "/data"}],
})
save("batch-b", batch)

scripts = {name: (ROOT / "scripts" / name).read_text(encoding="utf-8")
           for name in ("audit_lifecycle.py", "audit_batch_b.py")}
save("audit-scripts", {"apiVersion": "v1", "kind": "ConfigMap",
     "metadata": {"name": "assignment03-audit-scripts", "namespace": "rahbar"}, "data": scripts})
audit = copy.deepcopy(base)
audit["metadata"]["name"] = "assignment03-audit"
pod = audit["spec"]["template"]["spec"]
pod["initContainers"] = [{"name": "fixtures", "image": IMAGE,
    "command": ["python", "-c", "import shutil; shutil.copytree('/corpus/batch-b','/workspace/corpus/batch-b',dirs_exist_ok=True)"],
    "volumeMounts": [{"name": "work", "mountPath": "/workspace"}]}]
container = pod["containers"][0]
container["workingDir"] = "/workspace"
container["command"] = ["python", "-c", "import runpy; runpy.run_path('/scripts/audit_lifecycle.py'); runpy.run_path('/scripts/audit_batch_b.py')"]
container["volumeMounts"] = [
    {"name": "work", "mountPath": "/workspace"},
    {"name": "scripts", "mountPath": "/scripts", "readOnly": True},
    {"name": "results", "mountPath": "/workspace/eval/results"}]
pod["volumes"] = [{"name": "work", "emptyDir": {}},
    {"name": "scripts", "configMap": {"name": "assignment03-audit-scripts"}},
    {"name": "results", "persistentVolumeClaim": {"claimName": "rahbar-evaluation"}}]
save("audit", audit)

reader = {"apiVersion": "v1", "kind": "Pod", "metadata": {"name": "assignment03-reader", "namespace": "rahbar"},
          "spec": {"restartPolicy": "Never", "automountServiceAccountToken": False,
          "containers": [{"name": "reader", "image": IMAGE,
              "command": ["python", "-c", "import time; time.sleep(86400)"],
              "resources": {"requests": {"cpu": "10m", "memory": "32Mi"}, "limits": {"cpu": "100m", "memory": "128Mi"}},
              "volumeMounts": [{"name": name, "mountPath": path, "readOnly": True}
                               for name, path in [("results", "/results"), ("data", "/data"), ("traces", "/traces")]]}],
          "volumes": [{"name": name, "persistentVolumeClaim": {"claimName": claim}}
                      for name, claim in [("results", "rahbar-evaluation"), ("data", "rahbar-data-lake"), ("traces", "rahbar-traces")]]}}
save("reader", reader)
print(f"Prepared manifests in {OUT}")
