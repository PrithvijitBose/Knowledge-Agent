import unittest
from unittest.mock import patch, MagicMock
from knowledge_agent.prompt import ContextExplainer
from knowledge_agent.intent import IntentCategory
from knowledge_agent.agent import KnowledgeAgent


class TestHumanEngineeringKT(unittest.TestCase):
    """Hermetic unit tests validating Human Engineering KT (Issue #58)."""

    def test_dynamic_formatting_cues_in_system_prompt(self):
        """Verifies ContextExplainer.build_system_prompt contains dynamic formatting cues
        that actively penalize repetitive section headers and robotic templates."""
        sys_prompt = ContextExplainer.build_system_prompt(
            intent=IntentCategory.FEATURE_UNDERSTANDING,
            knowledge_rules=None,
            author="Sarah"
        )

        # 1. Check penalty against repetitive boilerplate headers
        self.assertIn("10. **No rigid response templates or repetitive section headers**", sys_prompt)
        self.assertIn("Actively avoid repetitive, formulaic section headers", sys_prompt)
        self.assertIn("Architecture & Component Flow", sys_prompt)
        self.assertIn("Cognitive Priority Tiering", sys_prompt)
        self.assertIn("Recommended 30-Minute Learning Path", sys_prompt)
        self.assertIn("Component Deep Dive", sys_prompt)

        # 2. Check dynamic narrative cues
        self.assertIn("Explain the narrative flow from entry point down through components naturally", sys_prompt)
        self.assertIn("Explain the 'why' for each connection", sys_prompt)
        self.assertIn("Do NOT use rigid prefabricated markdown tables or checklists", sys_prompt)
        self.assertIn("Senior Staff Engineer demeanor", sys_prompt)

    def test_few_shot_contrastive_examples_in_prompt(self):
        """Verifies few-shot contrastive exemplars demonstrating Mechanical Template (Bad)
        vs. Natural Senior Staff Explanation (Good)."""
        sys_prompt = ContextExplainer.build_system_prompt(
            intent=IntentCategory.ARCHITECTURE_UNDERSTANDING,
            knowledge_rules=None,
            author="Alex"
        )

        self.assertIn("FEW-SHOT CONTRASTIVE GUIDELINES", sys_prompt)
        self.assertIn("❌ Mechanical Template (Bad):", sys_prompt)
        self.assertIn("### Architecture & Component Flow", sys_prompt)
        self.assertIn("### Component Connections", sys_prompt)
        self.assertIn("LandingPage.tsx` connects to `HeroSection.tsx", sys_prompt)
        self.assertIn("Why this is bad:", sys_prompt)

        self.assertIn("✅ Natural Senior Staff Explanation (Good):", sys_prompt)
        self.assertIn("LandingPage.tsx` acts as the root orchestrator", sys_prompt)
        self.assertIn("The reason both `HeroSection` and `PricingTable` connect into `AuthModal.tsx`", sys_prompt)
        self.assertIn("to decouple authentication triggers from billing logic", sys_prompt)
        self.assertIn("Why this is good:", sys_prompt)

    def test_internal_scoring_and_meta_instructions_sanitization(self):
        """Verifies that internal depth points, score calculations, and meta-instructions
        never leak into user output and are stripped by sanitize_output."""
        raw_llm_output_with_leaks = (
            "=== INTERNAL DEPTH GUIDANCE ===\n"
            "ADAPTIVE EXPLANATION DEPTH: DEEP TECHNICAL IMPLEMENTATION\n"
            "- Trace exact function signatures.\n"
            "=== END INTERNAL DEPTH GUIDANCE ===\n\n"
            "[Internal Depth Score: 8/10]\n"
            "depth_score: 8\n\n"
            "LandingPage acts as the primary orchestrator seeding auth state down to HeroSection and PricingTable.\n"
            "HeroSection delegates checkout intent to AuthModal to decouple billing logic."
        )

        sanitized = ContextExplainer.sanitize_output(raw_llm_output_with_leaks)

        self.assertNotIn("INTERNAL DEPTH GUIDANCE", sanitized)
        self.assertNotIn("ADAPTIVE EXPLANATION DEPTH", sanitized)
        self.assertNotIn("Internal Depth Score", sanitized)
        self.assertNotIn("8/10", sanitized)
        self.assertNotIn("depth_score", sanitized)
        self.assertIn("LandingPage acts as the primary orchestrator", sanitized)
        self.assertIn("HeroSection delegates checkout intent to AuthModal", sanitized)

    @patch("knowledge_agent.retriever.ContextRetriever.discover_context")
    @patch("knowledge_agent.agent.KnowledgeAgent.call_llm")
    def test_agent_generate_answer_sanitizes_internal_leaks(self, mock_call_llm, mock_discover):
        """Hermetically verifies KnowledgeAgent.generate_answer cleanses accidental LLM leaks."""
        mock_discover.return_value = {
            "intent": IntentCategory.FEATURE_UNDERSTANDING,
            "owner": "testorg",
            "repo": "landing-app",
            "fetched_files": {
                "LandingPage.tsx": "export const LandingPage = () => <HeroSection />;"
            },
            "commit_sha": "abc1234"
        }
        mock_call_llm.return_value = (
            "[Adaptive Depth Level: 7/10]\n"
            "ADAPTIVE EXPLANATION DEPTH: DEEP TECHNICAL IMPLEMENTATION\n\n"
            "The landing page initializes user session state and passes it to the children."
        )

        res = KnowledgeAgent.generate_answer(
            token="ghp_test",
            owner="testorg",
            repo="landing-app",
            query="@Knowledge Explain how the landing page works and why these components connect.",
            author="Dev"
        )

        self.assertNotIn("Adaptive Depth Level", res["answer"])
        self.assertNotIn("7/10", res["answer"])
        self.assertNotIn("ADAPTIVE EXPLANATION DEPTH", res["answer"])
        self.assertIn("The landing page initializes user session state", res["answer"])

    def test_user_prompt_formatting_intent_distinction(self):
        """Verifies build_user_prompt creates natural narrative prompts for code/feature queries
        and clean bot handoffs for issue/PR triage."""
        feature_evidence = {
            "intent": IntentCategory.FEATURE_UNDERSTANDING,
            "query": "@Knowledge Explain how the landing page works and why these components connect.",
            "owner": "testorg",
            "repo": "webapp",
            "fetched_files": {"LandingPage.tsx": "export default LandingPage;"}
        }
        feature_prompt = ContextExplainer.build_user_prompt(feature_evidence, query_author="Jane")
        self.assertIn("senior staff engineer", feature_prompt)
        self.assertIn("Explain the narrative flow from entry point down through components", feature_prompt)
        self.assertIn("focusing on WHY connections exist", feature_prompt)
        self.assertNotIn("#### What this PR does:", feature_prompt)

        pr_evidence = {
            "intent": IntentCategory.PR_UNDERSTANDING,
            "query": "Review PR #5",
            "owner": "testorg",
            "repo": "webapp",
            "fetched_files": {},
            "pr": {"number": 5, "title": "Add Auth", "body": "Auth implementation"}
        }
        pr_prompt = ContextExplainer.build_user_prompt(pr_evidence, query_author="Bob")
        self.assertIn("### Knowledge-Agent Bot:", pr_prompt)
        self.assertIn("#### What this PR does:", pr_prompt)

    @patch("knowledge_agent.retriever.ContextRetriever.discover_context")
    @patch("knowledge_agent.agent.KnowledgeAgent.call_llm")
    def test_offline_hermetic_connective_explanation_synthesis(self, mock_call_llm, mock_discover):
        """Hermetically verifies response synthesis for landing page component flow query."""
        mock_discover.return_value = {
            "intent": IntentCategory.FEATURE_UNDERSTANDING,
            "owner": "acme",
            "repo": "storefront",
            "fetched_files": {
                "LandingPage.tsx": "// Root entry component",
                "HeroSection.tsx": "// Hero presentation",
                "PricingTable.tsx": "// Pricing matrix",
                "AuthModal.tsx": "// Authentication modal"
            },
            "commit_sha": "sha_landing_page"
        }

        senior_staff_response = (
            "When a user navigates to the storefront, `LandingPage.tsx` acts as the root orchestrator. "
            "It queries session state using `useAuth()` and passes the active plan tier to `HeroSection.tsx` "
            "and `PricingTable.tsx`.\n\n"
            "Both components connect to `AuthModal.tsx` because unauthenticated actions (like clicking a tier CTA) "
            "need to trigger auth without losing the selected checkout intent. Once authenticated, `AuthModal.tsx` "
            "updates the shared auth context so `PricingTable.tsx` immediately reflects the upgraded status.\n\n"
            "To trace this, start in `LandingPage.tsx` to see how the plan state is initialized, then follow the CTA callback into `AuthModal.tsx`."
        )
        mock_call_llm.return_value = senior_staff_response

        res = KnowledgeAgent.generate_answer(
            token="ghp_mock",
            owner="acme",
            repo="storefront",
            query="@Knowledge Explain how the landing page works and why these components connect.",
            author="ContributorSam"
        )

        # 1. Asserts connective narrative explanation is present
        self.assertIn("acts as the root orchestrator", res["answer"])
        self.assertIn("Both components connect to `AuthModal.tsx` because", res["answer"])
        self.assertIn("To trace this, start in `LandingPage.tsx`", res["answer"])

        # 2. Asserts NO generic boilerplate headers are present
        self.assertNotIn("### Architecture & Component Flow", res["answer"])
        self.assertNotIn("### Cognitive Priority Tiering", res["answer"])
        self.assertNotIn("### Recommended 30-Minute Learning Path", res["answer"])
        self.assertNotIn("### Component Deep Dive", res["answer"])

        # 3. Asserts depth_score internal point is returned in dict metadata but not in user answer text
        self.assertIn("depth_score", res)
        self.assertNotIn(f"depth_score: {res['depth_score']}", res["answer"])


if __name__ == "__main__":
    unittest.main()
