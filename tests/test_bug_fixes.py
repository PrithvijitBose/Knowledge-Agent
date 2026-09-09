"""
Tests verifying bug fixes across the Knowledge codebase.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import config
import knowledge_agent
import knowledge_agent.config
import knowledge_agent.citations
import knowledge_agent.context_engine
import context_engine
import knowledge_engine
import pr_context
import webhook_server


class TestBugFixes(unittest.TestCase):

    def test_context_engine_shim_identity(self):
        """context_engine.ContextEngine must be identical to knowledge_agent.context_engine.ContextEngine."""
        self.assertIs(
            context_engine.ContextEngine,
            knowledge_agent.context_engine.ContextEngine
        )

    def test_generate_knowledge_answer_fallback_structure(self):
        """generate_knowledge_answer must produce structured_context compatible with Streamlit app.py."""
        demo_issue = {
            "number": 142,
            "title": "Modernize the authentication UI",
            "body": "Modernize the auth UI referencing PR #143 and PR #151.",
            "user": {"login": "Maintainer"}
        }
        demo_comments = [
            {"user": {"login": "Maintainer"}, "body": "Don't modify the OAuth flow."},
            {"user": {"login": "Contributor"}, "body": "@Knowledge How should I start?"}
        ]

        with patch("knowledge_agent.agent.GitHubClient.fetch_file_content", return_value=None), \
             patch("knowledge_agent.context_engine.GitHubClient.fetch_pull_request", return_value=None):
            result = knowledge_agent.generate_knowledge_answer(
                access_token=None,
                owner="demo",
                repo="demo-repo",
                issue=demo_issue,
                comments=demo_comments,
                custom_query="@Knowledge How should I start?",
            )

        self.assertIn("answer", result)
        self.assertIn("engine", result)
        self.assertIn("files_read", result)
        self.assertIn("structured_context", result)

        struct_ctx = result["structured_context"]
        self.assertIn("linked_prs", struct_ctx)
        self.assertIn("maintainer_directives", struct_ctx)
        self.assertIn("fetched_files", struct_ctx)
        self.assertIn("formatted_evidence", struct_ctx)

        # Verify linked_prs items are dicts with number, title, merged
        linked_prs = struct_ctx["linked_prs"]
        self.assertTrue(len(linked_prs) > 0)
        for pr in linked_prs:
            self.assertIsInstance(pr, dict)
            self.assertIn("number", pr)
            self.assertIn("title", pr)
            self.assertIn("merged", pr)

        # Verify maintainer_directives items are dicts with author, body
        directives = struct_ctx["maintainer_directives"]
        self.assertTrue(len(directives) > 0)
        for d in directives:
            self.assertIsInstance(d, dict)
            self.assertIn("author", d)
            self.assertIn("body", d)

    def test_generate_knowledge_answer_with_mock_provider(self):
        """generate_knowledge_answer routes through selected LLM provider."""
        demo_issue = {"number": 1, "title": "Test Issue", "body": "Details"}
        demo_comments = [{"user": {"login": "Dev"}, "body": "@Knowledge Explain this"}]

        with patch("knowledge_agent.agent.GitHubClient.fetch_file_content", return_value=None):
            result = knowledge_agent.generate_knowledge_answer(
                access_token=None,
                owner="test-owner",
                repo="test-repo",
                issue=demo_issue,
                comments=demo_comments,
                provider_name="mock"
            )

        self.assertIn("answer", result)
        self.assertEqual(result["answer"], "This is a mock LLM answer.")
        self.assertIn("Mock", result["engine"])

    def test_detect_knowledge_query_slash_command(self):
        """detect_knowledge_query must detect both @Knowledge and /knowledge."""
        comments_slash = [
            {"user": {"login": "Alice"}, "body": "/knowledge explain the architecture"}
        ]
        query, author = knowledge_agent.detect_knowledge_query({"number": 1}, comments_slash)
        self.assertEqual(query, "/knowledge explain the architecture")
        self.assertEqual(author, "Alice")

        comments_at = [
            {"user": {"login": "Bob"}, "body": "@Knowledge how do I run tests?"}
        ]
        query2, author2 = knowledge_agent.detect_knowledge_query({"number": 1}, comments_at)
        self.assertEqual(query2, "@Knowledge how do I run tests?")
        self.assertEqual(author2, "Bob")

    def test_knowledge_agent_main_forwards_target_type(self):
        """knowledge_agent.__main__ must pass target_type to process_github_comment."""
        with patch.object(sys, "argv", [
            "knowledge-agent",
            "--owner", "my-org",
            "--repo", "my-repo",
            "--issue", "42",
            "--comment", "@Knowledge explain PR",
            "--token", "ghp_test_token",
            "--target-type", "pull_request"
        ]), patch("knowledge_agent.__main__.process_github_comment", return_value=True) as mock_process:
            from knowledge_agent.__main__ import main
            main()
            mock_process.assert_called_once()
            _, kwargs = mock_process.call_args
            self.assertEqual(kwargs.get("target_type"), "pull_request")

    def test_bot_exit_code_on_failure(self):
        """bot.py CLI must exit with code 1 when process_github_comment fails."""
        with patch.object(sys, "argv", [
            "bot.py",
            "--owner", "my-org",
            "--repo", "my-repo",
            "--issue", "42",
            "--comment", "@Knowledge explain",
            "--token", "ghp_test_token"
        ]), patch("bot.process_github_comment", return_value=False), \
           self.assertRaises(SystemExit) as cm:
            # Re-run bot main block
            with open("bot.py", "r", encoding="utf-8") as f:
                code = compile(f.read(), "bot.py", "exec")
                exec(code, {"__name__": "__main__"})
        self.assertEqual(cm.exception.code, 1)

    def test_load_local_config_on_package_config(self):
        """knowledge_agent.config.load_local_config must work and match config.load_local_config."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cfg_file = Path(tmp_dir) / ".knowledge-agent.json"
            cfg_file.write_text(json.dumps({"test_key": "test_val"}), encoding="utf-8")

            res_pkg = knowledge_agent.config.load_local_config(tmp_dir)
            res_shim = config.load_local_config(tmp_dir)
            self.assertEqual(res_pkg, {"test_key": "test_val"})
            self.assertEqual(res_shim, {"test_key": "test_val"})

    def test_format_citations_table_on_package_citations(self):
        """knowledge_agent.citations.format_citations_table must format markdown table."""
        citations = [
            {"file": "app.py", "start_line": 1, "end_line": 10, "url": "https://github.com/o/r/blob/main/app.py#L1-L10"}
        ]
        table_pkg = knowledge_agent.citations.format_citations_table(citations)
        table_shim = knowledge_engine.format_citations_table(citations)
        self.assertIn("| File | Lines | Link |", table_pkg)
        self.assertIn("app.py", table_pkg)
        self.assertEqual(table_pkg, table_shim)

    def test_pr_context_none_body_resilience(self):
        """PRContext.find_pr_references must handle None in title, body, and comments without throwing."""
        issue_ctx = {
            "issue": {"title": None, "body": None},
            "comments": [{"body": None}, {"body": "Refers to PR #88"}]
        }
        prs = pr_context.PRContext.find_pr_references(issue_ctx)
        self.assertEqual(prs, [88])

    def test_webhook_server_rejects_non_dict_json(self):
        """webhook_server.github_webhook must return 400 when JSON body is not a JSON object."""
        import asyncio

        mock_request = MagicMock()
        mock_request.body = b'["not", "a", "dict"]'
        mock_request.headers = {"X-Hub-Signature-256": "sha256=dummy", "X-GitHub-Event": "issue_comment"}

        with patch("webhook_server.verify_signature", return_value=True):
            with self.assertRaises(webhook_server.HTTPException) as cm:
                asyncio.run(webhook_server.github_webhook(mock_request, MagicMock()))
            self.assertEqual(cm.exception.status_code, 400)
            self.assertIn("JSON object", cm.exception.detail)


if __name__ == "__main__":
    unittest.main()
