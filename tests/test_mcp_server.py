"""Hermetic tests for the Knowledge MCP server (issue #63)."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from knowledge_agent.github import GitHubClient
from knowledge_agent.mcp_server import (
    KnowledgeContextTools,
    _collect_local_files,
    _looks_like_slug,
    _resolve_repository,
    _score_file,
    _tokenize,
    build_mcp_parser,
    is_mcp_available,
)


def _write(root: Path, relative: str, content: str) -> None:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


class TestArchitectureContextTool(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        _write(
            self.root,
            "app/auth.py",
            "import os\n\n\n"
            "class AuthService:\n"
            "    def login(self, user, password):\n"
            "        return os.getenv('AUTH_TOKEN')\n",
        )
        _write(
            self.root,
            "app/api.py",
            "from flask import Flask\n\napp = Flask(__name__)\n\n\n"
            "@app.get('/api/v1/users')\n"
            "def list_users():\n"
            "    return []\n",
        )
        _write(self.root, "README.md", "# Demo\n\nRun `login_account()` to sign in.\n")
        _write(self.root, "KNOWLEDGE.md", "# Rules\n\n- Never log tokens.\n")
        _write(self.root, "node_modules/pkg/index.js", "function unusedThing() {}\n")
        self.addCleanup(self._tmp.cleanup)

    def test_returns_grounded_symbols_and_evidence(self):
        result = KnowledgeContextTools().get_architecture_context("auth login", str(self.root))

        self.assertTrue(result["ok"])
        self.assertEqual(result["tool"], "knowledge_get_architecture_context")
        self.assertEqual(result["source"], "local")

        files = {item["file"] for item in result["mental_model"]["subsystems"]}
        self.assertIn("app/auth.py", files)

        class_names = {c["name"] for c in result["mental_model"]["classes"]}
        self.assertIn("AuthService", class_names)

        fn_names = {f["name"] for f in result["mental_model"]["functions"]}
        self.assertIn("login", fn_names)

        self.assertIn("AUTH_TOKEN", result["mental_model"]["environment_variables"])
        self.assertTrue(result["evidence"])
        for item in result["evidence"]:
            self.assertIn("file", item)
            self.assertIn("start_line", item)

    def test_extracts_http_routes(self):
        result = KnowledgeContextTools().get_architecture_context("api routes", str(self.root))
        routes = result["mental_model"]["http_routes"]
        self.assertTrue(any(r["path"] == "/api/v1/users" and r["method"] == "GET" for r in routes))

    def test_includes_repository_rules(self):
        result = KnowledgeContextTools().get_architecture_context("auth", str(self.root))
        self.assertIn("Never log tokens.", result["repository_rules"])

    def test_skips_vendor_directories(self):
        result = KnowledgeContextTools().get_architecture_context("unusedThing", str(self.root))
        self.assertNotIn("unusedThing", {f["name"] for f in result["mental_model"]["functions"]})

    def test_empty_query_fails_gracefully(self):
        result = KnowledgeContextTools().get_architecture_context("   ", str(self.root))
        self.assertFalse(result["ok"])
        self.assertIn("query", result["reason"])

    def test_unreadable_repo_path_reports_unknown(self):
        result = KnowledgeContextTools().get_architecture_context("auth", "does/not/exist")
        self.assertFalse(result["ok"])
        self.assertTrue(result["unknowns"])


class TestDocDriftTool(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        _write(self.root, "docs/api.md", "Use `verify_token(token)` to authenticate.\n")
        _write(self.root, "docs/legacy.md", "Call `retired_endpoint()` to refresh.\n")
        _write(self.root, "src/auth.py", "def verify_token(token):\n    return True\n")
        _write(self.root, "src/ghost.py", "def other():\n    return 1\n")
        self.addCleanup(self._tmp.cleanup)

    def test_reports_missing_implementation(self):
        result = KnowledgeContextTools().verify_doc_drift(
            str(self.root / "docs" / "api.md"),
            str(self.root / "src"),
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["tool"], "knowledge_verify_doc_drift")
        self.assertEqual(result["total_discrepancies"], 0)
        self.assertEqual(result["evidence"], [])

    def test_reports_unimplemented_documented_function(self):
        result = KnowledgeContextTools().verify_doc_drift(
            str(self.root / "docs" / "legacy.md"),
            str(self.root / "src"),
        )

        self.assertEqual(result["total_discrepancies"], 1)
        discrepancy = result["discrepancies"][0]
        self.assertEqual(discrepancy["type"], "MISSING_IMPLEMENTATION")
        self.assertEqual(discrepancy["claim"], "retired_endpoint()")
        self.assertEqual(discrepancy["source_doc"], "legacy.md")
        self.assertEqual(result["evidence"][0]["file"], "legacy.md")

    def test_accepts_doc_directory(self):
        result = KnowledgeContextTools().verify_doc_drift(
            str(self.root / "docs"),
            str(self.root / "src"),
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["docs_analyzed"], ["api.md", "legacy.md"])
        self.assertEqual(result["total_discrepancies"], 1)

    def test_clean_docs_have_no_discrepancies(self):
        result = KnowledgeContextTools().verify_doc_drift(
            str(self.root / "docs" / "api.md"),
            str(self.root / "src"),
        )
        self.assertEqual(result["total_discrepancies"], 0)
        self.assertTrue(result["unknowns"])
        self.assertIn("No drift detected", result["unknowns"][0])

    def test_missing_paths_fail_gracefully(self):
        for doc_path, code_dir in [
            (str(self.root / "nope.md"), str(self.root / "src")),
            (str(self.root / "docs" / "api.md"), str(self.root / "nope")),
            ("", str(self.root / "src")),
        ]:
            with self.subTest(doc_path=doc_path, code_dir=code_dir):
                result = KnowledgeContextTools().verify_doc_drift(doc_path, code_dir)
                self.assertFalse(result["ok"])
                self.assertTrue(result["reason"])


class TestIssueTraceTool(unittest.TestCase):
    def test_requires_token(self):
        tools = KnowledgeContextTools(token="", owner="acme", repo="core")
        with patch.dict(os.environ, {}, clear=True):
            result = tools.trace_issue_pr(42)
        self.assertFalse(result["ok"])
        self.assertIn("token", result["reason"].lower())

    def test_requires_repository_target(self):
        tools = KnowledgeContextTools(token="ghp_x", owner="", repo="")
        with patch.dict(os.environ, {}, clear=True):
            result = tools.trace_issue_pr(42)
        self.assertFalse(result["ok"])
        self.assertIn("owner", result["reason"].lower())

    def test_rejects_non_positive_issue_numbers(self):
        tools = KnowledgeContextTools(token="ghp_x", owner="acme", repo="core")
        for value in (0, -3, "not-a-number"):
            with self.subTest(value=value):
                result = tools.trace_issue_pr(value)
                self.assertFalse(result["ok"])

    def test_reports_missing_issue(self):
        tools = KnowledgeContextTools(token="ghp_x", owner="acme", repo="core")
        with patch.object(GitHubClient, "fetch_issue", return_value=None):
            result = tools.trace_issue_pr(7)
        self.assertFalse(result["ok"])
        self.assertIn("not found", result["reason"])

    @patch.object(GitHubClient, "fetch_issue_comments")
    @patch.object(GitHubClient, "fetch_issue")
    def test_returns_bidirectional_lineage(self, mock_issue, mock_comments):
        tools = KnowledgeContextTools(token="ghp_x", owner="acme", repo="core")

        mock_issue.return_value = {
            "number": 42,
            "title": "Fix the auth retry loop",
            "body": "Mentions knowledge_agent/retriever.py and #51.",
            "user": {"login": "maintainer"},
        }
        mock_comments.return_value = [
            {"user": {"login": "maintainer"}, "body": "maintainer: do not change the retry budget."},
            {"user": {"login": "dev"}, "body": "I tried PR #57 already."},
        ]

        simulated = {
            57: {
                "number": 57,
                "title": "Attempt to fix retry loop",
                "state": "closed",
                "merged": False,
                "body": "Closes #42",
                "changed_files": ["knowledge_agent/retry.py"],
                "html_url": "https://github.com/acme/core/pull/57",
            }
        }

        from knowledge_agent.context_engine import ContextEngine

        with patch.object(GitHubClient, "fetch_file_content", return_value=None):
            context = ContextEngine.build_structured_context(
                access_token="ghp_x",
                owner="acme",
                repo="core",
                issue=mock_issue.return_value,
                comments=mock_comments.return_value,
                simulated_prs=simulated,
            )

        self.assertEqual(context["issue_number"], 42)
        self.assertEqual(context["linked_prs"][0]["number"], 57)
        self.assertTrue(context["maintainer_directives"])
        self.assertTrue(context["contributor_discussions"])

    @patch.object(GitHubClient, "fetch_issue_comments", return_value=[])
    @patch.object(GitHubClient, "fetch_issue")
    def test_trace_issue_pr_end_to_end(self, mock_issue, _mock_comments):
        tools = KnowledgeContextTools(token="ghp_x", owner="acme", repo="core")
        mock_issue.return_value = {
            "number": 42,
            "title": "Bug in webhook server",
            "body": "Look at apps/webhook_server.py",
            "user": {"login": "maintainer"},
        }

        with patch(
            "knowledge_agent.mcp_server.ContextEngine.build_structured_context"
        ) as mock_context:
            mock_context.return_value = {
                "issue_title": "Bug in webhook server",
                "issue_author": "maintainer",
                "issue_body": "Look at apps/webhook_server.py",
                "maintainer_directives": [{"author": "maintainer", "body": "must verify HMAC"}],
                "contributor_discussions": [],
                "linked_prs": [
                    {
                        "number": 57,
                        "state": "merged",
                        "merged": True,
                        "body": "Fixes #42",
                        "changed_files": ["apps/webhook_server.py"],
                        "html_url": "https://github.com/acme/core/pull/57",
                    }
                ],
                "fetched_files": {"apps/webhook_server.py": "def read_root(): ..."},
                "formatted_evidence": "EVIDENCE",
            }
            result = tools.trace_issue_pr(42)

        self.assertTrue(result["ok"])
        self.assertEqual(result["previous_attempts"][0]["number"], 57)
        self.assertEqual(result["touched_files"], ["apps/webhook_server.py"])
        self.assertEqual(result["reverse_references"][0]["references_issues"], [42])
        self.assertEqual(result["unknowns"], [])

    def test_github_repository_env_slug_resolves_owner_repo(self):
        tools = KnowledgeContextTools(token="ghp_x", owner="", repo="")
        with patch.dict(os.environ, {"GITHUB_REPOSITORY": "acme/core"}, clear=True):
            self.assertEqual(tools._github_target(None, None), ("acme", "core"))


class TestHelperFunctions(unittest.TestCase):
    def test_tokenize_drops_stopwords_and_short_tokens(self):
        tokens = _tokenize("How does the auth layer work in this repository?")
        self.assertIn("auth", tokens)
        self.assertIn("layer", tokens)
        self.assertNotIn("the", tokens)
        self.assertNotIn("how", tokens)

    def test_looks_like_slug(self):
        self.assertTrue(_looks_like_slug("acme/core"))
        self.assertFalse(_looks_like_slug("."))
        self.assertFalse(_looks_like_slug("/tmp/repo"))
        self.assertFalse(_looks_like_slug("acme/core/extra"))

    def test_score_file_prefers_path_matches(self):
        path_heavy = _score_file("app/auth_service.py", "x = 1", ["auth"])
        body_heavy = _score_file("app/thing.py", "auth\nauth\n", ["auth"])
        self.assertGreater(path_heavy, body_heavy)

    def test_collect_local_files_respects_extension_and_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "a.py", "print(1)")
            _write(root, "b.py", "print(2)")
            _write(root, "c.md", "# doc")
            files = _collect_local_files(str(root), (".py",), 10)
            self.assertEqual(sorted(files), ["a.py", "b.py"])
            limited = _collect_local_files(str(root), (".py",), 1)
            self.assertEqual(len(limited), 1)

    def test_resolve_repository_handles_missing_path(self):
        label, root, files, kind = _resolve_repository("nope/not/here", None)
        self.assertEqual(kind, "missing")
        self.assertIsNone(root)
        self.assertEqual(files, {})


class TestMcpServerWiring(unittest.TestCase):
    def test_sdk_availability_probe_does_not_raise(self):
        self.assertIn(is_mcp_available(), (True, False))

    def test_server_builds_and_registers_three_tools(self):
        if not is_mcp_available():
            self.skipTest("official MCP SDK is not installed")

        import asyncio

        from knowledge_agent.mcp_server import build_server

        server = build_server(KnowledgeContextTools())
        tools = asyncio.run(server.list_tools())
        names = {tool.name for tool in tools}
        self.assertEqual(
            names,
            {
                "knowledge_get_architecture_context",
                "knowledge_verify_doc_drift",
                "knowledge_trace_issue_pr",
            },
        )
        by_name = {tool.name: tool for tool in tools}
        self.assertIn("query", by_name["knowledge_get_architecture_context"].input_schema["properties"])
        self.assertIn("doc_path", by_name["knowledge_verify_doc_drift"].input_schema["properties"])
        self.assertIn("issue_number", by_name["knowledge_trace_issue_pr"].input_schema["properties"])

    def test_tool_call_returns_json_serializable_payload(self):
        if not is_mcp_available():
            self.skipTest("official MCP SDK is not installed")

        import asyncio

        from knowledge_agent.mcp_server import build_server

        server = build_server(KnowledgeContextTools())
        result = asyncio.run(
            server.call_tool(
                "knowledge_get_architecture_context",
                {"query": "mcp server", "repo_path": str(REPO_ROOT)},
            )
        )
        payload = json.loads(result.content[0].text)
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["evidence"])

    def test_unsupported_transport_raises(self):
        from knowledge_agent.mcp_server import run

        with self.assertRaises(ValueError):
            run(transport="carrier-pigeon")

    def test_stdio_and_sse_dispatch_to_server_run(self):
        if not is_mcp_available():
            self.skipTest("official MCP SDK is not installed")

        from knowledge_agent.mcp_server import run_stdio, run_sse

        class Recorder:
            def __init__(self):
                self.calls = []

            def run(self, **kwargs):
                self.calls.append(kwargs)

        with patch("knowledge_agent.mcp_server.build_server", return_value=Recorder()) as mock_build:
            run_stdio()
            run_sse(host="0.0.0.0", port=9100)

        recorder = mock_build.return_value
        self.assertEqual(recorder.calls[0], {"transport": "stdio"})
        self.assertEqual(
            recorder.calls[1],
            {"transport": "sse", "host": "0.0.0.0", "port": 9100},
        )


class TestMcpCli(unittest.TestCase):
    def test_parser_defaults_to_stdio(self):
        args = build_mcp_parser().parse_args(["--stdio"])
        self.assertTrue(args.stdio)
        self.assertFalse(args.sse)
        self.assertEqual(args.host, "127.0.0.1")
        self.assertEqual(args.port, 8765)

    def test_parser_accepts_sse_options(self):
        args = build_mcp_parser().parse_args(["--sse", "--host", "0.0.0.0", "--port", "9999"])
        self.assertTrue(args.sse)
        self.assertEqual(args.port, 9999)

    def test_parser_rejects_conflicting_transports(self):
        with self.assertRaises(SystemExit):
            build_mcp_parser().parse_args(["--stdio", "--sse"])

    def test_cli_module_help_exposes_mcp_subcommand(self):
        result = subprocess.run(
            [sys.executable, "-m", "knowledge_agent", "mcp", "--help"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--stdio", result.stdout)
        self.assertIn("--sse", result.stdout)

    def test_cli_routes_mcp_subcommand(self):
        from knowledge_agent import __main__ as cli

        with patch("knowledge_agent.mcp_server.main", return_value=0) as mock_main:
            self.assertEqual(cli.main(["mcp", "--stdio"]), 0)
        mock_main.assert_called_once_with(["--stdio"])

    def test_cli_reports_missing_sdk(self):
        from knowledge_agent import __main__ as cli

        with patch("knowledge_agent.mcp_server.is_mcp_available", return_value=False):
            with self.assertRaises(SystemExit) as ctx:
                cli.main(["mcp", "--stdio"])
        self.assertEqual(ctx.exception.code, 1)

    def test_legacy_cli_still_parses_legacy_flags(self):
        from knowledge_agent import __main__ as cli

        args = cli.build_bot_parser().parse_args(
            ["--owner", "acme", "--repo", "core", "--issue", "1", "--comment", "@Knowledge hi"]
        )
        self.assertEqual(args.owner, "acme")
        self.assertEqual(args.target_type, None)


class TestMcpPackageExports(unittest.TestCase):
    def test_exports_are_public(self):
        import knowledge_agent
        import knowledge_engine

        for attr in [
            "KnowledgeContextTools",
            "is_mcp_available",
            "build_mcp_server",
            "run_mcp_server",
            "run_mcp_stdio",
            "run_mcp_sse",
        ]:
            self.assertTrue(hasattr(knowledge_agent, attr), f"knowledge_agent missing {attr}")
            self.assertIn(attr, knowledge_engine.__all__)

    def test_module_is_importable_without_sdk_errors(self):
        import knowledge_agent.mcp_server as module

        self.assertTrue(callable(module.build_server))
        self.assertTrue(callable(module.run))


if __name__ == "__main__":
    unittest.main()