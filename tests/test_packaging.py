"""Packaging, distribution, and root shim compatibility tests (#51)."""

import ast
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestPackagingAndShims(unittest.TestCase):
    """Verifies package integrity, version alignment, and backward compatibility shims."""

    def test_root_shims_reexport_identical_objects(self):
        """Root shims must re-export identical objects as the canonical package."""
        import adaptive_depth
        import knowledge_agent.adaptive_depth
        import knowledge_agent.memory_store
        import knowledge_agent.multi_repo
        import knowledge_agent.providers
        import knowledge_agent.retry
        import memory_store
        import multi_repo
        import providers
        import retry

        self.assertIs(
            providers.get_provider,
            knowledge_agent.providers.get_provider,
        )
        self.assertIs(
            providers.PROVIDER_REGISTRY,
            knowledge_agent.providers.PROVIDER_REGISTRY,
        )
        self.assertIs(
            providers.list_providers,
            knowledge_agent.providers.list_providers,
        )
        self.assertIs(
            retry.request_with_retry,
            knowledge_agent.retry.request_with_retry,
        )
        self.assertIs(
            memory_store.MemoryStore,
            knowledge_agent.memory_store.MemoryStore,
        )
        self.assertIs(
            memory_store.topic_key,
            knowledge_agent.memory_store.topic_key,
        )
        self.assertIs(
            adaptive_depth.AdaptiveDepthEngine,
            knowledge_agent.adaptive_depth.AdaptiveDepthEngine,
        )
        self.assertIs(
            adaptive_depth.DepthLevel,
            knowledge_agent.adaptive_depth.DepthLevel,
        )
        self.assertIs(
            multi_repo.MultiRepoConfig,
            knowledge_agent.multi_repo.MultiRepoConfig,
        )

    def test_version_matches_pyproject(self):
        """knowledge_agent.__version__ must match version declared in pyproject.toml."""
        import knowledge_agent

        pyproject_path = REPO_ROOT / "pyproject.toml"
        self.assertTrue(pyproject_path.is_file(), "pyproject.toml not found")

        content = pyproject_path.read_text(encoding="utf-8")
        match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', content)
        self.assertIsNotNone(match, "version field not found in pyproject.toml")
        pyproject_version = match.group(1)

        self.assertEqual(knowledge_agent.__version__, pyproject_version)
        self.assertEqual(knowledge_agent.__version__, "0.3.1")

    def test_knowledge_engine_exports_get_max_diff_budget(self):
        """knowledge_engine.__all__ must export get_max_diff_budget."""
        import knowledge_engine

        self.assertIn("get_max_diff_budget", knowledge_engine.__all__)
        self.assertTrue(callable(knowledge_engine.get_max_diff_budget))

    def test_no_bare_imports_of_moved_modules_inside_package(self):
        """No module inside knowledge_agent/ may import moved root modules by bare name."""
        pkg_dir = REPO_ROOT / "knowledge_agent"
        moved_modules = {
            "providers",
            "retry",
            "memory_store",
            "adaptive_depth",
            "multi_repo",
        }

        violations = []
        for py_file in pkg_dir.glob("*.py"):
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in moved_modules:
                            violations.append(
                                f"{py_file.name}:{node.lineno} bare import '{alias.name}'"
                            )
                elif isinstance(node, ast.ImportFrom):
                    # level == 0 means absolute/bare import (e.g. `import providers` or `from providers import ...`)
                    if node.level == 0 and node.module in moved_modules:
                        violations.append(
                            f"{py_file.name}:{node.lineno} bare 'from {node.module} import ...'"
                        )

        self.assertEqual(
            violations,
            [],
            f"Found bare imports of moved modules inside knowledge_agent/: {violations}",
        )

    def test_isolated_package_import(self):
        """knowledge_agent must be importable in isolation without root flat files on sys.path."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            pkg_src = REPO_ROOT / "knowledge_agent"
            pkg_dst = Path(tmp_dir) / "knowledge_agent"
            shutil.copytree(pkg_src, pkg_dst)

            # Subprocess runs outside the source tree with PYTHONPATH pointing ONLY to tmp_dir
            env = os.environ.copy()
            env["PYTHONPATH"] = tmp_dir

            test_script = (
                "import knowledge_agent\n"
                "from knowledge_agent import __version__, KnowledgeAgent, is_bot_triggered\n"
                "assert __version__ == '0.3.1'\n"
                "print('OK')\n"
            )

            result = subprocess.run(
                [sys.executable, "-c", test_script],
                cwd=tmp_dir,
                env=env,
                capture_output=True,
                text=True,
            )

            self.assertEqual(
                result.returncode,
                0,
                f"Isolated import failed with stderr: {result.stderr}",
            )
            self.assertEqual(result.stdout.strip(), "OK")

    def test_reexports(self):
        import knowledge_agent
        import knowledge_engine

        for attr in [
            "GitHubClient",
            "IntentClassifier",
            "IntentCategory",
            "RelationshipExtractor",
            "ContextRetriever",
            "truncate_diff_hunk_aware",
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
