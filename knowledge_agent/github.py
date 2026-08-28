import base64
from typing import Dict, Any, List, Optional
import httpx
from knowledge_agent.config import GITHUB_API_BASE
import retry


class GitHubClient:
    """GitHub REST API wrapper for fetching issues, PRs, comments, and file contents.

    Every request routes through _get/_post, which retry transient failures
    (timeouts, 5xx, rate limits) via retry.request_with_retry instead of
    treating a single failed attempt as "this data doesn't exist."
    """

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
    def _get_paginated(
        url: str,
        token: str,
        label: str,
        *,
        per_page: int = 100,
        max_pages: int = 5,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Walks GitHub's page-based pagination for one endpoint.

        Bounded at max_pages (default 5 x 100 = 500 items) so a genuinely
        huge thread or issue list can't turn one request into an unbounded
        crawl -- this collects what's actually relevant, not the entire
        history.
        """
        items: List[Dict[str, Any]] = []
        base_params = dict(extra_params or {})
        try:
            with httpx.Client(timeout=10.0) as client:
                for page in range(1, max_pages + 1):
                    params = {**base_params, "per_page": per_page, "page": page}
                    res = client.get(url, headers=GitHubClient._get_headers(token), params=params)
                    if res.status_code != 200:
                        break
                    batch = res.json()
                    if not batch:
                        break
                    items.extend(batch)
                    if len(batch) < per_page:
                        break  # last page
        except Exception as e:
            print(f"GitHub API Error ({label}): {e}")
        return items

    @staticmethod
    def _get(
        url: str,
        token: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 10.0,
    ) -> Optional[httpx.Response]:
        req_headers = headers or GitHubClient._get_headers(token)
        with httpx.Client(timeout=timeout) as client:
            return retry.request_with_retry(
                lambda: client.get(url, headers=req_headers, params=params)
            )

    @staticmethod
    def _post(
        url: str,
        token: str,
        *,
        json_body: Dict[str, Any],
        timeout: float = 10.0,
    ) -> Optional[httpx.Response]:
        headers = GitHubClient._get_headers(token)
        with httpx.Client(timeout=timeout) as client:
            # A dropped connection here doesn't tell us whether GitHub already
            # created the comment before it dropped -- retrying blind risks
            # posting it twice. Only retry on a definite rejection response
            # (5xx / rate limit), never on a connection-level exception.
            return retry.request_with_retry(
                lambda: client.post(url, headers=headers, json=json_body),
                retry_on_connection_error=False,
            )

    @staticmethod
    def fetch_user(token: str) -> Optional[Dict[str, Any]]:
        try:
            res = GitHubClient._get(f"{GITHUB_API_BASE}/user", token)
            if res is None:
                return None
            res.raise_for_status()
            return res.json()
        except Exception as e:
            print(f"GitHub API Error (fetch_user): {e}")
            return None

    @staticmethod
    def fetch_repositories(token: str, visibility: str = "all") -> List[Dict[str, Any]]:
        params = {"sort": "updated", "direction": "desc", "per_page": 100, "visibility": visibility}
        try:
            res = GitHubClient._get(f"{GITHUB_API_BASE}/user/repos", token, params=params)
            if res is None:
                return []
            res.raise_for_status()
            return res.json()
        except Exception as e:
            print(f"GitHub API Error (fetch_repositories): {e}")
            return []

    @staticmethod
    def fetch_issue(token: str, owner: str, repo: str, issue_number: int) -> Optional[Dict[str, Any]]:
        try:
            res = GitHubClient._get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues/{issue_number}", token)
            if res is None:
                return None
            res.raise_for_status()
            return res.json()
        except Exception as e:
            print(f"GitHub API Error (fetch_issue #{issue_number}): {e}")
            return None

    @staticmethod
    def fetch_repo_issues(token: str, owner: str, repo: str) -> List[Dict[str, Any]]:
        """Fetches recent repository issues, filtering out pull requests."""
        items = GitHubClient._get_paginated(
            f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues",
            token,
            "fetch_repo_issues",
            max_pages=3,
            extra_params={"state": "all", "sort": "updated", "direction": "desc"},
        )
        return [i for i in items if "pull_request" not in i]

    @staticmethod
    def fetch_pull_request(token: str, owner: str, repo: str, pr_number: int) -> Optional[Dict[str, Any]]:
        try:
            res = GitHubClient._get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}", token)
            if res is None:
                return None
            res.raise_for_status()
            return res.json()
        except Exception as e:
            print(f"GitHub API Error (fetch_pull_request #{pr_number}): {e}")
            return None

    @staticmethod
    def fetch_pr_files(token: str, owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        try:
            res = GitHubClient._get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/files", token)
            if res is None:
                return []
            res.raise_for_status()
            return res.json()
        except Exception as e:
            print(f"GitHub API Error (fetch_pr_files #{pr_number}): {e}")
            return []

    @staticmethod
    def fetch_issue_comments(token: str, owner: str, repo: str, issue_number: int) -> List[Dict[str, Any]]:
        """Fetches discussion comments for a specific issue using pagination."""
        return GitHubClient._get_paginated(
            f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues/{issue_number}/comments",
            token,
            f"fetch_issue_comments #{issue_number}",
        )

    @staticmethod
    def fetch_pr_diff(token: str, owner: str, repo: str, pr_number: int) -> Optional[str]:
        """Fetches unified git diff for a pull request."""
        try:
            headers = GitHubClient._get_headers(token)
            headers["Accept"] = "application/vnd.github.v3.diff"
            res = GitHubClient._get(
                f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}",
                token,
                headers=headers,
                timeout=15.0,
            )
            if res is not None and res.status_code == 200:
                return res.text
        except Exception as e:
            print(f"GitHub API Error (fetch_pr_diff #{pr_number}): {e}")
        return None

    @staticmethod
    def fetch_pr_review_comments(token: str, owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        """Fetches inline review comments on code diffs."""
        return GitHubClient._get_paginated(
            f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/comments",
            token,
            f"fetch_pr_review_comments #{pr_number}",
        )

    @staticmethod
    def fetch_pr_comments(token: str, owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        """Fetches both issue discussion comments and code review comments on a PR."""
        comments = GitHubClient._get_paginated(
            f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues/{pr_number}/comments",
            token,
            f"fetch_pr_comments(issue) #{pr_number}",
        )
        comments += GitHubClient._get_paginated(
            f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/comments",
            token,
            f"fetch_pr_comments(review) #{pr_number}",
        )
        return comments

    @staticmethod
    def fetch_file_content(
        token: str, owner: str, repo: str, file_path: str, ref: Optional[str] = None
    ) -> Optional[str]:
        params = {"ref": ref} if ref else None
        try:
            res = GitHubClient._get(
                f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{file_path}",
                token,
                params=params,
            )
            if res is None:
                return None
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
            res = GitHubClient._get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}", token)
            if res is not None and res.status_code == 200:
                return res.json().get("default_branch", "main")
        except Exception as e:
            print(f"GitHub API Error (fetch_repo_default_branch): {e}")
        return "main"

    @staticmethod
    def fetch_repo_tree(token: str, owner: str, repo: str, branch: Optional[str] = None) -> List[str]:
        target_branch = branch or GitHubClient.fetch_repo_default_branch(token, owner, repo)
        try:
            res = GitHubClient._get(
                f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/trees/{target_branch}",
                token,
                params={"recursive": 1},
            )
            if (res is None or res.status_code != 200) and target_branch != "main":
                res = GitHubClient._get(
                    f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/trees/main",
                    token,
                    params={"recursive": 1},
                )
            if (res is None or res.status_code != 200) and target_branch != "master":
                res = GitHubClient._get(
                    f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/trees/master",
                    token,
                    params={"recursive": 1},
                )
            if res is not None and res.status_code == 200:
                tree_data = res.json().get("tree", [])
                return [item["path"] for item in tree_data if item.get("type") == "blob"]
        except Exception as e:
            print(f"GitHub API Error (fetch_repo_tree): {e}")
        return []

    @staticmethod
    def fetch_latest_commit_sha(token: str, owner: str, repo: str, branch: Optional[str] = None) -> Optional[str]:
        """Fetches the latest commit SHA for the target or default branch."""
        target_branch = branch or GitHubClient.fetch_repo_default_branch(token, owner, repo)
        try:
            res = GitHubClient._get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/commits/{target_branch}", token)
            if (res is None or res.status_code != 200) and target_branch != "main":
                res = GitHubClient._get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/commits/main", token)
            if (res is None or res.status_code != 200) and target_branch != "master":
                res = GitHubClient._get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/commits/master", token)
            if res is not None and res.status_code == 200:
                return res.json().get("sha", "")[:40]
        except Exception as e:
            print(f"GitHub API Error (fetch_latest_commit_sha): {e}")
        return None

    @staticmethod
    def post_issue_comment(token: str, owner: str, repo: str, issue_number: int, comment_body: str) -> bool:
        try:
            res = GitHubClient._post(
                f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues/{issue_number}/comments",
                token,
                json_body={"body": comment_body},
            )
            if res is None:
                return False
            res.raise_for_status()
            return True
        except Exception as e:
            print(f"GitHub API Error (post_issue_comment #{issue_number}): {e}")
            return False
