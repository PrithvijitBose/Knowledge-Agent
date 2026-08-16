import unittest
from unittest.mock import patch, MagicMock

import knowledge_engine
from knowledge_engine import GitHubClient, RelationshipExtractor, ContextRetriever, KnowledgeAgent, IntentCategory
import pr_context


class TestGitHubIntegrationBugFixes(unittest.TestCase):

    @patch.object(GitHubClient, "fetch_file_content", return_value="def main(): pass")
    @patch.object(GitHubClient, "fetch_issue", return_value={"number": 42, "title": "Test Issue", "body": "Issue text"})
    @patch.object(GitHubClient, "fetch_issue_comments", return_value=[{"body": "You must not touch auth"}])
    def test_pr_context_get_final_context_no_crash(self, mock_comments, mock_issue, mock_file):
        """Verify B1: pr_context.get_final_context no longer calls dead EngineeringContextGraph."""
        ctx = pr_context.PRContext.get_final_context("mock_token", "owner", "repo", 42)
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx["intent"], IntentCategory.ISSUE_UNDERSTANDING)
        self.assertEqual(ctx["issue"]["number"], 42)

    @patch.object(GitHubClient, "fetch_file_content", return_value="# Doc")
    @patch.object(GitHubClient, "fetch_issue", return_value={"number": 10, "title": "Add feature", "body": "Fixes #10"})
    @patch.object(GitHubClient, "fetch_issue_comments", return_value=[{"body": "You must follow KNOWLEDGE.md directives"}])
    @patch.object(KnowledgeAgent, "call_mistral_api", return_value="Answer")
    def test_structured_context_returned_for_dashboard(self, mock_llm, mock_comments, mock_issue, mock_file):
        """Verify B2: generate_answer returns structured_context with linked_prs, directives, and fetched_files."""
        res = KnowledgeAgent.generate_answer("token", "owner", "repo", "@Knowledge Help with #10", author="Alice", issue_number=10)
        self.assertIn("structured_context", res)
        struct = res["structured_context"]
        self.assertIn("directives", struct)
        self.assertIn("linked_prs", struct)
        self.assertIn("fetched_files", struct)
        self.assertEqual(len(struct["directives"]), 1)
        self.assertIn("must follow", struct["directives"][0])

    def test_extract_referenced_files_no_boilerplate_pollution(self):
        """Verify B7: extract_referenced_files only extracts actual referenced filenames without injecting 6 defaults."""
        files = RelationshipExtractor.extract_referenced_files("Check out src/pipeline.py for details")
        self.assertEqual(files, ["src/pipeline.py"])
        self.assertNotIn("KNOWLEDGE.md", files)
        self.assertNotIn("requirements.txt", files)
        self.assertNotIn("config.py", files)

    @patch.object(GitHubClient, "fetch_file_content", return_value=None)
    @patch.object(GitHubClient, "fetch_issue", return_value=None)
    @patch.object(GitHubClient, "fetch_issue_comments", return_value=[])
    def test_no_fallback_to_issue_one(self, mock_comments, mock_issue, mock_file):
        """Verify B4: When no issue number is present, do not fall back to fetching Issue #1."""
        evidence = ContextRetriever.discover_context("token", "owner", "repo", "What is the purpose of this project?", {"intent": IntentCategory.GENERAL_QUERY, "keywords": []})
        mock_issue.assert_not_called()
        self.assertIsNone(evidence["issue"])

    @patch.object(GitHubClient, "fetch_pull_request", return_value={"id": 999, "number": 7, "title": "PR Title"})
    @patch.object(KnowledgeAgent, "generate_answer", return_value={"answer": "PR explanation", "engine": "Mistral AI"})
    @patch.object(GitHubClient, "post_issue_comment", return_value=True)
    @patch("builtins.print")
    def test_pr_detection_from_github_api(self, mock_print, mock_post, mock_gen, mock_pr):
        """Verify B3: Detect PR directly via GitHub API even if comment text does not contain 'pr #'."""
        knowledge_engine.process_github_comment(
            access_token="mock_token",
            owner="owner",
            repo="repo",
            issue_number=7,
            comment_body="@Knowledge What are the changes introduced here?",
            comment_author="Reviewer"
        )
        mock_pr.assert_called_with("mock_token", "owner", "repo", 7)
        mock_gen.assert_called_once()
        _, kwargs = mock_gen.call_args
        self.assertEqual(kwargs.get("pr_number"), 7)
        self.assertIsNone(kwargs.get("issue_number"))


if __name__ == "__main__":
    unittest.main()
