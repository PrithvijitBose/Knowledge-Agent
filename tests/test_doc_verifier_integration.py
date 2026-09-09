import unittest
from unittest.mock import patch
from knowledge_agent.intent import IntentCategory, IntentClassifier
from knowledge_agent.prompt import ContextExplainer
from knowledge_agent.retriever import ContextRetriever
from knowledge_agent.agent import KnowledgeAgent
from knowledge_agent.github import GitHubClient


class TestDocVerifierIntegration(unittest.TestCase):
    def test_intent_classification_for_doc_verification(self):
        queries = [
            "@knowledge verify documentation against the code",
            "does the readme match actual implementation?",
            "check for doc drift in this repository",
            "are there any documentation discrepancies here?",
            "please verify doc claims against code",
        ]
        for q in queries:
            result = IntentClassifier.classify(q)
            self.assertEqual(
                result["intent"],
                IntentCategory.DOC_VERIFICATION,
                f"Query '{q}' should have been classified as DOC_VERIFICATION, got {result['intent']}"
            )

    def test_system_prompt_includes_doc_verification_strategy(self):
        sys_prompt = ContextExplainer.build_system_prompt(
            intent=IntentCategory.DOC_VERIFICATION,
            knowledge_rules=None,
            author="DevUser"
        )
        self.assertIn("Documentation vs Implementation verification", sys_prompt)
        self.assertIn("Cross-reference claims", sys_prompt)

    def test_user_prompt_injects_discrepancy_evidence(self):
        evidence = {
            "intent": IntentCategory.DOC_VERIFICATION,
            "query": "verify docs",
            "owner": "testorg",
            "repo": "testrepo",
            "fetched_files": {
                "README.md": "# Docs\nCall `missing_func()` to run.",
                "main.py": "def other_func(): pass",
            },
            "doc_discrepancies": {
                "total_discrepancies": 1,
                "discrepancies": [
                    {
                        "type": "MISSING_IMPLEMENTATION",
                        "claim": "missing_func()",
                        "source_doc": "README.md",
                        "line": 2,
                        "details": "Documented function `missing_func()` was not found in inspected source files.",
                    }
                ],
                "summary": "⚠️ Documentation vs Implementation Discrepancies (1 detected):\n| Type | Claim | Details |",
            }
        }
        user_prompt = ContextExplainer.build_user_prompt(evidence, query_author="DevUser")
        self.assertIn("--- DOCUMENTATION VS IMPLEMENTATION EVIDENCE ---", user_prompt)
        self.assertIn("missing_func()", user_prompt)

    @patch.object(GitHubClient, "fetch_latest_commit_sha", return_value="sha123")
    @patch.object(GitHubClient, "fetch_repo_tree", return_value=["README.md", "auth.py"])
    @patch.object(GitHubClient, "fetch_file_content")
    def test_discover_context_populates_doc_discrepancies(self, mock_fetch_file, mock_tree, mock_sha):
        def fake_file(token, owner, repo, path, ref=None):
            if path == "README.md":
                return "# Auth\nUse `verify_jwt_token(secret)` to authenticate.\nCall `POST /api/v1/auth/token`"
            elif path == "auth.py":
                return "def basic_login(u, p):\n    return True"
            return None

        mock_fetch_file.side_effect = fake_file

        evidence = ContextRetriever.discover_context(
            token="ghp_test",
            owner="acme",
            repo="core",
            query="@knowledge verify doc claims",
            intent_info={"intent": IntentCategory.DOC_VERIFICATION, "keywords": []}
        )

        self.assertIn("doc_discrepancies", evidence)
        doc_disc = evidence["doc_discrepancies"]
        self.assertGreater(doc_disc["total_discrepancies"], 0)
        claims = [d["claim"] for d in doc_disc["discrepancies"]]
        self.assertTrue(any("verify_jwt_token" in c for c in claims))

    @patch("knowledge_agent.retriever.ContextRetriever.discover_context")
    @patch("knowledge_agent.agent.KnowledgeAgent.call_llm")
    def test_agent_structured_context_contains_doc_discrepancies(self, mock_call_llm, mock_discover):
        mock_discover.return_value = {
            "intent": IntentCategory.DOC_VERIFICATION,
            "owner": "testorg",
            "repo": "testrepo",
            "commit_sha": "abc123",
            "fetched_files": {"README.md": "# Docs", "main.py": "def test(): pass"},
            "doc_discrepancies": {
                "total_discrepancies": 1,
                "discrepancies": [{"type": "MISSING_IMPLEMENTATION", "claim": "foo()"}],
                "summary": "1 discrepancy found"
            }
        }
        mock_call_llm.return_value = "Verified that foo() is missing in main.py."

        res = KnowledgeAgent.generate_answer(
            token="ghp_test",
            owner="testorg",
            repo="testrepo",
            query="verify documentation against code"
        )

        self.assertIn("structured_context", res)
        self.assertIn("doc_discrepancies", res["structured_context"])
        self.assertEqual(res["structured_context"]["doc_discrepancies"]["total_discrepancies"], 1)


if __name__ == "__main__":
    unittest.main()
