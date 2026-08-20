import base64
from typing import Dict, Any, List, Optional
import httpx
from knowledge_agent.config import GITHUB_API_BASE


class GitHubClient:
    """GitHub REST API wrapper for fetching issues, PRs, comments, and file contents."""

    @staticmethod
    def _get_headers(token: str) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Knowledge-Engineering-Context-App",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    @staticmethod
    def fetch_user(token: str) -> Optional[Dict[str, Any]]:
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(f"{GITHUB_API_BASE}/user", headers=GitHubClient._get_headers(token))
                res.raise_for_status()
                return res.json()
        except Exception as e:
            print(f"GitHub API Error (fetch_user): {e}")
            return None

    @staticmethod
    def fetch_repositories(token: str, visibility: str = "all") -> List[Dict[str, Any]]:
        params = {"sort": "updated", "direction": "desc", "per_page": 100, "visibility": visibility}
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(f"{GITHUB_API_BASE}/user/repos", headers=GitHubClient._get_headers(token), params=params)
                res.raise_for_status()
                return res.json()
        except Exception as e:
            print(f"GitHub API Error (fetch_repositories): {e}")
            return []

    @staticmethod
    def fetch_issue(token: str, owner: str, repo: str, issue_number: int) -> Optional[Dict[str, Any]]:
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues/{issue_number}", headers=GitHubClient._get_headers(token))
                res.raise_for_status()
                return res.json()
        except Exception as e:
            print(f"GitHub API Error (fetch_issue #{issue_number}): {e}")
            return None

    @staticmethod
    def fetch_repo_issues(token: str, owner: str, repo: str) -> List[Dict[str, Any]]:
        params = {"state": "all", "sort": "updated", "direction": "desc", "per_page": 30}
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues", headers=GitHubClient._get_headers(token), params=params)
                res.raise_for_status()
                return [i for i in res.json() if "pull_request" not in i]
        except Exception as e:
            print(f"GitHub API Error (fetch_repo_issues): {e}")
            return []

    @staticmethod
    def fetch_pull_request(token: str, owner: str, repo: str, pr_number: int) -> Optional[Dict[str, Any]]:
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}", headers=GitHubClient._get_headers(token))
                res.raise_for_status()
                return res.json()
        except Exception as e:
            print(f"GitHub API Error (fetch_pull_request #{pr_number}): {e}")
            return None

    @staticmethod
    def fetch_pr_files(token: str, owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/files", headers=GitHubClient._get_headers(token))
                res.raise_for_status()
                return res.json()
        except Exception as e:
            print(f"GitHub API Error (fetch_pr_files #{pr_number}): {e}")
            return []

    @staticmethod
    def fetch_issue_comments(token: str, owner: str, repo: str, issue_number: int) -> List[Dict[str, Any]]:
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues/{issue_number}/comments", headers=GitHubClient._get_headers(token))
                res.raise_for_status()
                return res.json()
        except Exception as e:
            print(f"GitHub API Error (fetch_issue_comments #{issue_number}): {e}")
            return []

    @staticmethod
    def fetch_pr_diff(token: str, owner: str, repo: str, pr_number: int) -> Optional[str]:
        """Fetches unified git diff for a pull request."""
        try:
            headers = GitHubClient._get_headers(token)
            headers["Accept"] = "application/vnd.github.v3.diff"
            with httpx.Client(timeout=15.0) as client:
                res = client.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}", headers=headers)
                if res.status_code == 200:
                    return res.text
        except Exception as e:
            print(f"GitHub API Error (fetch_pr_diff #{pr_number}): {e}")
        return None

    @staticmethod
    def fetch_pr_review_comments(token: str, owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        """Fetches inline review comments on code diffs."""
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(
                    f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/comments",
                    headers=GitHubClient._get_headers(token)
                )
                if res.status_code == 200:
                    return res.json()
        except Exception as e:
            print(f"GitHub API Error (fetch_pr_review_comments #{pr_number}): {e}")
        return []

    @staticmethod
    def fetch_pr_comments(token: str, owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        comments = []
        try:
            with httpx.Client(timeout=10.0) as client:
                headers = GitHubClient._get_headers(token)
                res_issue = client.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues/{pr_number}/comments", headers=headers)
                if res_issue.status_code == 200:
                    comments.extend(res_issue.json())
                res_pr = client.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/comments", headers=headers)
                if res_pr.status_code == 200:
                    comments.extend(res_pr.json())
        except Exception as e:
            print(f"GitHub API Error (fetch_pr_comments #{pr_number}): {e}")
        return comments

    @staticmethod
    def fetch_file_content(token: str, owner: str, repo: str, file_path: str) -> Optional[str]:
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{file_path}", headers=GitHubClient._get_headers(token))
                res.raise_for_status()
                data = res.json()
                if "content" in data and data.get("encoding") == "base64":
                    decoded_bytes = base64.b64decode(data["content"])
                    return decoded_bytes.decode("utf-8", errors="replace")
                return None
        except Exception as e:
            print(f"GitHub API Error (fetch_file_content '{file_path}'): {e}")
            return None

    @staticmethod
    def fetch_repo_default_branch(token: str, owner: str, repo: str) -> str:
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}", headers=GitHubClient._get_headers(token))
                if res.status_code == 200:
                    return res.json().get("default_branch", "main")
        except Exception as e:
            print(f"GitHub API Error (fetch_repo_default_branch): {e}")
        return "main"

    @staticmethod
    def fetch_repo_tree(token: str, owner: str, repo: str, branch: Optional[str] = None) -> List[str]:
        target_branch = branch or GitHubClient.fetch_repo_default_branch(token, owner, repo)
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/trees/{target_branch}?recursive=1", headers=GitHubClient._get_headers(token))
                if res.status_code != 200 and target_branch != "main":
                    res = client.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/trees/main?recursive=1", headers=GitHubClient._get_headers(token))
                if res.status_code != 200 and target_branch != "master":
                    res = client.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/trees/master?recursive=1", headers=GitHubClient._get_headers(token))
                if res.status_code == 200:
                    tree_data = res.json().get("tree", [])
                    return [item["path"] for item in tree_data if item.get("type") == "blob"]
        except Exception as e:
            print(f"GitHub API Error (fetch_repo_tree): {e}")
        return []

    @staticmethod
    def fetch_latest_commit_sha(token: str, owner: str, repo: str, branch: Optional[str] = None) -> Optional[str]:
        """Fetches the latest commit SHA for the target or default branch."""
        target_branch = branch or "main"
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/commits/{target_branch}", headers=GitHubClient._get_headers(token))
                if res.status_code != 200 and target_branch != "master":
                    res = client.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/commits/master", headers=GitHubClient._get_headers(token))
                if res.status_code == 200:
                    return res.json().get("sha", "")[:40]
        except Exception as e:
            print(f"GitHub API Error (fetch_latest_commit_sha): {e}")
        return None

    @staticmethod
    def post_issue_comment(token: str, owner: str, repo: str, issue_number: int, comment_body: str) -> bool:
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(
                    f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues/{issue_number}/comments",
                    headers=GitHubClient._get_headers(token),
                    json={"body": comment_body}
                )
                res.raise_for_status()
                return True
        except Exception as e:
            print(f"GitHub API Error (post_issue_comment #{issue_number}): {e}")
            return False
