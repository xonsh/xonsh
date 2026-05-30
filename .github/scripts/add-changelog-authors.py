#!/usr/bin/env python3
"""
Post-process CHANGELOG.md after release-please to add author attribution.
Adds @author username to each commit reference in the changelog.

Desired format: * description ([#PR](URL)) ([@username](commit_url))
"""

import re
import json
import urllib.request
import os
import sys

CHANGELOG_PATH = "CHANGELOG.md"
REPO = "xonsh/xonsh"
GITHUB_API = "https://api.github.com"

# Get token from env
TOKEN = os.environ.get("GITHUB_TOKEN", "")

def github_get(url):
    """Make authenticated GitHub API request."""
    req = urllib.request.Request(url)
    if TOKEN:
        req.add_header("Authorization", f"token {TOKEN}")
    req.add_header("Accept", "application/vnd.github.v3+json")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())

def get_author_from_commit(sha):
    """Get author username from commit SHA."""
    try:
        data = github_get(f"{GITHUB_API}/repos/{REPO}/commits/{sha}")
        # Try to get author from commit
        author = data.get("author")
        if author and author.get("login"):
            return f"@{author['login']}"
        # Fallback to commit author name
        commit_author = data.get("commit", {}).get("author", {}).get("name", "")
        return commit_author
    except Exception as e:
        return None

def process_changelog():
    """Add author attribution to CHANGELOG.md entries."""
    if not os.path.exists(CHANGELOG_PATH):
        print(f"CHANGELOG.md not found, skipping")
        return

    with open(CHANGELOG_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    original = content

    # Pattern: find commit links like ([sha](https://github.com/xonsh/xonsh/commit/abcdef))
    # and append @author
    # We need to track which commits we've already looked up to avoid duplicate API calls
    seen_commits = {}
    changes = 0

    def replace_commit_link(match):
        full = match.group(0)  # e.g. "([abcdef123](https://github.com/.../commit/abcdef123))"
        inner = match.group(1)  # SHA
        url = match.group(2)

        if inner in seen_commits:
            author = seen_commits[inner]
        else:
            author = get_author_from_commit(inner)
            seen_commits[inner] = author

        if author:
            return f"({author} {full[1:]}"  # Replace leading ( with (@author 
        return full

    # Match commit references: ([0-9a-f]+](...commit/...))
    pattern = r'\(\[0-9a-f]+\]\(https://github\.com/xonsh/xonsh/commit/[0-9a-f]+\)\)'

    content = re.sub(pattern, replace_commit_link, content, flags=re.IGNORECASE)

    if content != original:
        with open(CHANGELOG_PATH, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Added author attribution to {len(seen_commits)} commits in CHANGELOG.md")
    else:
        print("No changes needed in CHANGELOG.md")

if __name__ == "__main__":
    process_changelog()
