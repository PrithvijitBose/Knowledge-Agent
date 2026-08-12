import unittest
from unittest.mock import patch
import knowledge_engine
from knowledge_engine import IntentCategory

class TestIntentDrivenKnowledgeEngine(unittest.TestCase):

    def test_relationship_extractor_prs(self):
        text = "Check out PR #82 and PR #101. Also see github.com/owner/repo/pull/105."
        prs = knowledge_engine.RelationshipExtractor.extract_referenced_prs(text)
        self.assertEqual(prs, [82, 101, 105])

    def test_relationship_extractor_issues(self):
        text = "Fixes #43 and closes issue #45. Related to github.com/owner/repo/issues/50."
        issues = knowledge_engine.RelationshipExtractor.extract_referenced_issues(text)
        self.assertEqual(issues, [43, 45, 50])

    def test_intent_classifier_categories(self):
        # 1. PR Understanding
        res_pr = knowledge_engine.IntentClassifier.classify("@Knowledge Why does PR #82 exist?")
        self.assertEqual(res_pr["intent"], IntentCategory.PR_UNDERSTANDING)
        self.assertEqual(res_pr["pr_numbers"], [82])

        # 2. Repo Onboarding
        res_onboard = knowledge_engine.IntentClassifier.classify("@Knowledge I just joined this repository. What should I learn first?")
        self.assertEqual(res_onboard["intent"], IntentCategory.REPO_ONBOARDING)

        # 3. Architecture Understanding
        res_arch = knowledge_engine.IntentClassifier.classify("@Knowledge How does authentication work in this repository?")
        self.assertEqual(res_arch["intent"], IntentCategory.ARCHITECTURE_UNDERSTANDING)
        self.assertIn("auth", res_arch["keywords"])

        # 4. Contribution Guidance
        res_contrib = knowledge_engine.IntentClassifier.classify("@Knowledge How do I run tests and setup dev environment?")
        self.assertEqual(res_contrib["intent"], IntentCategory.CONTRIBUTION_GUIDANCE)

        # 5. Issue Understanding
        res_issue = knowledge_engine.IntentClassifier.classify("@Knowledge What do I need to know before contributing to Issue #43?")
        self.assertEqual(res_issue["intent"], IntentCategory.ISSUE_UNDERSTANDING)
        self.assertEqual(res_issue["issue_numbers"], [43])

    @patch("knowledge_engine.is_mistral_configured", return_value=False)
    def test_architecture_fallback_response(self, mock_mistral):
        res = knowledge_engine.KnowledgeAgent.generate_answer(
            token="",
            owner="demo",
            repo="demo-repo",
            query="@Knowledge How does authentication work in this repository?",
            author="DeveloperJane"
        )
        self.assertEqual(res["intent"], IntentCategory.ARCHITECTURE_UNDERSTANDING)
        self.assertEqual(res["author"], "DeveloperJane")
        self.assertIn("DeveloperJane", res["answer"])
        self.assertIn("Subsystem Architecture Overview", res["answer"])

    @patch("knowledge_engine.is_mistral_configured", return_value=False)
    def test_repo_onboarding_fallback_response(self, mock_mistral):
        res = knowledge_engine.KnowledgeAgent.generate_answer(
            token="",
            owner="demo",
            repo="demo-repo",
            query="@Knowledge I just joined. What should I learn first?",
            author="NewContributor"
        )
        self.assertEqual(res["intent"], IntentCategory.REPO_ONBOARDING)
        self.assertEqual(res["author"], "NewContributor")
        self.assertIn("NewContributor", res["answer"])
        self.assertIn("Cognitive Priority Tiering", res["answer"])


if __name__ == "__main__":
    unittest.main()
