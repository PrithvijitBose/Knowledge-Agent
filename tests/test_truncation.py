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


if __name__ == "__main__":
    unittest.main()
