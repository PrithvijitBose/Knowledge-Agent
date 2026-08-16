"""
pr_context.py — Backward-compatibility Shim
Re-exports PR context engine from `knowledge_engine.py`.
"""

from typing import Dict, Any, List, Optional
import knowledge_engine


class PRContext:
    @staticmethod
    def get_issue_context(access_token: str, owner: str, repo: str, issue_number: int) -> Optional[Dict[str, Any]]:
        issue = knowledge_engine.GitHubClient.fetch_issue(access_token, owner, repo, issue_number)
        if not issue:
            return None
        comments = knowledge_engine.GitHubClient.fetch_issue_comments(access_token, owner, repo, issue_number)
        return {'issue': issue, 'comments': comments or []}

    @staticmethod
    def get_pr_context(access_token: str, owner: str, repo: str, pr_number: int) -> Optional[Dict[str, Any]]:
        pr = knowledge_engine.GitHubClient.fetch_pull_request(access_token, owner, repo, pr_number)
        if not pr:
            return None
        pr_comments = knowledge_engine.GitHubClient.fetch_pr_comments(access_token, owner, repo, pr_number)
        return {'pr': pr, 'pr_comments': pr_comments or []}

    @staticmethod
    def find_pr_references(issue_context: Dict[str, Any]) -> List[int]:
        if not issue_context or 'issue' not in issue_context:
            return []
        issue = issue_context['issue']
        combined = f"{issue.get('title', '')}\n{issue.get('body', '')}\n" + "\n".join([c.get('body', '') for c in issue_context.get('comments', [])])
        return knowledge_engine.RelationshipExtractor.extract_referenced_prs(combined)

    @staticmethod
    def get_final_context(access_token: str, owner: str, repo: str, issue_number: int, target_pr_number: Optional[int] = None) -> Dict[str, Any]:
        intent_info = {"intent": knowledge_engine.IntentCategory.ISSUE_UNDERSTANDING, "issue_numbers": [issue_number]}
        if target_pr_number:
            intent_info = {"intent": knowledge_engine.IntentCategory.PR_UNDERSTANDING, "pr_numbers": [target_pr_number]}
        return knowledge_engine.ContextRetriever.discover_context(
            token=access_token,
            owner=owner,
            repo=repo,
            query=f"Issue #{issue_number}",
            intent_info=intent_info,
            issue_number=issue_number,
            pr_number=target_pr_number
        )