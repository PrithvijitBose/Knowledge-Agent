import os
import unittest
from unittest.mock import patch, MagicMock

import knowledge_engine


class TestTruncationLimits(unittest.TestCase):
    def test_configurable_truncation_limits(self):
        long_content = "A" * 5000
        with patch.dict(os.environ, {
            "KNOWLEDGE_MAX_FILE_CHARS": "100",
            "KNOWLEDGE_MAX_COMMENT_CHARS": "50",
            "KNOWLEDGE_MAX_DIFF_CHARS": "25"
        }):
            self.assertEqual(knowledge_engine.get_max_file_chars(), 100)
            self.assertEqual(knowledge_engine.get_max_comment_chars(), 50)
            self.assertEqual(knowledge_engine.get_max_diff_chars(), 25)

            with patch("knowledge_engine.GitHubClient.fetch_file_content", return_value=long_content):
                with patch("knowledge_engine.GitHubClient.fetch_latest_commit_sha", return_value="sha123"):
                    with patch("knowledge_engine.GitHubClient.fetch_repo_tree", return_value=[]):
                        evidence = knowledge_engine.ContextRetriever.retrieve_context(
                            token="tok",
                            owner="own",
                            repo="rep",
                            query="hi",
                            intent_info={"intent": knowledge_engine.IntentCategory.REPO_ONBOARDING, "keywords": []}
                        )
                        self.assertEqual(len(evidence["fetched_files"]["README.md"]), 100)

    def test_diff_and_comment_truncation_limits(self):
        long_diff = "D" * 5000
        long_file = "C" * 5000
        with patch.dict(os.environ, {
            "KNOWLEDGE_MAX_FILE_CHARS": "100",
            "KNOWLEDGE_MAX_COMMENT_CHARS": "50",
            "KNOWLEDGE_MAX_DIFF_CHARS": "25"
        }):
            with patch("knowledge_engine.GitHubClient.fetch_file_content", return_value=long_file), \
                 patch("knowledge_engine.GitHubClient.fetch_latest_commit_sha", return_value="sha123"), \
                 patch("knowledge_engine.GitHubClient.fetch_pull_request", return_value={"number": 1, "head": {"sha": "sha_pr"}}), \
                 patch("knowledge_engine.GitHubClient.fetch_pr_comments", return_value=[]), \
                 patch("knowledge_engine.GitHubClient.fetch_pr_review_comments", return_value=[]), \
                 patch("knowledge_engine.GitHubClient.fetch_pr_files", return_value=[{"filename": "app.py"}]), \
                 patch("knowledge_engine.GitHubClient.fetch_pr_diff", return_value=long_diff):
                
                evidence = knowledge_engine.ContextRetriever.retrieve_context(
                    token="tok",
                    owner="own",
                    repo="rep",
                    query="review PR #1",
                    intent_info={"intent": knowledge_engine.IntentCategory.PR_UNDERSTANDING, "pr_numbers": [1]}
                )
                self.assertEqual(len(evidence["diff"]), 25)
                self.assertEqual(len(evidence["fetched_files"]["app.py"]), 50)

    def test_default_and_invalid_truncation_limits(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(knowledge_engine.get_max_file_chars(), 3000)
            self.assertEqual(knowledge_engine.get_max_comment_chars(), 2500)
            self.assertEqual(knowledge_engine.get_max_diff_chars(), 1500)

        with patch.dict(os.environ, {
            "KNOWLEDGE_MAX_FILE_CHARS": "invalid",
            "KNOWLEDGE_MAX_COMMENT_CHARS": "invalid",
            "KNOWLEDGE_MAX_DIFF_CHARS": "invalid"
        }):
            self.assertEqual(knowledge_engine.get_max_file_chars(), 3000)
            self.assertEqual(knowledge_engine.get_max_comment_chars(), 2500)
            self.assertEqual(knowledge_engine.get_max_diff_chars(), 1500)

    def test_retrieve_context_alias_and_discover_context(self):
        self.assertIs(
            knowledge_engine.ContextRetriever.retrieve_context,
            knowledge_engine.ContextRetriever.discover_context
        )
        from knowledge_agent.retriever import ContextRetriever as DirectContextRetriever
        self.assertIs(
            DirectContextRetriever.retrieve_context,
            DirectContextRetriever.discover_context
        )


if __name__ == "__main__":
    unittest.main()
