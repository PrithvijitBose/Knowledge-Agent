import unittest
from unittest.mock import patch, MagicMock
import knowledge_engine


class TestSlashCommandsAndTriggers(unittest.TestCase):

    def test_is_bot_triggered_canonical_tokens(self):
        """Verify is_bot_triggered handles exact tokens and malformed strings correctly."""
        # Valid triggers
        self.assertTrue(knowledge_engine.is_bot_triggered("/knowledge explain this"))
        self.assertTrue(knowledge_engine.is_bot_triggered("@Knowledge explain this"))
        self.assertTrue(knowledge_engine.is_bot_triggered("@knowledge explain this"))
        self.assertTrue(knowledge_engine.is_bot_triggered("Hey @knowledge, could you explain?"))
        self.assertTrue(knowledge_engine.is_bot_triggered("Please run (/knowledge)"))
        self.assertTrue(knowledge_engine.is_bot_triggered("/knowledge"))
        self.assertTrue(knowledge_engine.is_bot_triggered("@Knowledge"))

        # Invalid / malformed triggers
        self.assertFalse(knowledge_engine.is_bot_triggered("user@knowledge.com"))
        self.assertFalse(knowledge_engine.is_bot_triggered("someone@knowledge"))
        self.assertFalse(knowledge_engine.is_bot_triggered("https://github.com/org/knowledge-repo"))
        self.assertFalse(knowledge_engine.is_bot_triggered("feeling knowledgeable today"))
        self.assertFalse(knowledge_engine.is_bot_triggered("path/to/knowledge/file.py"))
        self.assertFalse(knowledge_engine.is_bot_triggered("LGTM!"))
        self.assertFalse(knowledge_engine.is_bot_triggered(""))

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
        mock_post.assert_called_once()

    @patch("builtins.print")
    @patch.object(knowledge_engine.GitHubClient, "post_issue_comment")
    @patch.object(knowledge_engine.KnowledgeAgent, "generate_answer")
    def test_unrelated_comment_skipped(self, mock_gen, mock_post, mock_print):
        """Verify comments without trigger are skipped immediately without generation or comment post."""
        success = knowledge_engine.process_github_comment(
            access_token="token",
            owner="owner",
            repo="repo",
            issue_number=3,
            comment_body="LGTM, thanks for fixing this!",
            comment_author="Charlie"
        )
        self.assertFalse(success)
        mock_gen.assert_not_called()
        mock_post.assert_not_called()

    @patch("builtins.print")
    @patch.object(knowledge_engine.GitHubClient, "post_issue_comment")
    @patch.object(knowledge_engine.KnowledgeAgent, "generate_answer")
    def test_malformed_token_comment_skipped(self, mock_gen, mock_post, mock_print):
        """Verify comments with substring-only matches (e.g. emails, urls) are skipped without generation or posting."""
        malformed_comments = [
            "Contact dev@knowledge.com for questions",
            "See https://github.com/org/knowledge for docs",
            "This makes the system very knowledgeable",
            "Check my/knowledge/base path"
        ]
        for idx, comment in enumerate(malformed_comments, start=10):
            success = knowledge_engine.process_github_comment(
                access_token="token",
                owner="owner",
                repo="repo",
                issue_number=idx,
                comment_body=comment,
                comment_author="Contributor"
            )
            self.assertFalse(success)
            mock_gen.assert_not_called()
            mock_post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
