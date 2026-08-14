import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

import knowledge_engine
from knowledge_engine import ExecutionTracer, GitHubClient, KnowledgeAgent


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
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


if __name__ == "__main__":
    unittest.main()
