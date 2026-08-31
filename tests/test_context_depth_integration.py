# tests/test_context_depth_integration.py
import unittest
from unittest.mock import patch, MagicMock
from knowledge_engine import ContextExplainer, KnowledgeAgent, IntentCategory
import adaptive_depth


class TestContextDepthIntegration(unittest.TestCase):
    def test_explainer_injects_depth_guidance_for_deep_score(self):
        prompt_deep = ContextExplainer.build_system_prompt(
            intent=IntentCategory.ARCHITECTURE_UNDERSTANDING,
            knowledge_rules=None,
            author="testuser",
            depth_score=8
        )
        self.assertIn("=== INTERNAL DEPTH GUIDANCE ===", prompt_deep)
        self.assertIn("DEEP TECHNICAL IMPLEMENTATION", prompt_deep)
        self.assertNotIn("8/10", prompt_deep)
        self.assertNotIn("score: 8", prompt_deep.lower())

    def test_explainer_injects_depth_guidance_for_simple_score(self):
        prompt_simple = ContextExplainer.build_system_prompt(
            intent=IntentCategory.ARCHITECTURE_UNDERSTANDING,
            knowledge_rules=None,
            author="testuser",
            depth_score=3
        )
        self.assertIn("=== INTERNAL DEPTH GUIDANCE ===", prompt_simple)
        self.assertIn("HIGH ACCESSIBILITY", prompt_simple)
        self.assertNotIn("3/10", prompt_simple)

    def test_explainer_injects_depth_guidance_for_balanced_score(self):
        prompt_balanced = ContextExplainer.build_system_prompt(
            intent=IntentCategory.ARCHITECTURE_UNDERSTANDING,
            knowledge_rules=None,
            author="testuser",
            depth_score=5
        )
        self.assertIn("=== INTERNAL DEPTH GUIDANCE ===", prompt_balanced)
        self.assertIn("BALANCED ENGINEERING KT", prompt_balanced)
        self.assertNotIn("5/10", prompt_balanced)

    def test_explainer_without_depth_score_omits_depth_guidance(self):
        prompt = ContextExplainer.build_system_prompt(
            intent=IntentCategory.ARCHITECTURE_UNDERSTANDING,
            knowledge_rules=None,
            author="testuser",
            depth_score=None
        )
        self.assertNotIn("=== INTERNAL DEPTH GUIDANCE ===", prompt)

    @patch("knowledge_engine.ContextRetriever.discover_context")
    @patch("knowledge_engine.KnowledgeAgent.call_llm")
    def test_agent_calculates_depth_from_deep_query(self, mock_call_llm, mock_discover):
        mock_discover.return_value = {
            "intent": IntentCategory.ARCHITECTURE_UNDERSTANDING,
            "owner": "testorg",
            "repo": "testrepo",
            "fetched_files": {},
            "commit_sha": "abc1234"
        }
        mock_call_llm.return_value = "Verified technical explanation."

        res = KnowledgeAgent.generate_answer(
            token="ghp_test",
            owner="testorg",
            repo="testrepo",
            query="@knowledge explain the AST bytecode and database connection pool at HTTP endpoint"
        )
        self.assertIn("answer", res)
        # Verify call_llm received system prompt with deep technical guidance
        self.assertTrue(mock_call_llm.called)
        system_prompt_arg = mock_call_llm.call_args[0][0]
        self.assertIn("=== INTERNAL DEPTH GUIDANCE ===", system_prompt_arg)
        self.assertIn("DEEP TECHNICAL IMPLEMENTATION", system_prompt_arg)
        self.assertIn("depth_score", res)
        self.assertGreaterEqual(res["depth_score"], 7)

    @patch("knowledge_engine.ContextRetriever.discover_context")
    @patch("knowledge_engine.KnowledgeAgent.call_llm")
    def test_agent_calculates_depth_from_simple_query(self, mock_call_llm, mock_discover):
        mock_discover.return_value = {
            "intent": IntentCategory.REPO_ONBOARDING,
            "owner": "testorg",
            "repo": "testrepo",
            "fetched_files": {},
            "commit_sha": "abc1234"
        }
        mock_call_llm.return_value = "Verified beginner explanation."

        res = KnowledgeAgent.generate_answer(
            token="ghp_test",
            owner="testorg",
            repo="testrepo",
            query="@knowledge can you explain me this more clearly, eli5 for a beginner"
        )
        self.assertIn("answer", res)
        # Verify call_llm received system prompt with high accessibility guidance
        self.assertTrue(mock_call_llm.called)
        system_prompt_arg = mock_call_llm.call_args[0][0]
        self.assertIn("=== INTERNAL DEPTH GUIDANCE ===", system_prompt_arg)
        self.assertIn("HIGH ACCESSIBILITY", system_prompt_arg)
        self.assertIn("depth_score", res)
        self.assertLessEqual(res["depth_score"], 4)

    @patch("knowledge_engine.ContextRetriever.discover_context")
    @patch("knowledge_engine.KnowledgeAgent.call_llm")
    def test_agent_honors_explicit_depth_override(self, mock_call_llm, mock_discover):
        mock_discover.return_value = {
            "intent": IntentCategory.GENERAL_QUERY,
            "owner": "testorg",
            "repo": "testrepo",
            "fetched_files": {},
            "commit_sha": "abc1234"
        }
        mock_call_llm.return_value = "Verified answer."

        res = KnowledgeAgent.generate_answer(
            token="ghp_test",
            owner="testorg",
            repo="testrepo",
            query="@knowledge what does this do?",
            depth_score=9
        )
        self.assertEqual(res["depth_score"], 9)
        system_prompt_arg = mock_call_llm.call_args[0][0]
        self.assertIn("DEEP TECHNICAL IMPLEMENTATION", system_prompt_arg)

    @patch("knowledge_engine.ContextRetriever.discover_context")
    @patch("knowledge_engine.KnowledgeAgent.call_llm")
    def test_agent_uses_conversation_history_for_depth_adjustment(self, mock_call_llm, mock_discover):
        mock_discover.return_value = {
            "intent": IntentCategory.ARCHITECTURE_UNDERSTANDING,
            "owner": "testorg",
            "repo": "testrepo",
            "fetched_files": {},
            "comments": [
                {"body": "Can you explain this in simpler terms?"}
            ],
            "commit_sha": "abc1234"
        }
        mock_call_llm.return_value = "Simplified answer."

        res = KnowledgeAgent.generate_answer(
            token="ghp_test",
            owner="testorg",
            repo="testrepo",
            query="@knowledge How does the router work?"
        )
        self.assertLess(res["depth_score"], 5)


if __name__ == "__main__":
    unittest.main()
