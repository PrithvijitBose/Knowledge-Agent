import unittest
from unittest.mock import patch, MagicMock
from knowledge_engine import ContextRetriever, ContextExplainer, CitationFormatter, KnowledgeAgent, IntentCategory
from multi_repo import MultiRepoConfig


class TestMultiRepoRetriever(unittest.TestCase):

    @patch("knowledge_engine.GitHubClient.fetch_repo_tree")
    @patch("knowledge_engine.GitHubClient.fetch_file_content")
    @patch("knowledge_engine.GitHubClient.fetch_commit_sha")
    def test_cross_repo_retrieval_for_endpoint_queries(self, mock_sha, mock_fetch_file, mock_tree):
        mock_sha.return_value = "main123"
        mock_tree.return_value = [
            "backend/app/main.py",
            "backend/app/routers/users.py",
            "backend/app/db.py"
        ]
        mock_fetch_file.side_effect = lambda token, o, r, path, ref=None: (
            "@app.get('/api/v1/layout')\ndef get_layout(): return {'status': 'ok'}" if "main.py" in path else None
        )

        with patch.object(MultiRepoConfig, "parse_related_repositories", return_value=[{"owner": "acme", "repo": "backend-api", "description": "Backend service"}]):
            evidence = ContextRetriever.discover_context(
                token="ghp_test",
                owner="acme",
                repo="frontend-web",
                query="@knowledge layout.tsx is connected with which HTTP endpoint in backend repo?",
                intent_info={"intent": IntentCategory.FEATURE_UNDERSTANDING, "keywords": ["endpoint", "backend"]}
            )

            self.assertIn("cross_repo_evidence", evidence)
            self.assertIn("acme/backend-api", evidence["cross_repo_evidence"])
            self.assertIn("backend/app/main.py", evidence["cross_repo_evidence"]["acme/backend-api"]["fetched_files"])
            self.assertIn("main123", evidence["cross_repo_evidence"]["acme/backend-api"]["sha"])
            self.assertEqual(evidence["cross_repo_evidence"]["acme/backend-api"]["description"], "Backend service")

    def test_multi_repo_citation_formatting(self):
        citations = CitationFormatter.build_citations_section(
            owner="acme",
            repo="frontend-web",
            commit_sha="abc1234",
            files_read=["src/layout.tsx"],
            cross_repo_files={"acme/backend-api": {"sha": "def5678", "files": ["app/main.py"]}}
        )
        self.assertIn("frontend-web", citations)
        self.assertIn("acme/backend-api", citations)
        self.assertIn("app/main.py", citations)
        self.assertIn("### 📚 Referenced Files & Citations", citations)
        self.assertIn("### 📚 Related Repository Citations", citations)
        self.assertIn("https://github.com/acme/backend-api/blob/def5678/app/main.py", citations)

    def test_multi_repo_citation_formatting_cross_repo_only(self):
        citations = CitationFormatter.build_citations_section(
            owner="acme",
            repo="frontend-web",
            commit_sha="abc1234",
            files_read=[],
            cross_repo_files={"acme/backend-api": {"sha": "def5678", "files_read": ["app/main.py"]}}
        )
        self.assertNotIn("Referenced Files & Citations", citations)
        self.assertIn("### 📚 Related Repository Citations", citations)
        self.assertIn("https://github.com/acme/backend-api/blob/def5678/app/main.py", citations)

    def test_multi_repo_citation_formatting_empty_both(self):
        citations = CitationFormatter.build_citations_section(
            owner="acme",
            repo="frontend-web",
            commit_sha="abc1234",
            files_read=[],
            cross_repo_files={}
        )
        self.assertEqual(citations, "")

    def test_context_explainer_user_prompt_with_cross_repo(self):
        evidence = {
            "intent": IntentCategory.FEATURE_UNDERSTANDING,
            "query": "Which API endpoint does layout.tsx call in the backend repo?",
            "owner": "acme",
            "repo": "frontend-web",
            "fetched_files": {
                "src/layout.tsx": "export default function Layout() { fetch('/api/v1/layout'); }"
            },
            "cross_repo_evidence": {
                "acme/backend-api": {
                    "description": "Core FastAPI backend service",
                    "fetched_files": {
                        "backend/app/main.py": "@app.get('/api/v1/layout')\ndef get_layout(): return {'status': 'ok'}"
                    }
                }
            }
        }
        prompt = ContextExplainer.build_user_prompt(evidence, query_author="alice")
        self.assertIn("--- CROSS-REPOSITORY EVIDENCE ---", prompt)
        self.assertIn("Companion Repository: acme/backend-api (Core FastAPI backend service)", prompt)
        self.assertIn("File [acme/backend-api:backend/app/main.py]:", prompt)
        self.assertIn("@app.get('/api/v1/layout')", prompt)
        self.assertIn("File [src/layout.tsx]:", prompt)

    def test_context_explainer_user_prompt_without_cross_repo(self):
        evidence = {
            "intent": IntentCategory.ARCHITECTURE_UNDERSTANDING,
            "query": "How is auth implemented?",
            "owner": "acme",
            "repo": "frontend-web",
            "fetched_files": {
                "src/auth.ts": "export function login() {}"
            }
        }
        prompt = ContextExplainer.build_user_prompt(evidence, query_author="bob")
        self.assertNotIn("--- CROSS-REPOSITORY EVIDENCE ---", prompt)
        self.assertIn("File [src/auth.ts]:", prompt)

    @patch("knowledge_engine.GitHubClient.fetch_repo_tree")
    @patch("knowledge_engine.GitHubClient.fetch_file_content")
    @patch("knowledge_engine.GitHubClient.fetch_commit_sha")
    def test_non_cross_repo_query_skips_cross_repo_retrieval(self, mock_sha, mock_fetch_file, mock_tree):
        mock_sha.return_value = "main123"
        mock_fetch_file.return_value = "function test() {}"

        evidence = ContextRetriever.discover_context(
            token="ghp_test",
            owner="acme",
            repo="frontend-web",
            query="How do I run tests in this repo?",
            intent_info={"intent": IntentCategory.CONTRIBUTION_GUIDANCE, "keywords": ["test"]}
        )
        self.assertNotIn("cross_repo_evidence", evidence)

    @patch("knowledge_engine.GitHubClient.fetch_repo_tree")
    @patch("knowledge_engine.GitHubClient.fetch_file_content")
    @patch("knowledge_engine.GitHubClient.fetch_commit_sha")
    def test_cross_repo_retrieval_bounds_repositories_to_three(self, mock_sha, mock_fetch_file, mock_tree):
        mock_sha.return_value = "sha_abc"
        mock_tree.return_value = ["app/main.py"]
        mock_fetch_file.return_value = "content"

        mock_repos = [
            {"owner": "acme", "repo": f"service-{i}", "description": f"Service {i}"}
            for i in range(1, 6)
        ]

        with patch.object(MultiRepoConfig, "parse_related_repositories", return_value=mock_repos):
            evidence = ContextRetriever.discover_context(
                token="ghp_test",
                owner="acme",
                repo="frontend-web",
                query="How do backend repos handle notifications across repos?",
                intent_info={"intent": IntentCategory.FEATURE_UNDERSTANDING, "keywords": ["backend"]}
            )

            self.assertIn("cross_repo_evidence", evidence)
            self.assertLessEqual(len(evidence["cross_repo_evidence"]), 3)
            self.assertEqual(len(evidence["cross_repo_evidence"]), 3)
            self.assertIn("acme/service-1", evidence["cross_repo_evidence"])
            self.assertIn("acme/service-2", evidence["cross_repo_evidence"])
            self.assertIn("acme/service-3", evidence["cross_repo_evidence"])
            self.assertNotIn("acme/service-4", evidence["cross_repo_evidence"])

    @patch("knowledge_engine.ContextRetriever.discover_context")
    @patch("knowledge_engine.KnowledgeAgent.call_llm")
    def test_knowledge_agent_generate_answer_with_cross_repo(self, mock_call_llm, mock_discover):
        mock_discover.return_value = {
            "intent": IntentCategory.FEATURE_UNDERSTANDING,
            "query": "Which API endpoint does layout.tsx call in the backend repo?",
            "owner": "acme",
            "repo": "frontend-web",
            "commit_sha": "abc1234",
            "fetched_files": {"src/layout.tsx": "fetch('/api/v1/layout')"},
            "cross_repo_evidence": {
                "acme/backend-api": {
                    "owner": "acme",
                    "repo": "backend-api",
                    "sha": "def5678",
                    "description": "Backend API",
                    "files_read": ["app/routes.py"],
                    "fetched_files": {"app/routes.py": "@router.get('/api/v1/layout')"}
                }
            }
        }
        mock_call_llm.return_value = "layout.tsx calls /api/v1/layout defined in backend-api."

        result = KnowledgeAgent.generate_answer(
            token="ghp_test",
            owner="acme",
            repo="frontend-web",
            query="Which API endpoint does layout.tsx call in the backend repo?"
        )

        self.assertIn("answer", result)
        self.assertIn("citations", result)
        self.assertIn("frontend-web", result["citations"])
        self.assertIn("acme/backend-api", result["citations"])
        self.assertIn("app/routes.py", result["citations"])
        self.assertIn("cross_repo_evidence", result["structured_context"])


if __name__ == "__main__":
    unittest.main()
