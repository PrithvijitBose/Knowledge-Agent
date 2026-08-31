import unittest
from unittest.mock import patch, MagicMock
import httpx

import knowledge_engine
from knowledge_engine import GitHubClient, ContextRetriever, ContextExplainer, IntentCategory, KnowledgeAgent, process_github_comment


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

    @patch.object(GitHubClient, "fetch_pull_request", return_value={"number": 15, "title": "Refactor auth", "body": "PR description", "head": {"sha": "pr_head_commit_sha_123"}})
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
        self.assertEqual(evidence.get("commit_sha"), "pr_head_commit_sha_123")

        prompt = ContextExplainer.build_user_prompt(evidence, query_author="Bob")
        self.assertIn("UNIFIED DIFF", prompt)
        self.assertIn("Code Review Comments", prompt)
        self.assertIn("auth.py:10", prompt)

    @patch("builtins.print")
    @patch.object(GitHubClient, "fetch_pull_request", return_value={"id": 101, "number": 15, "head": {"sha": "pr_head_sha_abc"}})
    @patch.object(GitHubClient, "post_issue_comment", return_value=True)
    @patch.object(KnowledgeAgent, "generate_answer")
    def test_comment_trigger_detects_pr_target(self, mock_gen, mock_post, mock_fetch_pr, mock_print):
        mock_gen.return_value = {
            "answer": "PR explanation",
            "citations": "",
            "engine": "Mistral AI",
            "commit_sha": "pr_head_sha_abc"
        }
        # Comment does not explicitly contain "pr #" or "pull request"
        res = process_github_comment("token", "owner", "repo", 15, "@Knowledge why did CI fail?", "Alice")
        self.assertTrue(res)
        mock_fetch_pr.assert_called_once_with("token", "owner", "repo", 15)
        mock_gen.assert_called_once()
        _, kwargs = mock_gen.call_args
        self.assertEqual(kwargs["pr_number"], 15)
        self.assertIsNone(kwargs["issue_number"])

    @patch.object(GitHubClient, "fetch_latest_commit_sha", return_value="latest_main_sha")
    @patch.object(GitHubClient, "fetch_file_content", return_value=None)
    @patch.object(GitHubClient, "fetch_pr_diff", return_value="+++ b/main.py\n+print('hello')")
    @patch.object(GitHubClient, "fetch_pr_files", return_value=[{"filename": "main.py"}])
    @patch.object(GitHubClient, "fetch_pr_review_comments", return_value=[])
    @patch.object(GitHubClient, "fetch_pr_comments", return_value=[])
    @patch.object(GitHubClient, "fetch_pull_request", return_value={"number": 20, "title": "New feature", "head": {"sha": "pinned_head_sha"}})
    def test_general_query_with_pr_number_forces_pr_understanding(self, mock_pr, mock_pr_comments, mock_reviews, mock_files, mock_diff, mock_file, mock_sha):
        evidence = ContextRetriever.discover_context(
            token="token",
            owner="owner",
            repo="repo",
            query="hello world",
            intent_info={"intent": IntentCategory.GENERAL_QUERY, "keywords": []},
            pr_number=20
        )
        self.assertEqual(evidence["intent"], IntentCategory.PR_UNDERSTANDING)
        self.assertEqual(evidence["commit_sha"], "pinned_head_sha")
        self.assertIsNotNone(evidence["diff"])


if __name__ == "__main__":
    unittest.main()
