import os
import unittest
from unittest.mock import patch
from knowledge_agent.retriever import truncate_diff_hunk_aware, compress_hunk_lines, ContextRetriever
from knowledge_agent.intent import IntentCategory
from knowledge_agent.config import get_max_diff_budget


class TestHunkAwareDiffTruncation(unittest.TestCase):
    def test_compress_hunk_lines_short_unchanged(self):
        lines = [
            " context 1",
            " context 2",
            "-old_line",
            "+new_line",
            " context 3"
        ]
        compressed = compress_hunk_lines(lines)
        self.assertEqual(compressed, lines)

    def test_compress_hunk_lines_long_unchanged(self):
        lines = (
            [" context start 1", " context start 2"]
            + [f" unchanged line {i}" for i in range(10)]
            + [" context end 1", "+added line"]
        )
        compressed = compress_hunk_lines(lines)
        compressed_text = "\n".join(compressed)
        self.assertIn("context start 1", compressed_text)
        self.assertIn("unchanged lines omitted", compressed_text)
        self.assertIn("+added line", compressed_text)
        self.assertLess(len(compressed), len(lines))

    def test_truncate_diff_preserves_headers_and_functions(self):
        sample_diff = (
            "diff --git a/core/engine.py b/core/engine.py\n"
            "index 1234567..89abcdef 100644\n"
            "--- a/core/engine.py\n"
            "+++ b/core/engine.py\n"
            "@@ -10,30 +10,32 @@ def run_pipeline(context, options):\n"
            + "\n".join([f" unchanged line {i}" for i in range(25)]) + "\n"
            "-    old_call()\n"
            "+    new_call()\n"
            "     return True\n"
        )
        result = truncate_diff_hunk_aware(sample_diff, max_budget=14000)
        self.assertIsNotNone(result)
        self.assertIn("diff --git a/core/engine.py b/core/engine.py", result)
        self.assertIn("--- a/core/engine.py", result)
        self.assertIn("+++ b/core/engine.py", result)
        self.assertIn("def run_pipeline(context, options):", result)
        self.assertIn("+    new_call()", result)
        self.assertIn("unchanged lines omitted", result)

    def test_truncate_diff_multi_file_budget_enforcement(self):
        # Generate a large diff spanning multiple files (> 20,000 characters)
        file_diffs = []
        for i in range(10):
            fdiff = (
                f"diff --git a/pkg/module_{i}.py b/pkg/module_{i}.py\n"
                f"--- a/pkg/module_{i}.py\n"
                f"+++ b/pkg/module_{i}.py\n"
                f"@@ -1,50 +1,55 @@ def process_item_{i}():\n"
                + "\n".join([f"     long line of context code in module {i} line {j} = {j * 10}" for j in range(40)]) + "\n"
                f"+    # addition in module {i}\n"
            )
            file_diffs.append(fdiff)
        large_diff = "\n".join(file_diffs)
        self.assertGreater(len(large_diff), 20000)

        budget = 1200
        truncated = truncate_diff_hunk_aware(large_diff, max_budget=budget)
        self.assertIsNotNone(truncated)
        self.assertLessEqual(len(truncated), budget)
        self.assertIn("diff --git a/pkg/module_0.py", truncated)
        self.assertIn("diff truncated", truncated)

    def test_truncate_diff_plain_text_fallback(self):
        plain = "A" * 500
        res = truncate_diff_hunk_aware(plain, max_budget=50)
        self.assertEqual(len(res), 50)
        self.assertEqual(res, "A" * 50)

    def test_truncate_diff_none_and_empty(self):
        self.assertIsNone(truncate_diff_hunk_aware(None))
        self.assertEqual(truncate_diff_hunk_aware(""), "")
        self.assertEqual(truncate_diff_hunk_aware("hello", max_budget=0), "")

    def test_config_max_diff_budget_env_resolution(self):
        with patch.dict(os.environ, {"KNOWLEDGE_MAX_DIFF_BUDGET": "8500"}):
            self.assertEqual(get_max_diff_budget(), 8500)

        with patch.dict(os.environ, {"KNOWLEDGE_MAX_DIFF_CHARS": "4200"}, clear=True):
            self.assertEqual(get_max_diff_budget(), 4200)

        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(get_max_diff_budget(), 14000)


if __name__ == "__main__":
    unittest.main()
