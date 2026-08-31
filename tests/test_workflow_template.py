import os
import unittest


class TestWorkflowTemplate(unittest.TestCase):
    def test_workflow_template_exists_and_valid(self):
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        template_path = os.path.join(repo_root, "templates", "knowledge.yml")
        self.assertTrue(os.path.exists(template_path), "templates/knowledge.yml must exist")

        with open(template_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Verify key triggers, guards and permissions
        self.assertIn("issue_comment:", content)
        self.assertIn("pull_request_review_comment:", content)
        self.assertIn("github-actions[bot]", content)
        self.assertIn("issues: write", content)
        self.assertIn("pull-requests: write", content)
        self.assertIn("knowledge_engine.py", content)
        self.assertIn("--owner", content)
        self.assertIn("--issue", content)
        self.assertIn("KA_COMMENT:", content)
        self.assertIn('"$KA_COMMENT"', content)


if __name__ == "__main__":
    unittest.main()
