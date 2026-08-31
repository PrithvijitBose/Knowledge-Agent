import sys
import os
import argparse
from knowledge_agent.agent import process_github_comment


def main():
    parser = argparse.ArgumentParser(description="Knowledge Engine CLI Runner")
    parser.add_argument("--owner", required=True, help="GitHub repository owner")
    parser.add_argument("--repo", required=True, help="GitHub repository name")
    parser.add_argument("--issue", type=int, required=True, help="Issue or PR number")
    parser.add_argument("--comment", required=True, help="Comment body containing @Knowledge")
    parser.add_argument("--token", help="GitHub OAuth or Personal Access Token")
    parser.add_argument("--author", default="Contributor", help="Author of the comment")
    parser.add_argument("--target-type", default=None, choices=["issue", "pull_request"], help="Webhook target type")

    args = parser.parse_args()

    token = args.token or os.getenv("GITHUB_TOKEN")
    if not token:
        print("Error: GitHub Token required via --token or GITHUB_TOKEN environment variable.")
        sys.exit(1)

    process_github_comment(
        access_token=token,
        owner=args.owner,
        repo=args.repo,
        issue_number=args.issue,
        comment_body=args.comment,
        comment_author=args.author,
        target_type=args.target_type
    )


if __name__ == "__main__":
    main()
