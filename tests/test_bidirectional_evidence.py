"""Tests for the Issue<->PR evidence chain: referenced_prs/referenced_issues
used to be extracted and then dropped on the floor. These verify the linked
PR/issue is actually fetched and shows up in both the evidence dict and the
prompt sent to the LLM."""

import unittest
from unittest.mock import patch

from knowledge_engine import ContextRetriever, ContextExplainer, GitHubClient, IntentCategory


class TestIssueToPREvidenceChain(unittest.TestCase):

    @patch.object(
        GitHubClient,
        "fetch_file_content",
        side_effect=lambda token, owner, repo, path: "def login(): pass" if path == "auth.py" else None,
    )
    @patch.object(GitHubClient, "fetch_pr_files", return_value=[{"filename": "auth.py", "additions": 5, "deletions": 1}])
    @patch.object(GitHubClient, "fetch_pull_request", return_value={"number": 12, "title": "Fix auth bug", "body": "Fixes the login crash"})
    @patch.object(GitHubClient, "fetch_issue_comments", return_value=[{"body": "Should be fixed in PR #12"}])
    @patch.object(GitHubClient, "fetch_issue", return_value={"number": 43, "title": "Login crashes", "body": "See PR #12"})
    def test_referenced_pr_is_fetched_and_its_files_pulled_in(
        self, mock_issue, mock_comments, mock_pr, mock_pr_files, mock_file
    ):
        evidence = ContextRetriever.discover_context(
            "token", "owner", "repo", "@Knowledge what's issue #43 about?",
            {"intent": IntentCategory.ISSUE_UNDERSTANDING, "issue_numbers": [43], "keywords": []},
            issue_number=43,
        )
        self.assertEqual(evidence["referenced_prs"], [12])
        mock_pr.assert_called_once_with("token", "owner", "repo", 12)
        self.assertEqual(evidence["linked_pr"]["number"], 12)
        mock_pr_files.assert_called_once_with("token", "owner", "repo", 12)
        self.assertEqual(evidence["linked_pr_files"][0]["filename"], "auth.py")
        self.assertIn("auth.py", evidence["fetched_files"])

    @patch.object(GitHubClient, "fetch_pull_request", return_value=None)
    @patch.object(GitHubClient, "fetch_issue_comments", return_value=[{"body": "See PR #999"}])
    @patch.object(GitHubClient, "fetch_issue", return_value={"number": 43, "title": "T", "body": "B"})
    def test_referenced_pr_that_does_not_exist_does_not_crash(self, mock_issue, mock_comments, mock_pr):
        evidence = ContextRetriever.discover_context(
            "token", "owner", "repo", "q",
            {"intent": IntentCategory.ISSUE_UNDERSTANDING, "issue_numbers": [43], "keywords": []},
            issue_number=43,
        )
        self.assertEqual(evidence["referenced_prs"], [999])
        self.assertNotIn("linked_pr", evidence)

    @patch.object(GitHubClient, "fetch_issue_comments", return_value=[])
    @patch.object(GitHubClient, "fetch_issue", return_value={"number": 43, "title": "T", "body": "No references here"})
    def test_no_referenced_pr_means_no_extra_fetch(self, mock_issue, mock_comments):
        with patch.object(GitHubClient, "fetch_pull_request") as mock_pr:
            evidence = ContextRetriever.discover_context(
                "token", "owner", "repo", "q",
                {"intent": IntentCategory.ISSUE_UNDERSTANDING, "issue_numbers": [43], "keywords": []},
                issue_number=43,
            )
            mock_pr.assert_not_called()
        self.assertEqual(evidence["referenced_prs"], [])

    def test_linked_pr_appears_in_user_prompt(self):
        evidence = {
            "intent": IntentCategory.ISSUE_UNDERSTANDING,
            "query": "what's this about",
            "owner": "o", "repo": "r",
            "fetched_files": {},
            "issue": {"number": 43, "title": "Login crashes", "body": "See PR #12"},
            "comments": [],
            "linked_pr": {"number": 12, "title": "Fix auth bug", "body": "Fixes the login crash"},
            "linked_pr_files": [{"filename": "auth.py", "additions": 5, "deletions": 1}],
        }
        prompt = ContextExplainer.build_user_prompt(evidence, query_author="Dev")
        self.assertIn("LINKED PR #12", prompt)
        self.assertIn("Fix auth bug", prompt)
        self.assertIn("auth.py", prompt)


class TestPRToIssueEvidenceChain(unittest.TestCase):

    @patch.object(GitHubClient, "fetch_file_content", return_value=None)
    @patch.object(GitHubClient, "fetch_issue", return_value={"number": 43, "title": "Login crashes", "body": "500 on bad password"})
    @patch.object(GitHubClient, "fetch_pr_diff", return_value=None)
    @patch.object(GitHubClient, "fetch_pr_files", return_value=[])
    @patch.object(GitHubClient, "fetch_pr_review_comments", return_value=[])
    @patch.object(GitHubClient, "fetch_pr_comments", return_value=[])
    @patch.object(GitHubClient, "fetch_pull_request", return_value={"number": 12, "title": "Fix auth bug", "body": "Fixes #43"})
    def test_referenced_issue_is_fetched(
        self, mock_pr, mock_pr_comments, mock_review, mock_pr_files, mock_diff, mock_issue, mock_file
    ):
        evidence = ContextRetriever.discover_context(
            "token", "owner", "repo", "@Knowledge explain PR #12",
            {"intent": IntentCategory.PR_UNDERSTANDING, "pr_numbers": [12], "keywords": []},
            pr_number=12,
        )
        self.assertEqual(evidence["referenced_issues"], [43])
        mock_issue.assert_called_once_with("token", "owner", "repo", 43)
        self.assertEqual(evidence["linked_issue"]["number"], 43)

    def test_linked_issue_appears_in_user_prompt(self):
        evidence = {
            "intent": IntentCategory.PR_UNDERSTANDING,
            "query": "explain this pr",
            "owner": "o", "repo": "r",
            "fetched_files": {},
            "pr": {"number": 12, "title": "Fix auth bug", "body": "Fixes #43"},
            "linked_issue": {"number": 43, "title": "Login crashes", "body": "500 on bad password"},
        }
        prompt = ContextExplainer.build_user_prompt(evidence, query_author="Dev")
        self.assertIn("LINKED ISSUE #43", prompt)
        self.assertIn("Login crashes", prompt)

    @patch.object(GitHubClient, "fetch_pull_request", return_value=None)
    def test_pr_not_found_leaves_referenced_issues_empty(self, mock_pr):
        evidence = ContextRetriever.discover_context(
            "token", "owner", "repo", "q",
            {"intent": IntentCategory.PR_UNDERSTANDING, "pr_numbers": [], "keywords": []},
            pr_number=None,
        )
        self.assertEqual(evidence["referenced_issues"], [])
        self.assertNotIn("linked_issue", evidence)


class TestNoDuplicateFetchRegression(unittest.TestCase):
    """The PR_UNDERSTANDING branch used to call fetch_pr_files twice and
    assign evidence["changed_files"] twice in both branches -- merge debris.
    Confirms it's called exactly once now."""

    @patch.object(GitHubClient, "fetch_file_content", return_value=None)
    @patch.object(GitHubClient, "fetch_pr_diff", return_value=None)
    @patch.object(GitHubClient, "fetch_pr_files", return_value=[{"filename": "a.py"}])
    @patch.object(GitHubClient, "fetch_pr_review_comments", return_value=[])
    @patch.object(GitHubClient, "fetch_pr_comments", return_value=[])
    @patch.object(GitHubClient, "fetch_pull_request", return_value={"number": 12, "title": "T", "body": "B"})
    def test_fetch_pr_files_called_exactly_once(
        self, mock_pr, mock_pr_comments, mock_review, mock_pr_files, mock_diff, mock_file
    ):
        ContextRetriever.discover_context(
            "token", "owner", "repo", "q",
            {"intent": IntentCategory.PR_UNDERSTANDING, "pr_numbers": [12], "keywords": []},
            pr_number=12,
        )
        mock_pr_files.assert_called_once_with("token", "owner", "repo", 12)


if __name__ == "__main__":
    unittest.main()
