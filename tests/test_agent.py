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

    def test_intent_classifier_routes_contribution_queries(self):
        """Verifies IntentClassifier accurately routes where to start, how to tackle,
        and contribution guide questions to CONTRIBUTION_GUIDANCE (Issue #59)."""
        from knowledge_agent.intent import IntentClassifier

        q1 = IntentClassifier.classify("@Knowledge Where should I start to solve Issue #42?")
        self.assertEqual(q1["intent"], IntentCategory.CONTRIBUTION_GUIDANCE)
        self.assertEqual(q1["issue_numbers"], [42])

        q2 = IntentClassifier.classify("where should i start")
        self.assertEqual(q2["intent"], IntentCategory.CONTRIBUTION_GUIDANCE)

        q3 = IntentClassifier.classify("how do i tackle this")
        self.assertEqual(q3["intent"], IntentCategory.CONTRIBUTION_GUIDANCE)

        q4 = IntentClassifier.classify("contribution guide for issue #15")
        self.assertEqual(q4["intent"], IntentCategory.CONTRIBUTION_GUIDANCE)
        self.assertEqual(q4["issue_numbers"], [15])

        q5 = IntentClassifier.classify("how do i tackle issue #99")
        self.assertEqual(q5["intent"], IntentCategory.CONTRIBUTION_GUIDANCE)
        self.assertEqual(q5["issue_numbers"], [99])

        # Contrast: general issue context request vs. investigation pathway request
        q6 = IntentClassifier.classify("@Knowledge What do I need to know before contributing to Issue #43?")
        self.assertEqual(q6["intent"], IntentCategory.ISSUE_UNDERSTANDING)

    @patch("knowledge_agent.github.GitHubClient.fetch_repo_tree")
    @patch("knowledge_agent.github.GitHubClient.fetch_file_content")
    @patch("knowledge_agent.github.GitHubClient.fetch_issue")
    @patch("knowledge_agent.github.GitHubClient.fetch_issue_comments")
    def test_context_retriever_gathers_related_test_files_for_contribution_queries(
        self, mock_comments, mock_issue, mock_file_content, mock_repo_tree
    ):
        """Verifies ContextRetriever discovers related test files alongside primary files
        for contribution queries (Issue #59)."""
        from knowledge_agent.retriever import ContextRetriever

        mock_issue.return_value = {
            "number": 42,
            "title": "Bug in auth prompt formatting",
            "body": "Inspect knowledge_agent/prompt.py for issues."
        }
        mock_comments.return_value = []
        mock_repo_tree.return_value = [
            "knowledge_agent/prompt.py",
            "tests/test_prompt.py",
            "pyproject.toml",
            "README.md",
            "CONTRIBUTING.md"
        ]

        def fake_file_content(token, owner, repo, path, ref=None):
            if path == "knowledge_agent/prompt.py":
                return "class ContextExplainer:\n    pass"
            elif path == "tests/test_prompt.py":
                return "def test_prompt():\n    assert True"
            elif path == "pyproject.toml":
                return "[tool.pytest]\nminversion = '6.0'"
            elif path == "CONTRIBUTING.md":
                return "Run `pytest` to verify your changes."
            return None

        mock_file_content.side_effect = fake_file_content

        evidence = ContextRetriever.discover_context(
            token="ghp_test",
            owner="testorg",
            repo="testrepo",
            query="@Knowledge Where should I start to solve Issue #42?",
            intent_info={
                "intent": IntentCategory.CONTRIBUTION_GUIDANCE,
                "issue_numbers": [42],
                "files": ["knowledge_agent/prompt.py"],
                "keywords": ["prompt"]
            },
            issue_number=42
        )

        self.assertEqual(evidence["intent"], IntentCategory.CONTRIBUTION_GUIDANCE)
        self.assertIn("test_files", evidence)
        self.assertIn("tests/test_prompt.py", evidence["test_files"])
        self.assertIn("tests/test_prompt.py", evidence["fetched_files"])
        self.assertIn("knowledge_agent/prompt.py", evidence["fetched_files"])
        self.assertIn("CONTRIBUTING.md", evidence["fetched_files"])
        self.assertIn("pyproject.toml", evidence["fetched_files"])

    def test_prompt_synthesis_for_contribution_guidance(self):
        """Verifies build_system_prompt and build_user_prompt construct the 3-step
        investigation pathway without prescribing speculative code fixes (Issue #59)."""
        sys_prompt = ContextExplainer.build_system_prompt(
            intent=IntentCategory.CONTRIBUTION_GUIDANCE,
            knowledge_rules=None,
            author="DevCandidate"
        )
        self.assertIn("Contribution Guidance (Structured Investigation Pathways)", sys_prompt)
        self.assertIn("Do NOT prescribe speculative code solutions", sys_prompt)
        self.assertIn("Starting Point & Reproduction", sys_prompt)
        self.assertIn("State & Subsystem Dynamics", sys_prompt)
        self.assertIn("Test Suite & Verification Commands", sys_prompt)

        user_prompt = ContextExplainer.build_user_prompt({
            "intent": IntentCategory.CONTRIBUTION_GUIDANCE,
            "query": "@Knowledge Where should I start to solve Issue #42?",
            "owner": "testorg",
            "repo": "testrepo",
            "fetched_files": {
                "knowledge_agent/prompt.py": "code",
                "tests/test_prompt.py": "test_code"
            },
            "test_files": ["tests/test_prompt.py"]
        }, query_author="DevCandidate")

        self.assertIn("Related Test Files Found:", user_prompt)
        self.assertIn("tests/test_prompt.py", user_prompt)
        self.assertIn("Provide structured contribution guidance", user_prompt)
        self.assertIn("Do NOT prescribe unverified code patches", user_prompt)

    @patch("knowledge_agent.retriever.ContextRetriever.discover_context")
    @patch("knowledge_agent.agent.KnowledgeAgent.call_llm")
    def test_agent_contribution_guidance_outputs_investigation_pathway(self, mock_call_llm, mock_discover):
        """Hermetically verifies generate_answer produces a structured investigation pathway
        with entry point, dynamics, and test commands (Issue #59)."""
        mock_discover.return_value = {
            "intent": IntentCategory.CONTRIBUTION_GUIDANCE,
            "owner": "testorg",
            "repo": "testrepo",
            "issue": {"number": 42, "title": "Prompt formatting bug", "body": "See prompt.py"},
            "fetched_files": {
                "knowledge_agent/prompt.py": "code",
                "tests/test_prompt.py": "tests",
                "pyproject.toml": "[tool.pytest]"
            },
            "test_files": ["tests/test_prompt.py"],
            "commit_sha": "abc1234"
        }

        investigation_answer = (
            "Here is the investigation pathway for Issue #42:\n\n"
            "1. **Starting Point & Reproduction**: Start with `knowledge_agent/prompt.py`. This is where `ContextExplainer.build_system_prompt` formats prompt rules.\n"
            "2. **State & Subsystem Dynamics**: Next, trace how `KnowledgeAgent.generate_answer` consumes the synthesized prompt and delegates to the provider router.\n"
            "3. **Test Suite & Verification Commands**: Run `pytest tests/test_prompt.py` locally to reproduce current behavior and verify adjustments.\n\n"
            "Align final interface changes with maintainers before opening a PR."
        )
        mock_call_llm.return_value = investigation_answer

        res = KnowledgeAgent.generate_answer(
            token="ghp_test",
            owner="testorg",
            repo="testrepo",
            query="@Knowledge Where should I start to solve Issue #42?",
            author="NewContributor"
        )

        self.assertEqual(res["intent"], IntentCategory.CONTRIBUTION_GUIDANCE)
        self.assertIn("Starting Point & Reproduction", res["answer"])
        self.assertIn("knowledge_agent/prompt.py", res["answer"])
        self.assertIn("State & Subsystem Dynamics", res["answer"])
        self.assertIn("Test Suite & Verification Commands", res["answer"])
        self.assertIn("pytest tests/test_prompt.py", res["answer"])


if __name__ == "__main__":
    unittest.main()
