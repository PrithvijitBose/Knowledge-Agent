import subprocess
import sys
import unittest
import knowledge_agent
import knowledge_engine


class TestPackagingAndImports(unittest.TestCase):
    def test_version(self):
        self.assertEqual(knowledge_agent.__version__, "0.3.0")
        self.assertEqual(knowledge_engine.__version__, "0.3.0")

    def test_reexports(self):
        for attr in [
            "GitHubClient",
            "IntentClassifier",
            "IntentCategory",
            "RelationshipExtractor",
            "ContextRetriever",
            "ContextExplainer",
            "ExecutionTracer",
            "KnowledgeAgent",
            "is_bot_triggered",
            "process_github_comment",
        ]:
            self.assertTrue(hasattr(knowledge_agent, attr), f"knowledge_agent missing {attr}")
            self.assertTrue(hasattr(knowledge_engine, attr), f"knowledge_engine missing {attr}")

    def test_python_module_cli_help(self):
        res = subprocess.run(
            [sys.executable, "-m", "knowledge_agent", "--help"],
            capture_output=True,
            text=True
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("--owner", res.stdout)
        self.assertIn("--repo", res.stdout)
        self.assertIn("--issue", res.stdout)


if __name__ == "__main__":
    unittest.main()
