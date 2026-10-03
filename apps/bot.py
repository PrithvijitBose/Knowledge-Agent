"""
bot.py — Headless CLI Runner for Knowledge Bot

Delegates execution to `knowledge_agent` for GitHub Actions and headless execution.
"""

import sys
import os
import argparse
from pathlib import Path
from typing import Optional

try:
    REPO_ROOT = Path(__file__).resolve().parent.parent
except (NameError, TypeError):
    REPO_ROOT = Path.cwd()

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from knowledge_agent import process_github_comment


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Knowledge GitHub Bot CLI Runner")
    parser.add_argument("--owner", required=True, help="GitHub repository owner")
    parser.add_argument("--repo", required=True, help="GitHub repository name")
    parser.add_argument("--issue", type=int, required=True, help="Issue or PR number")
    parser.add_argument("--comment", required=True, help="Comment body containing @Knowledge")
    parser.add_argument("--token", help="GitHub OAuth or Personal Access Token")
    parser.add_argument("--author", default="Contributor", help="Comment author username")
    parser.add_argument("--target-type", default=None, choices=["issue", "pull_request"], help="Webhook target type")

    args = parser.parse_args()

    token = args.token or os.getenv("GITHUB_TOKEN")
    if not token:
        print("Error: GitHub Token required via --token or GITHUB_TOKEN environment variable.")
        sys.exit(1)

    succeeded = process_github_comment(
        access_token=token,
        owner=args.owner,
        repo=args.repo,
        issue_number=args.issue,
        comment_body=args.comment,
        comment_author=args.author,
        target_type=args.target_type
    )
    if not succeeded:
        print("Error: Knowledge Bot failed to post a reply.")
        sys.exit(1)
