import ssl
import urllib.request
import json

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

req = urllib.request.Request(
    "https://api.github.com/repos/tawassulAkbr/rahbar-starter/actions/runs?per_page=6",
    headers={"User-Agent": "A"}
)
data = json.loads(urllib.request.urlopen(req, context=ctx).read().decode())
print("=== RECENT WORKFLOW RUNS ===")
for r in data.get("workflow_runs", []):
    print(f"{r.get('name')} #{r.get('run_number')} (id {r.get('id')}): event={r.get('event')} | status={r.get('status')} | conclusion={r.get('conclusion')} | branch={r.get('head_branch')} | sha={r.get('head_sha')[:7]} | url={r.get('html_url')}")

req_pr = urllib.request.Request(
    "https://api.github.com/repos/tawassulAkbr/rahbar-starter/pulls/7",
    headers={"User-Agent": "A"}
)
pr_data = json.loads(urllib.request.urlopen(req_pr, context=ctx).read().decode())
print("\n=== PR #7 ===")
print("state:", pr_data.get("state"), "merged:", pr_data.get("merged"))
