import unittest
from unittest.mock import patch, MagicMock
import httpx

import knowledge_engine
from knowledge_engine import GitHubClient, ContextRetriever, ContextExplainer, IntentCategory


class TestPRDiffAndReviewComments(unittest.TestCase):

    @patch.object(httpx.Client, "get")
    def test_fetch_pr_diff_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "diff --git a/main.py b/main.py\n--- a/main.py\n+++ b/main.py\n@@ -1 +1 @@\n-old\n+new"
        mock_get.return_value = mock_resp

        diff = GitHubClient.fetch_pr_diff("mock_token", "owner", "repo", 15)
        self.assertIsNotNone(diff)
        self.assertIn("diff --git", diff)
        mock_get.assert_called_once()
        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs["headers"]["Accept"], "application/vnd.github.v3.diff")

    @patch.object(httpx.Client, "get")
    def test_fetch_pr_review_comments_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {"path": "auth.py", "line": 42, "user": {"login": "reviewer1"}, "body": "Why use MD5?"}
        ]
        mock_get.return_value = mock_resp

        comments = GitHubClient.fetch_pr_review_comments("mock_token", "owner", "repo", 15)
        self.assertEqual(len(comments), 1)
        self.assertEqual(comments[0]["path"], "auth.py")
        self.assertEqual(comments[0]["body"], "Why use MD5?")

    @patch.object(GitHubClient, "fetch_pull_request", return_value={"number": 15, "title": "Refactor auth", "body": "PR description"})
    @patch.object(GitHubClient, "fetch_pr_comments", return_value=[])
    @patch.object(GitHubClient, "fetch_pr_review_comments", return_value=[{"path": "auth.py", "line": 10, "user": {"login": "alice"}, "body": "Good catch"}])
    @patch.object(GitHubClient, "fetch_pr_files", return_value=[{"filename": "auth.py", "additions": 5, "deletions": 2}])
    @patch.object(GitHubClient, "fetch_pr_diff", return_value="+++ b/auth.py\n+import hashlib")
    @patch.object(GitHubClient, "fetch_file_content", return_value="def hash(): pass")
    def test_discover_context_with_diff_and_reviews(self, mock_file, mock_diff, mock_files, mock_reviews, mock_comments, mock_pr):
        evidence = ContextRetriever.discover_context(
            token="token",
            owner="owner",
            repo="repo",
            query="Explain PR #15",
            intent_info={"intent": IntentCategory.PR_UNDERSTANDING, "pr_numbers": [15]},
            pr_number=15
        )
        self.assertIsNotNone(evidence.get("diff"))
        self.assertIn("hashlib", evidence["diff"])
        self.assertEqual(len(evidence.get("review_comments", [])), 1)

        prompt = ContextExplainer.build_user_prompt(evidence, query_author="Bob")
        self.assertIn("UNIFIED DIFF", prompt)
        self.assertIn("Code Review Comments", prompt)
        self.assertIn("auth.py:10", prompt)


if __name__ == "__main__":
    unittest.main()
