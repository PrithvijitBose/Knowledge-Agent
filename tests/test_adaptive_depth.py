# tests/test_adaptive_depth.py
import unittest
from adaptive_depth import AdaptiveDepthEngine, DepthLevel


class TestAdaptiveDepthEngine(unittest.TestCase):
    def setUp(self):
        self.engine = AdaptiveDepthEngine()

    def test_default_base_score(self):
        score = self.engine.calculate_depth("How do I run this project?")
        self.assertEqual(score, 5)

    def test_empty_or_none_query_returns_default(self):
        self.assertEqual(self.engine.calculate_depth(""), 5)
        self.assertEqual(self.engine.calculate_depth(None), 5)

    def test_simplification_cues_decrease_score(self):
        queries = [
            "@knowledge can you explain me this more clearly",
            "can you explain this in simpler terms?",
            "ELI5 how auth works here, I am confused",
            "break it down step by step for a beginner",
            "spoon feed me the explanation"
        ]
        for q in queries:
            score = self.engine.calculate_depth(q)
            self.assertLess(score, 5, f"Query '{q}' should have decreased score below 5, got {score}")

    def test_technical_cues_increase_score(self):
        queries = [
            "@knowledge i can understand this, can you go to more technical terms",
            "explain the AST parser and bytecode generation under the hood",
            "how is fastapi connected to the database and at what HTTP endpoint"
        ]
        for q in queries:
            score = self.engine.calculate_depth(q)
            self.assertGreater(score, 5, f"Query '{q}' should have increased score above 5, got {score}")

    def test_moderate_technical_cues(self):
        q = "Can you explain the data flow and middleware pipeline lifecycle?"
        score = self.engine.calculate_depth(q)
        self.assertGreaterEqual(score, 6)

    def test_score_bounds_clamp_between_1_and_10(self):
        deep_query = "FastAPI endpoint database async connection pool ORM schema SQL transaction isolation level AST bytecode internals"
        score = self.engine.calculate_depth(deep_query)
        self.assertLessEqual(score, DepthLevel.MAX_SCORE)
        self.assertGreaterEqual(score, 7)

        simple_query = "explain clearly simply beginner basic ELI5 spoon feed me confused in plain english"
        score_simple = self.engine.calculate_depth(simple_query)
        self.assertGreaterEqual(score_simple, DepthLevel.MIN_SCORE)
        self.assertLessEqual(score_simple, 4)

    def test_history_influences_depth(self):
        base_query = "How does routing work?"
        score_with_tech_history = self.engine.calculate_depth(
            base_query,
            history=["Can we go more technical?", "Tell me more about the architecture"]
        )
        self.assertGreater(score_with_tech_history, 5)

        score_with_simple_history = self.engine.calculate_depth(
            base_query,
            history=["Explain more clearly", "Simpler please"]
        )
        self.assertLess(score_with_simple_history, 5)

    def test_prompt_guidance_generation(self):
        # Low depth (<=3)
        guidance_low = self.engine.get_prompt_guidance(3)
        self.assertIn("conceptual", guidance_low.lower())
        self.assertIn("HIGH ACCESSIBILITY", guidance_low)
        self.assertNotIn("3/10", guidance_low)  # strictly no leaking of points
        self.assertNotIn("score", guidance_low.lower())

        # Mid depth (4-6)
        guidance_mid = self.engine.get_prompt_guidance(5)
        self.assertIn("BALANCED ENGINEERING KT", guidance_mid)
        self.assertNotIn("5/10", guidance_mid)

        # High depth (>=7)
        guidance_high = self.engine.get_prompt_guidance(8)
        self.assertIn("technical", guidance_high.lower())
        self.assertIn("DEEP TECHNICAL IMPLEMENTATION", guidance_high)
        self.assertNotIn("8/10", guidance_high)
        self.assertNotIn("score", guidance_high.lower())


if __name__ == "__main__":
    unittest.main()
