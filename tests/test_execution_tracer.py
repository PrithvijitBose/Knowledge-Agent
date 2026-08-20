import os
import tempfile
import unittest
import asyncio
from unittest.mock import patch, MagicMock

import knowledge_engine
from knowledge_engine import ExecutionTracer, GitHubClient, KnowledgeAgent, is_bot_triggered
import webhook_server


class TestExecutionTracer(unittest.TestCase):

    def test_generate_markdown_summary_success(self):
        tracer = ExecutionTracer("owner", "repo", 42, "alice")
        result = {
            "intent": "ARCHITECTURE_UNDERSTANDING",
            "engine": "Mistral AI (mistral-small-2506)",
            "files_read": ["src/auth.py", "config.py"]
        }
        tracer.finish(True, result)
        md = tracer.generate_markdown_summary()

        self.assertIn("## 🧠 Knowledge Agent Execution Summary", md)
        self.assertIn("owner/repo#42", md)
        self.assertIn("@alice", md)
        self.assertIn("ARCHITECTURE_UNDERSTANDING", md)
        self.assertIn("Mistral AI", md)
        self.assertIn("Success", md)
        self.assertIn("src/auth.py", md)

    def test_generate_markdown_summary_failure(self):
        tracer = ExecutionTracer("owner", "repo", 42, "alice")
        tracer.finish(False, {})
        md = tracer.generate_markdown_summary()

        self.assertIn("## 🧠 Knowledge Agent Execution Summary", md)
        self.assertIn("Failed", md)
        self.assertIn("UNKNOWN", md)

    def test_write_step_summary_file(self):
        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as tf:
            temp_path = tf.name

        try:
            with patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": temp_path}):
                tracer = ExecutionTracer("owner", "repo", 10, "bob")
                tracer.finish(True, {"intent": "GENERAL_QUERY", "files_read": ["README.md"], "engine": "OpenAI"})
                with open(temp_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.assertIn("## 🧠 Knowledge Agent Execution Summary", content)
                self.assertIn("@bob", content)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    @patch("builtins.print")
    @patch.object(GitHubClient, "post_issue_comment", return_value=True)
    @patch.object(KnowledgeAgent, "generate_answer", return_value={"answer": "Done", "engine": "Mistral AI", "intent": "REPO_ONBOARDING", "files_read": []})
    def test_process_comment_traces_run(self, mock_gen, mock_post, mock_print):
        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as tf:
            temp_path = tf.name

        try:
            with patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": temp_path}):
                success = knowledge_engine.process_github_comment("token", "owner", "repo", 1, "@Knowledge help", "charlie")
                self.assertTrue(success)
                with open(temp_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.assertIn("@charlie", content)
                self.assertIn("REPO_ONBOARDING", content)
                self.assertIn("Success", content)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    @patch("builtins.print")
    @patch.object(KnowledgeAgent, "generate_answer", side_effect=RuntimeError("Context synthesis exploded"))
    def test_process_comment_records_failure_on_exception(self, mock_gen, mock_print):
        """Verify tracer.finish is invoked in finally block when generate_answer raises."""
        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as tf:
            temp_path = tf.name

        try:
            with patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": temp_path}):
                with self.assertRaises(RuntimeError):
                    knowledge_engine.process_github_comment("token", "owner", "repo", 99, "@Knowledge please break", "dan")
                with open(temp_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.assertIn("@dan", content)
                self.assertIn("Failed", content)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_canonical_token_trigger_matcher(self):
        """Verify is_bot_triggered recognizes complete tokens and rejects substrings."""
        self.assertTrue(is_bot_triggered("@Knowledge explain this"))
        self.assertTrue(is_bot_triggered("/knowledge explain this"))
        self.assertTrue(is_bot_triggered("@knowledge"))
        self.assertTrue(is_bot_triggered("/knowledge"))

        # Rejects substring matches
        self.assertFalse(is_bot_triggered("dev@knowledge.com"))
        self.assertFalse(is_bot_triggered("https://github.com/knowledge-agent"))
        self.assertFalse(is_bot_triggered("knowledgeable"))
        self.assertFalse(is_bot_triggered("LGTM"))

    @patch("builtins.print")
    def test_webhook_accepts_slash_knowledge(self, mock_print):
        """Verify webhook listener accepts /knowledge and @knowledge commands."""
        # Use an AsyncMock or mock Request/BackgroundTasks to verify webhook dispatch
        mock_bg = MagicMock()
        mock_req = MagicMock()
        mock_req.headers = {"X-GitHub-Event": "issue_comment"}
        
        async def run_test():
            secret = "test_webhook_secret_key"
            payload = {
                "action": "created",
                "comment": {"body": "/knowledge explain how auth works", "user": {"login": "eve", "type": "User"}},
                "issue": {"number": 12},
                "repository": {"name": "repo", "owner": {"login": "owner"}},
                "sender": {"login": "eve", "type": "User"}
            }
            import json
            import hmac
            import hashlib
            payload_bytes = json.dumps(payload).encode("utf-8")
            sig = "sha256=" + hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
            mock_req.headers = {"X-GitHub-Event": "issue_comment", "X-Hub-Signature-256": sig}
            async def mock_body():
                return payload_bytes
            mock_req.body = mock_body
            mock_req.json = MagicMock(return_value=payload)
            with patch.dict(os.environ, {"GITHUB_TOKEN": "mock_token", "GITHUB_WEBHOOK_SECRET": secret}):
                resp = await webhook_server.github_webhook(mock_req, mock_bg)
                self.assertEqual(resp.get("status"), "processing")
                mock_bg.add_task.assert_called_once()

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
