import unittest
from unittest.mock import patch
import knowledge_engine

class TestKnowledgeEngine(unittest.TestCase):

    def test_relationship_extractor_prs(self):
        text = "Check out PR #82 and PR #101. Also see github.com/owner/repo/pull/105."
        prs = knowledge_engine.RelationshipExtractor.extract_referenced_prs(text)
        self.assertEqual(prs, [82, 101, 105])

    def test_relationship_extractor_issues(self):
        text = "Fixes #43 and closes issue #45. Related to github.com/owner/repo/issues/50."
        issues = knowledge_engine.RelationshipExtractor.extract_referenced_issues(text)
        self.assertEqual(issues, [43, 45, 50])

    def test_entry_point_classifier(self):
        self.assertEqual(knowledge_engine.EntryPointClassifier.classify("Why does PR #82 look like this?"), "PR")
        self.assertEqual(knowledge_engine.EntryPointClassifier.classify("I have never worked on this repository. How should I learn this codebase?"), "REPO_ONBOARDING")
        self.assertEqual(knowledge_engine.EntryPointClassifier.classify("I need to work on Issue #43. What should I understand first?"), "ISSUE")

    def test_repo_onboarding_context_building(self):
        ctx = knowledge_engine.EngineeringContextGraph.build_repo_onboarding_context("", "owner", "repo")
        self.assertEqual(ctx["type"], "REPO_ONBOARDING")

    @patch("knowledge_engine.is_mistral_configured", return_value=False)
    def test_knowledge_agent_fallback(self, mock_mistral):
        res = knowledge_engine.KnowledgeAgent.generate_answer(
            token="",
            owner="demo",
            repo="demo-repo",
            query="I have never worked on this repository. How should I learn this codebase?"
        )
        self.assertIn("answer", res)
        self.assertIn("Cognitive Priority Tiering", res["answer"])
        self.assertEqual(res["type"], "REPO_ONBOARDING")


if __name__ == "__main__":
    unittest.main()
