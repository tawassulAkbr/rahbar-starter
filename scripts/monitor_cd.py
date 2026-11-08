import ssl
import urllib.request
import json
import time

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

req = urllib.request.Request(
    "https://api.github.com/repos/tawassulAkbr/rahbar-starter/actions/runs/42516510379/jobs",
    headers={"User-Agent": "A"}
)
data = json.loads(urllib.request.urlopen(req, context=ctx).read().decode())
print("=== CD #4 JOBS ===")
for j in data.get("jobs", []):
    print(f"Job '{j.get('name')}': status={j.get('status')}, conclusion={j.get('conclusion')}")
