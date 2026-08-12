"""
bot.py — Headless CLI Runner Shim for Knowledge Bot

Delegates execution to `knowledge_engine.py` for GitHub Actions and headless execution.
"""

import sys
import os
import argparse
import knowledge_engine

def process_github_comment(
    access_token: str,
    owner: str,
    repo: str,
    issue_number: int,
    comment_body: str,
    comment_author: str = "Contributor"
) -> bool:
    return knowledge_engine.process_github_comment(
        access_token=access_token,
        owner=owner,
        repo=repo,
        issue_number=issue_number,
        comment_body=comment_body,
        comment_author=comment_author
    )

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Knowledge GitHub Bot CLI Runner")
    parser.add_argument("--owner", required=True, help="GitHub repository owner")
    parser.add_argument("--repo", required=True, help="GitHub repository name")
    parser.add_argument("--issue", type=int, required=True, help="Issue or PR number")
    parser.add_argument("--comment", required=True, help="Comment body containing @Knowledge")
    parser.add_argument("--token", help="GitHub OAuth or Personal Access Token")

    args = parser.parse_args()

    token = args.token or os.getenv("GITHUB_TOKEN") or knowledge_engine.GITHUB_CLIENT_SECRET
    if not token:
        print("Error: GitHub Token required via --token or GITHUB_TOKEN environment variable.")
        sys.exit(1)

    process_github_comment(
        access_token=token,
        owner=args.owner,
        repo=args.repo,
        issue_number=args.issue,
        comment_body=args.comment
    )
