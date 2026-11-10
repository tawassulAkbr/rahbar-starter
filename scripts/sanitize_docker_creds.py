"""Sanitizes Docker Hub credentials from environment variables.

Removes stray whitespace, line endings, quotes, or accidental CLI command prefixes,
masks sensitive tokens in GitHub Actions logs, and writes cleaned outputs to GITHUB_OUTPUT.
"""

from __future__ import annotations

import os
import re
import sys


def sanitize() -> None:
    raw_user = os.environ.get("RAW_USER", "")
    raw_token = os.environ.get("RAW_TOKEN", "")

    user = raw_user.strip(" \t\r\n\"'")
    token = raw_token.strip(" \t\r\n\"'")

    # If the user pasted the entire 'docker login' CLI command into either field:
    cmd_match = re.search(r"-u\s+([^\s]+).*?-p\s+([^\s]+)", token) or re.search(
        r"-u\s+([^\s]+).*?-p\s+([^\s]+)", user
    )
    if cmd_match:
        user = cmd_match.group(1).strip(" \t\r\n\"'")
        token = cmd_match.group(2).strip(" \t\r\n\"'")
    else:
        pat_match = re.search(r"(dckr_pat_[A-Za-z0-9_\-]+)", token)
        if pat_match:
            token = pat_match.group(1)

    # Detect if user and token were accidentally swapped
    if user.startswith("dckr_pat_") and not token.startswith("dckr_pat_"):
        user, token = token, user

    # Docker Hub username must be a Docker ID, not an email address
    if "@" in user:
        print(
            f"::warning::DOCKERHUB_USERNAME appears to be an email ({user}). "
            "Docker Hub authentication requires your Docker ID (username), not your email. "
            "Attempting login with username prefix.",
            file=sys.stderr,
        )
        user = user.split("@")[0]

    # Docker image repository prefixes must be valid lowercase alphanumeric identifiers
    prefix = re.sub(r"[^a-zA-Z0-9_\-\.]", "", user).lower() if user else "rahbar"
    can_publish = "true" if (user and token) else "false"

    if token:
        # Mask the cleaned token so it never leaks into workflow logs
        print(f"::add-mask::{token}")

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as f:
            f.write(f"username={user}\n")
            f.write(f"token={token}\n")
            f.write(f"prefix={prefix}\n")
            f.write(f"can_publish={can_publish}\n")
    else:
        print(f"username={user}")
        print(f"prefix={prefix}")
        print(f"can_publish={can_publish}")


if __name__ == "__main__":
    sanitize()
