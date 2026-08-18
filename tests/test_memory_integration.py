"""Tests that KnowledgeAgent.generate_answer() actually reads and writes
persistent memory (#6), not just that memory_store.py works standalone."""

import os
import tempfile
import unittest
from unittest.mock import patch

import memory_store
from knowledge_engine import GitHubClient, KnowledgeAgent, ContextExplainer, IntentCategory


class TestGenerateAnswerMemoryWiring(unittest.TestCase):

    def setUp(self):
        fd, self.tmp_path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.remove(self.tmp_path)
        self._patcher = patch.object(memory_store, "DEFAULT_MEMORY_PATH", self.tmp_path)
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        if os.path.exists(self.tmp_path):
            os.remove(self.tmp_path)

    @patch.object(GitHubClient, "fetch_file_content", return_value="def login(): pass")
    @patch.object(GitHubClient, "fetch_repo_tree", return_value=["auth.py"])
    @patch.object(GitHubClient, "fetch_latest_commit_sha", return_value="sha1")
    @patch.object(KnowledgeAgent, "call_llm", return_value="Auth flows through auth.py.")
    @patch("knowledge_engine.is_mistral_configured", return_value=True)
    def test_first_call_writes_memory(self, mock_cfg, mock_llm, mock_sha, mock_tree, mock_file):
        store = memory_store.MemoryStore()
        self.assertIsNone(store.get("demo", "demo-repo", IntentCategory.ARCHITECTURE_UNDERSTANDING, ["auth"]))

        KnowledgeAgent.generate_answer(
            token="t", owner="demo", repo="demo-repo",
            query="@Knowledge explain the auth system architecture", author="Dev",
        )

        entry = store.get("demo", "demo-repo", IntentCategory.ARCHITECTURE_UNDERSTANDING, ["auth"])
        self.assertIsNotNone(entry)
        self.assertEqual(entry["summary"], "Auth flows through auth.py.")
        self.assertEqual(entry["commit_sha"], "sha1")

    @patch.object(GitHubClient, "fetch_issue", return_value={"number": 5, "title": "T", "body": "B"})
    @patch.object(GitHubClient, "fetch_issue_comments", return_value=[])
    @patch.object(GitHubClient, "fetch_file_content", return_value=None)
    @patch.object(KnowledgeAgent, "call_llm", return_value="This is the second answer.")
    @patch("knowledge_engine.is_mistral_configured", return_value=True)
    def test_second_related_call_sees_prior_context_in_prompt(
        self, mock_cfg, mock_llm, mock_file, mock_comments, mock_issue
    ):
        store = memory_store.MemoryStore()
        store.put(
            "demo", "demo-repo", IntentCategory.ISSUE_UNDERSTANDING, [],
            summary="Previously found: the login crash is a null session bug.",
            files_read=["auth.py"], commit_sha=None,
        )

        captured = {}
        original = ContextExplainer.build_user_prompt

        def _spy(evidence, query_author="Contributor"):
            captured["evidence"] = evidence
            return original(evidence, query_author=query_author)

        with patch.object(ContextExplainer, "build_user_prompt", side_effect=_spy):
            KnowledgeAgent.generate_answer(
                token="t", owner="demo", repo="demo-repo",
                query="@Knowledge what's issue #5 about?", author="Dev", issue_number=5,
            )

        prior = captured["evidence"].get("prior_context")
        self.assertIsNotNone(prior)
        self.assertIn("null session bug", prior["summary"])

    @patch.object(GitHubClient, "fetch_issue", return_value={"number": 5, "title": "T", "body": "B"})
    @patch.object(GitHubClient, "fetch_issue_comments", return_value=[])
    @patch.object(GitHubClient, "fetch_file_content", return_value=None)
    @patch.object(GitHubClient, "fetch_latest_commit_sha", return_value="sha_new")
    @patch.object(KnowledgeAgent, "call_llm", return_value="answer")
    @patch("knowledge_engine.is_mistral_configured", return_value=True)
    def test_stale_prior_context_is_flagged(
        self, mock_cfg, mock_llm, mock_sha, mock_file, mock_comments, mock_issue
    ):
        store = memory_store.MemoryStore()
        store.put(
            "demo", "demo-repo", IntentCategory.ISSUE_UNDERSTANDING, [],
            summary="Old finding.", files_read=[], commit_sha="sha_old",
        )

        captured = {}
        original = ContextExplainer.build_user_prompt

        def _spy(evidence, query_author="Contributor"):
            captured["evidence"] = evidence
            return original(evidence, query_author=query_author)

        with patch.object(ContextExplainer, "build_user_prompt", side_effect=_spy):
            KnowledgeAgent.generate_answer(
                token="t", owner="demo", repo="demo-repo",
                query="@Knowledge what's issue #5 about?", author="Dev", issue_number=5,
            )

        prior = captured["evidence"]["prior_context"]
        self.assertTrue(prior["stale"])

    def test_prior_investigation_appears_in_built_prompt_text(self):
        evidence = {
            "intent": IntentCategory.ARCHITECTURE_UNDERSTANDING,
            "query": "how does auth work", "owner": "o", "repo": "r",
            "fetched_files": {},
            "prior_context": {
                "summary": "Auth flows through auth.py -> session.py.",
                "files_read": ["auth.py", "session.py"],
                "stale": False,
            },
        }
        prompt = ContextExplainer.build_user_prompt(evidence, query_author="Dev")
        self.assertIn("PRIOR INVESTIGATION", prompt)
        self.assertIn("Auth flows through auth.py", prompt)
        self.assertIn("session.py", prompt)

    def test_no_prior_context_omits_the_section(self):
        evidence = {
            "intent": IntentCategory.ARCHITECTURE_UNDERSTANDING,
            "query": "how does auth work", "owner": "o", "repo": "r",
            "fetched_files": {},
        }
        prompt = ContextExplainer.build_user_prompt(evidence, query_author="Dev")
        self.assertNotIn("PRIOR INVESTIGATION", prompt)

    def test_system_prompt_instructs_verification_of_prior_context(self):
        prompt = ContextExplainer.build_system_prompt(
            intent=IntentCategory.ARCHITECTURE_UNDERSTANDING, knowledge_rules=None, author="Dev"
        )
        self.assertIn("PRIOR INVESTIGATION", prompt)
        self.assertIn("never as something already established", prompt)


if __name__ == "__main__":
    unittest.main()
