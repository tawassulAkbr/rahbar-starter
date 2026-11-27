"""Wait for a Kubernetes Job to finish, print its logs, and return its result."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job", help="Kubernetes Job name")
    parser.add_argument("--namespace", default="rahbar")
    parser.add_argument("--timeout", type=float, default=7200)
    parser.add_argument("--poll-interval", type=float, default=2)
    args = parser.parse_args()
    deadline = time.monotonic() + args.timeout
    condition: str | None = None
    while time.monotonic() < deadline:
        result = subprocess.run(
            ["kubectl", "get", "job", args.job, "-n", args.namespace, "-o", "json"],
            capture_output=True, text=True, check=False,
        )
        if result.returncode:
            print(result.stderr, file=sys.stderr, end="")
            return result.returncode
        job = json.loads(result.stdout)
        conditions = job.get("status", {}).get("conditions", [])
        condition = next((item["type"] for item in conditions
                          if item.get("status") == "True" and item.get("type") in {"Complete", "Failed"}), None)
        if condition:
            break
        time.sleep(max(0.1, args.poll_interval))
    if not condition:
        print(f"timed out waiting for Job/{args.job}", file=sys.stderr)
        return 124

    print(f"Job/{args.job}: {condition}")
    logs = subprocess.run(
        ["kubectl", "logs", f"job/{args.job}", "-n", args.namespace], check=False,
    )
    if logs.returncode:
        return logs.returncode
    return 0 if condition == "Complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
