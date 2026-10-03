import sys
import os
import argparse
from knowledge_agent.agent import process_github_comment


def build_bot_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Knowledge Engine CLI Runner. For MCP server mode, run: knowledge-agent mcp --help"
    )
    parser.add_argument("--owner", required=True, help="GitHub repository owner")
    parser.add_argument("--repo", required=True, help="GitHub repository name")
    parser.add_argument("--issue", type=int, required=True, help="Issue or PR number")
    parser.add_argument("--comment", required=True, help="Comment body containing @Knowledge")
    parser.add_argument("--token", help="GitHub OAuth or Personal Access Token")
    parser.add_argument("--author", default="Contributor", help="Author of the comment")
    parser.add_argument("--target-type", default=None, choices=["issue", "pull_request"], help="Webhook target type")
    return parser


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)

    # `knowledge-agent mcp ...` runs the Model Context Protocol server instead of
    # the legacy single-comment invocation.
    if argv and argv[0] == "mcp":
        from knowledge_agent.mcp_server import main as mcp_main

        return mcp_main(argv[1:])

    parser = build_bot_parser()
    args = parser.parse_args(argv)

    token = args.token or os.getenv("GITHUB_TOKEN")
    if not token:
        print("Error: GitHub Token required via --token or GITHUB_TOKEN environment variable.")
        sys.exit(1)

    from knowledge_agent.agent import is_bot_triggered

    if not is_bot_triggered(args.comment):
        # No trigger token present; this is a no-op, not a failure.
        return 0

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
        print("Error: Knowledge Agent failed to post a reply.")
        sys.exit(1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
