# tests/test_multi_repo.py
import unittest
import os
from multi_repo import MultiRepoConfig


class TestMultiRepoConfig(unittest.TestCase):
    def test_parse_from_knowledge_md_frontmatter_or_section(self):
        content = """
# Repository Guidelines

## Related Repositories
- `acme/backend-api`: Core FastAPI backend and database services
- `acme/shared-ui`: Shared design system components
- `acme/frontend-web`: Self repository that should be excluded
"""
        related = MultiRepoConfig.parse_related_repositories("acme", "frontend-web", content)
        self.assertEqual(len(related), 2)
        self.assertEqual(related[0]["owner"], "acme")
        self.assertEqual(related[0]["repo"], "backend-api")
        self.assertEqual(related[0]["description"], "Core FastAPI backend and database services")
        self.assertEqual(related[1]["owner"], "acme")
        self.assertEqual(related[1]["repo"], "shared-ui")
        self.assertEqual(related[1]["description"], "Shared design system components")

    def test_parse_from_knowledge_md_variations(self):
        content = """
## Related Repositories
* [acme/mobile-app](https://github.com/acme/mobile-app) - iOS and Android client
* acme/worker-service: Background queue worker
- `acme/analytics-api`
"""
        related = MultiRepoConfig.parse_related_repositories("acme", "frontend-web", content)
        self.assertEqual(len(related), 3)
        self.assertEqual(related[0]["owner"], "acme")
        self.assertEqual(related[0]["repo"], "mobile-app")
        self.assertEqual(related[0]["description"], "iOS and Android client")
        self.assertEqual(related[1]["repo"], "worker-service")
        self.assertEqual(related[1]["description"], "Background queue worker")
        self.assertEqual(related[2]["repo"], "analytics-api")
        self.assertEqual(related[2]["description"], "")

    def test_parse_from_env_var(self):
        os.environ["KNOWLEDGE_RELATED_REPOS"] = "acme/auth-service, acme/billing-api, acme/frontend-web"
        try:
            related = MultiRepoConfig.parse_related_repositories("acme", "frontend-web", None)
            self.assertEqual(len(related), 2)
            self.assertEqual(related[0]["owner"], "acme")
            self.assertEqual(related[0]["repo"], "auth-service")
            self.assertEqual(related[1]["owner"], "acme")
            self.assertEqual(related[1]["repo"], "billing-api")
        finally:
            del os.environ["KNOWLEDGE_RELATED_REPOS"]

    def test_parse_from_env_var_without_owner_prefix(self):
        os.environ["KNOWLEDGE_RELATED_REPOS"] = "auth-service, billing-api"
        try:
            related = MultiRepoConfig.parse_related_repositories("myorg", "frontend-web", None)
            self.assertEqual(len(related), 2)
            self.assertEqual(related[0]["owner"], "myorg")
            self.assertEqual(related[0]["repo"], "auth-service")
            self.assertEqual(related[1]["owner"], "myorg")
            self.assertEqual(related[1]["repo"], "billing-api")
        finally:
            del os.environ["KNOWLEDGE_RELATED_REPOS"]

    def test_merge_env_and_knowledge_content_enrichment(self):
        os.environ["KNOWLEDGE_RELATED_REPOS"] = "acme/backend-api, acme/docs"
        content = """
## Related Repositories
- `acme/backend-api`: Backend API service with PostgreSQL
- `acme/extra-service`: Extra utility microservice
"""
        try:
            related = MultiRepoConfig.parse_related_repositories("acme", "frontend-web", content)
            self.assertEqual(len(related), 3)
            # backend-api should have received description from markdown
            self.assertEqual(related[0]["repo"], "backend-api")
            self.assertEqual(related[0]["description"], "Backend API service with PostgreSQL")
            self.assertEqual(related[1]["repo"], "docs")
            self.assertEqual(related[1]["description"], "")
            self.assertEqual(related[2]["repo"], "extra-service")
            self.assertEqual(related[2]["description"], "Extra utility microservice")
        finally:
            del os.environ["KNOWLEDGE_RELATED_REPOS"]

    def test_case_insensitive_deduplication(self):
        content = """
- `Acme/Backend-API`: First mention
- `acme/backend-api`: Duplicate mention
- `ACME/FRONTEND-WEB`: Self repo in upper case
"""
        related = MultiRepoConfig.parse_related_repositories("acme", "frontend-web", content)
        self.assertEqual(len(related), 1)
        self.assertEqual(related[0]["repo"], "Backend-API")

    def test_empty_inputs_return_empty_list(self):
        if "KNOWLEDGE_RELATED_REPOS" in os.environ:
            del os.environ["KNOWLEDGE_RELATED_REPOS"]
        self.assertEqual(MultiRepoConfig.parse_related_repositories("acme", "frontend-web", None), [])
        self.assertEqual(MultiRepoConfig.parse_related_repositories("acme", "frontend-web", ""), [])

    def test_cross_repo_query_detection(self):
        # Positive detections
        positive_queries = [
            "layout.tsx is connected with which HTTP endpoint in backend repo?",
            "Which repositories are involved in this feature?",
            "Where is the frontend repo calling our api?",
            "How do services communicate across repos?",
            "What is the contract between microservices in the other repo?",
            "Is there a companion repo for shared styles?",
            "Can you check the companion service for schema definitions?",
            "How does multi-repo orchestration work here?"
        ]
        for q in positive_queries:
            self.assertTrue(MultiRepoConfig.is_cross_repo_query(q), f"Query '{q}' should be detected as cross-repo")

        # Negative detections
        negative_queries = [
            "How does auth work in this repo?",
            "Explain the architecture of the current project.",
            "Where is the main entrypoint file?",
            "What does the helper function do?",
            "",
            None
        ]
        for q in negative_queries:
            self.assertFalse(MultiRepoConfig.is_cross_repo_query(q), f"Query '{q}' should NOT be detected as cross-repo")


if __name__ == "__main__":
    unittest.main()
