import unittest
from unittest.mock import patch, MagicMock
import knowledge_engine


class TestSlashCommandsAndTriggers(unittest.TestCase):

    @patch("builtins.print")
    @patch.object(knowledge_engine.GitHubClient, "post_issue_comment", return_value=True)
    @patch.object(knowledge_engine.KnowledgeAgent, "generate_answer", return_value={"answer": "Slash command answer", "engine": "Mistral AI"})
    def test_slash_knowledge_trigger(self, mock_gen, mock_post, mock_print):
        """Verify /knowledge slash command triggers processing."""
        success = knowledge_engine.process_github_comment(
            access_token="token",
            owner="owner",
            repo="repo",
            issue_number=1,
            comment_body="/knowledge How do I run tests?",
            comment_author="Alice"
        )
        self.assertTrue(success)
        mock_gen.assert_called_once()
        mock_post.assert_called_once()

    @patch("builtins.print")
    @patch.object(knowledge_engine.GitHubClient, "post_issue_comment", return_value=True)
    @patch.object(knowledge_engine.KnowledgeAgent, "generate_answer", return_value={"answer": "At knowledge answer", "engine": "Mistral AI"})
    def test_at_knowledge_lowercase_trigger(self, mock_gen, mock_post, mock_print):
        """Verify @knowledge in lowercase triggers processing."""
        success = knowledge_engine.process_github_comment(
            access_token="token",
            owner="owner",
            repo="repo",
            issue_number=2,
            comment_body="@knowledge explain the auth flow",
            comment_author="Bob"
        )
        self.assertTrue(success)
        mock_gen.assert_called_once()

    @patch("builtins.print")
    def test_unrelated_comment_skipped(self, mock_print):
        """Verify comments without trigger are skipped immediately."""
        success = knowledge_engine.process_github_comment(
            access_token="token",
            owner="owner",
            repo="repo",
            issue_number=3,
            comment_body="LGTM, thanks for fixing this!",
            comment_author="Charlie"
        )
        self.assertFalse(success)


if __name__ == "__main__":
    unittest.main()
