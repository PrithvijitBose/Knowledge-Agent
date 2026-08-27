"""
github_auth.py — Backward-compatibility Shim
Re-exports GitHub REST API functions from `knowledge_engine.py`.
"""

import urllib.parse
from typing import Dict, Any, List, Optional
import knowledge_engine

GITHUB_AUTH_URL = knowledge_engine.GITHUB_AUTH_URL
GITHUB_TOKEN_URL = knowledge_engine.GITHUB_TOKEN_URL
GITHUB_API_BASE = knowledge_engine.GITHUB_API_BASE


def get_authorization_url(state: str = "knowledge_auth_state", scope: str = "read:user repo") -> str:
    params = {
        "client_id": knowledge_engine.GITHUB_CLIENT_ID,
        "redirect_uri": knowledge_engine.REDIRECT_URI,
        "scope": scope,
        "state": state,
        "allow_signup": "true",
    }
    return f"{GITHUB_AUTH_URL}?{urllib.parse.urlencode(params)}"


def exchange_code_for_token(code: str) -> Optional[str]:
    payload = {
        "client_id": knowledge_engine.GITHUB_CLIENT_ID,
        "client_secret": knowledge_engine.GITHUB_CLIENT_SECRET,
        "code": code,
        "redirect_uri": knowledge_engine.REDIRECT_URI,
    }
    headers = {"Accept": "application/json"}
    try:
        import httpx
        with httpx.Client(timeout=10.0) as client:
            res = client.post(GITHUB_TOKEN_URL, data=payload, headers=headers)
            res.raise_for_status()
            return res.json().get("access_token")
    except Exception as e:
        print(f"Error exchanging code for token: {e}")
        return None


def fetch_github_user(access_token: str) -> Optional[Dict[str, Any]]:
    return knowledge_engine.GitHubClient.fetch_user(access_token)


def fetch_user_repositories(access_token: str, visibility: str = "all") -> List[Dict[str, Any]]:
    return knowledge_engine.GitHubClient.fetch_repositories(access_token, visibility)


def fetch_repo_issues(access_token: str, owner: str, repo: str) -> List[Dict[str, Any]]:
    return knowledge_engine.GitHubClient.fetch_repo_issues(access_token, owner, repo)


def fetch_issue_comments(access_token: str, owner: str, repo: str, issue_number: int) -> List[Dict[str, Any]]:
    return knowledge_engine.GitHubClient.fetch_issue_comments(access_token, owner, repo, issue_number)


def fetch_repo_file_content(access_token: str, owner: str, repo: str, file_path: str) -> Optional[str]:
    return knowledge_engine.GitHubClient.fetch_file_content(access_token, owner, repo, file_path)


def extract_referenced_files(text: str) -> List[str]:
    return knowledge_engine.RelationshipExtractor.extract_referenced_files(text)


def post_issue_comment(access_token: str, owner: str, repo: str, issue_number: int, comment_body: str) -> bool:
    return knowledge_engine.GitHubClient.post_issue_comment(access_token, owner, repo, issue_number, comment_body)


def fetch_issue(access_token: str, owner: str, repo: str, issue_number: int) -> Optional[Dict[str, Any]]:
    return knowledge_engine.GitHubClient.fetch_issue(access_token, owner, repo, issue_number)


def fetch_pull_request(access_token: str, owner: str, repo: str, pr_number: int) -> Optional[Dict[str, Any]]:
    return knowledge_engine.GitHubClient.fetch_pull_request(access_token, owner, repo, pr_number)


def fetch_pr_comments(access_token: str, owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
    return knowledge_engine.GitHubClient.fetch_pr_comments(access_token, owner, repo, pr_number)


def fetch_pull_request_files(access_token: str, owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
    return knowledge_engine.GitHubClient.fetch_pr_files(access_token, owner, repo, pr_number)


def extract_referenced_prs(text: str) -> List[int]:
    return knowledge_engine.RelationshipExtractor.extract_referenced_prs(text)


# Aliases
fetch_issues = fetch_issue
fetch_pull_requests = fetch_pull_request
fetch_pr_files = fetch_pull_request_files
