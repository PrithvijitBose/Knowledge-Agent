from typing import Dict, Any, List, Optional, Tuple
import github_auth

class PRContext:
    """
    PR (Pull Request) Context Expansion (PR Context V1)
    Constructs the minimal, high-signal evidence set around a PR that 
    intersects with the target issue, using patterns and heuristics.
    """

    @staticmethod
    def get_issue_context(access_token: str, owner: str, repo: str, issue_number: int) -> Optional[Dict[str, Any]]:
        """
        Fetches the context for a GitHub issue using the GitHub API.
        """
        try:
            issue = github_auth.fetch_issues(access_token, owner, repo, issue_number)
            if not issue:
                return None
            comments = github_auth.fetch_issue_comments(access_token, owner, repo, issue_number)
            return {'issue': issue, 'comments': comments or []}
        except Exception as e:
            print(f"Error fetching issue context: {str(e)}")
            return None

    @staticmethod
    def get_pr_context(access_token: str, owner: str, repo: str, pr_number: int) -> Optional[Dict[str, Any]]:
        """
        Fetches the context for a GitHub PR using the GitHub API.
        """
        try:
            pr = github_auth.fetch_pull_requests(access_token, owner, repo, pr_number)
            if not pr:
                return None

            pr_comments = github_auth.fetch_pr_comments(access_token, owner, repo, pr_number)
            return {'pr': pr, 'pr_comments': pr_comments or []}
        except Exception as e:
            print(f"Error fetching PR context: {str(e)}")
            return None

    @staticmethod
    def find_pr_references(issue_context: Dict[str, Any]) -> List[int]:
        """
        Extracts referenced PR numbers from issue title, body, and comments.
        """
        if not issue_context or 'issue' not in issue_context:
            return []

        issue = issue_context['issue']
        issue_title = issue.get('title', '') if isinstance(issue, dict) else ''
        issue_body = issue.get('body', '') if isinstance(issue, dict) else (str(issue) if isinstance(issue, str) else '')
        issue_comments = issue_context.get('comments', [])

        combined_text = f"{issue_title}\n{issue_body}\n" + "\n".join([
            comment.get('body', '') for comment in issue_comments if isinstance(comment, dict)
        ])

        referenced_pr_numbers = github_auth.extract_referenced_prs(combined_text)
        return referenced_pr_numbers

    @staticmethod
    def get_final_context(
        access_token: str,
        owner: str,
        repo: str,
        issue_number: int,
        target_pr_number: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Assembles the complete final context by combining:
        - Target Issue context (metadata + comments)
        - All referenced PR numbers detected in the issue thread
        - Complete PR context (PR metadata + review comments) for each referenced PR
        """
        # 1. Fetch Issue Context
        issue_ctx = PRContext.get_issue_context(access_token, owner, repo, issue_number)
        if not issue_ctx:
            return {"error": f"Could not fetch issue #{issue_number}", "issue_number": issue_number}

        # 2. Find all referenced PR numbers from issue description and comments
        referenced_pr_numbers = PRContext.find_pr_references(issue_ctx)

        # Merge with target_pr_number if provided
        pr_numbers_to_fetch = set(referenced_pr_numbers)
        if target_pr_number:
            pr_numbers_to_fetch.add(target_pr_number)

        # 3. Fetch PR context for each referenced PR
        prs_context = []
        for pr_num in sorted(list(pr_numbers_to_fetch)):
            pr_ctx = PRContext.get_pr_context(access_token, owner, repo, pr_num)
            if pr_ctx:
                prs_context.append(pr_ctx)

        # 4. Formulate unified Final Context
        final_context = {
            "owner": owner,
            "repo": repo,
            "issue_number": issue_number,
            "issue_context": issue_ctx,
            "referenced_pr_numbers": referenced_pr_numbers,
            "prs_context": prs_context,
            "total_prs_fetched": len(prs_context)
        }

        return final_context


if __name__ == "__main__":
    print("PRContext module loaded successfully.")