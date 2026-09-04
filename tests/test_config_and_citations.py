import json
import os
import tempfile
import unittest
from pathlib import Path

import config
import knowledge_engine


class TestConfigAndCitations(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_load_local_config_json(self):
        cfg_file = Path(self.temp_dir.name) / ".knowledge-agent.json"
        cfg_file.write_text(json.dumps({
            "default_provider": "ollama",
            "ollama_base_url": "http://localhost:11434",
            "request_timeout": 45
        }), encoding="utf-8")

        loaded = config.load_local_config(self.temp_dir.name)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.get("default_provider"), "ollama")
        self.assertEqual(loaded.get("ollama_base_url"), "http://localhost:11434")
        self.assertEqual(loaded.get("request_timeout"), 45)

    def test_format_citations_table(self):
        citations = [
            {"file": "src/core/auth.py", "start_line": 12, "end_line": 28, "url": "https://github.com/org/repo/blob/main/src/core/auth.py#L12-L28"},
            {"file": "src/api/routes.py", "start_line": 45, "end_line": 60, "url": "https://github.com/org/repo/blob/main/src/api/routes.py#L45-L60"},
            {"file": "README.md", "start_line": 1, "end_line": 10, "url": "https://github.com/org/repo/blob/main/README.md#L1-L10"}
        ]
        table = knowledge_engine.format_citations_table(citations)
        self.assertIn("| File | Lines | Link |", table)
        self.assertIn("src/core/auth.py", table)
        self.assertIn("L12-L28", table)
        self.assertIn("https://github.com/org/repo/blob/main/src/core/auth.py#L12-L28", table)


if __name__ == '__main__':
    unittest.main()
