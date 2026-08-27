# Adaptive Technicality Point System & Multi-Repository Intelligence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement an internal 1–10 adaptive depth/technicality point system and multi-repository cross-context intelligence for Knowledge Agent, enabling the bot to calibrate explanation depth dynamically and investigate connected repositories.

**Architecture:** 
1. `AdaptiveDepthEngine`: A deterministic heuristic + keyword analyzer that scores user context from 1 to 10 (base 5) based on query vocabulary, intent cues, and conversational history, silently injecting technicality constraints into `ContextExplainer` without exposing point numbers to end users.
2. `MultiRepoRetriever`: Extends `ContextRetriever` to parse related repository declarations from `KNOWLEDGE.md` or `.knowledge/repos.json` / env vars, allowing cross-repo tree discovery and file fetching across frontend, backend, and shared companion repos with multi-repo citation formatting (`owner/repo@sha:file#L1-L10`).

**Tech Stack:** Python 3.10+, `httpx`, `pytest` / `unittest`, standard library (`re`, `json`, `pathlib`, `typing`, `os`).

**Spec:** Prithvi's roadmap enhancement notes:
- Feature A: Internal Point System (Base 5, scale 1-10, adjusts -1/-2 for simplification requests, +1/+3 for deep code/architecture inquiries; strictly internal).
- Feature B: Multi-Repository Intelligence (Cross-repo file tracing, e.g., linking `layout.tsx` in a frontend repo to a FastAPI router endpoint in the backend repo).

---

## Global Constraints

- Zero new heavy dependencies — pure Python stdlib + existing `httpx`.
- Strictly internal point system: point values, calibrations, or scores MUST NEVER leak into user-facing comments, summaries, or citations.
- Backward compatibility: single-repo workflows behave identically; default depth remains balanced (score 5).
- Follow the Ponytail ladder: reuse existing `RelationshipExtractor`, `ContextRetriever`, and `CitationFormatter` before creating new abstractions.
- All tests must run offline with hermetic fixtures and mocks.

---

### Task 1: Adaptive Depth & Technicality Point Engine

**Files:**
- Create: `adaptive_depth.py`
- Test: `tests/test_adaptive_depth.py`

**Interfaces:**
- Consumes: `query: str`, `history_comments: Optional[List[Dict[str, Any]]]`, `base_score: int = 5`
- Produces: `AdaptiveDepthEngine.calculate_depth(query: str, history: Optional[List[str]] = None) -> int`, `AdaptiveDepthEngine.get_prompt_guidance(depth: int) -> str`

- [ ] **Step 1: Write the failing unit tests for Adaptive Depth Engine**

```python
# tests/test_adaptive_depth.py
import unittest
from adaptive_depth import AdaptiveDepthEngine, DepthLevel

class TestAdaptiveDepthEngine(unittest.TestCase):
    def setUp(self):
        self.engine = AdaptiveDepthEngine()

    def test_default_base_score(self):
        score = self.engine.calculate_depth("How do I run this project?")
        self.assertEqual(score, 5)

    def test_simplification_cues_decrease_score(self):
        queries = [
            "@knowledge can you explain me this more clearly",
            "can you explain this in simpler terms?",
            "ELI5 how auth works here, I am confused",
            "break it down step by step for a beginner"
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

    def test_score_bounds_clamp_between_1_and_10(self):
        deep_query = "FastAPI endpoint database async connection pool ORM schema SQL transaction isolation level AST bytecode internals"
        score = self.engine.calculate_depth(deep_query)
        self.assertLessEqual(score, 10)
        self.assertGreaterEqual(score, 7)

        simple_query = "explain clearly simply beginner basic ELI5 spoon feed me confused"
        score_simple = self.engine.calculate_depth(simple_query)
        self.assertGreaterEqual(score_simple, 1)
        self.assertLessEqual(score_simple, 4)

    def test_prompt_guidance_generation(self):
        guidance_low = self.engine.get_prompt_guidance(3)
        self.assertIn("conceptual", guidance_low.lower())
        self.assertNotIn("3/10", guidance_low)  # strictly no leaking of points

        guidance_high = self.engine.get_prompt_guidance(8)
        self.assertIn("technical", guidance_high.lower())
        self.assertNotIn("8/10", guidance_high)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests/test_adaptive_depth.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'adaptive_depth'`

- [ ] **Step 3: Implement `adaptive_depth.py`**

```python
# adaptive_depth.py
"""
Adaptive Depth Engine (adaptive_depth.py)
Internal technicality calibration system for Knowledge Agent.
Calibrates depth (1-10) without leaking point values into user-facing output.
"""

from __future__ import annotations
import re
from typing import List, Optional, Dict, Any

class DepthLevel:
    MIN_SCORE = 1
    MAX_SCORE = 10
    DEFAULT_BASE = 5

class AdaptiveDepthEngine:
    """Calculates internal technicality level based on vocabulary and conversational flow."""

    SIMPLIFICATION_PATTERNS = [
        r"\b(?:explain\s+(?:me\s+)?(?:this\s+)?more\s+clearly|simpler|simple\s+terms|in\s+plain\s+english)\b",
        r"\b(?:eli5|for\s+beginners?|beginner-friendly|spoon\s*feed|too\s+complex|confused|break\s+it\s+down)\b",
        r"\b(?:what\s+does\s+this\s+mean|i\s+don'?t\s+understand|basic\s+explanation)\b",
    ]

    MODERATE_TECHNICAL_PATTERNS = [
        r"\b(?:more\s+technical(?:\s+terms)?|in-depth|detailed\s+architecture|under\s+the\s+hood|internals?)\b",
        r"\b(?:data\s+flow|lifecycle|contract|interface|subsystem|middleware|pipeline)\b",
    ]

    DEEP_TECHNICAL_PATTERNS = [
        r"\b(?:http\s+endpoint|api\s+route|database\s+connection|orm|schema|sql|migration)\b",
        r"\b(?:asyncio|thread\s*pool|concurrency|mutex|deadlock|race\s+condition|ast|bytecode)\b",
        r"\b(?:fastapi|express|django|postgres|sqlite|redis|grpc|protobuf|webhook\s+payload)\b",
    ]

    def calculate_depth(self, query: str, history: Optional[List[str]] = None) -> int:
        if not query:
            return DepthLevel.DEFAULT_BASE

        score = DepthLevel.DEFAULT_BASE
        q_lower = query.lower()

        # Check simplification cues (-1 to -2)
        for pat in self.SIMPLIFICATION_PATTERNS:
            if re.search(pat, q_lower):
                score -= 1
                if "spoon feed" in q_lower or "eli5" in q_lower or "more clearly" in q_lower:
                    score -= 1
                break

        # Check moderate technical cues (+1)
        for pat in self.MODERATE_TECHNICAL_PATTERNS:
            if re.search(pat, q_lower):
                score += 1
                break

        # Check deep technical cues (+1 to +3)
        deep_matches = 0
        for pat in self.DEEP_TECHNICAL_PATTERNS:
            if re.search(pat, q_lower):
                deep_matches += 1

        if deep_matches >= 2:
            score += 3
        elif deep_matches == 1:
            score += 2

        # Check history cues if available
        if history:
            for past in history[-3:]:
                p_lower = past.lower()
                if "more technical" in p_lower:
                    score += 1
                elif "more clearly" in p_lower or "simpler" in p_lower:
                    score -= 1

        # Clamp between MIN_SCORE and MAX_SCORE
        return max(DepthLevel.MIN_SCORE, min(DepthLevel.MAX_SCORE, score))

    def get_prompt_guidance(self, depth: int) -> str:
        """Translates numerical depth to internal LLM instructions without disclosing numbers."""
        if depth <= 3:
            return (
                "ADAPTIVE EXPLANATION DEPTH: HIGH ACCESSIBILITY\n"
                "- Keep explanations conceptual, intuitive, and focused on the big picture.\n"
                "- Avoid dense jargon or raw bytecode/protocol traces.\n"
                "- Use clear analogies and walk through steps incrementally before showing code."
            )
        elif depth >= 7:
            return (
                "ADAPTIVE EXPLANATION DEPTH: DEEP TECHNICAL IMPLEMENTATION\n"
                "- Provide direct, concrete, low-level technical specifics.\n"
                "- Trace exact function signatures, HTTP routes/methods, schema fields, and execution flow.\n"
                "- Detail underlying data structures, state transitions, and error edge cases without high-level filler."
            )
        else:
            return (
                "ADAPTIVE EXPLANATION DEPTH: BALANCED ENGINEERING KT\n"
                "- Provide direct, senior-engineer level context with clear evidence links.\n"
                "- Balance architectural rationale with specific file and component references."
            )
```

- [ ] **Step 4: Run unit tests to verify they pass**

Run: `python -m unittest tests/test_adaptive_depth.py`
Expected: PASS (all tests pass).

- [ ] **Step 5: Commit**

```bash
git add adaptive_depth.py tests/test_adaptive_depth.py
git commit -m "feat(engine): add internal adaptive technicality depth engine"
```

---

### Task 2: Integrate Adaptive Depth Engine into `ContextExplainer` & `KnowledgeAgent`

**Files:**
- Modify: `knowledge_engine.py`
- Test: `tests/test_context_depth_integration.py`

**Interfaces:**
- Consumes: `adaptive_depth.AdaptiveDepthEngine`
- Produces: `ContextExplainer.build_system_prompt(..., depth_score: Optional[int] = None)`, `KnowledgeAgent.generate_answer(..., depth_score: Optional[int] = None)`

- [ ] **Step 1: Write integration tests for depth-guided prompt construction**

```python
# tests/test_context_depth_integration.py
import unittest
from unittest.mock import patch, MagicMock
from knowledge_engine import ContextExplainer, KnowledgeAgent, IntentCategory
import adaptive_depth

class TestContextDepthIntegration(unittest.TestCase):
    def test_explainer_injects_depth_guidance(self):
        prompt_deep = ContextExplainer.build_system_prompt(
            intent=IntentCategory.ARCHITECTURE_UNDERSTANDING,
            knowledge_rules=None,
            author="testuser",
            depth_score=8
        )
        self.assertIn("DEEP TECHNICAL IMPLEMENTATION", prompt_deep)
        self.assertNotIn("8/10", prompt_deep)

        prompt_simple = ContextExplainer.build_system_prompt(
            intent=IntentCategory.ARCHITECTURE_UNDERSTANDING,
            knowledge_rules=None,
            author="testuser",
            depth_score=3
        )
        self.assertIn("HIGH ACCESSIBILITY", prompt_simple)

    @patch("knowledge_engine.ContextRetriever.discover_context")
    @patch("knowledge_engine.KnowledgeAgent.call_llm")
    def test_agent_calculates_depth_from_query(self, mock_call_llm, mock_discover):
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
            query="@knowledge layout.tsx is connected with which HTTP endpoint in backend repo?"
        )
        self.assertIn("answer", res)
        # Verify call_llm received system prompt with deep technical guidance
        system_prompt_arg = mock_call_llm.call_args[0][0]
        self.assertIn("DEEP TECHNICAL IMPLEMENTATION", system_prompt_arg)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests/test_context_depth_integration.py`
Expected: FAIL due to missing parameter or unintegrated depth.

- [ ] **Step 3: Modify `knowledge_engine.py` to wire `AdaptiveDepthEngine`**

In `knowledge_engine.py`:
1. Import `from adaptive_depth import AdaptiveDepthEngine`.
2. Update `ContextExplainer.build_system_prompt` signature to accept `depth_score: Optional[int] = None`.
3. If `depth_score` is provided (or computed), append `AdaptiveDepthEngine().get_prompt_guidance(depth_score)` to the system prompt.
4. Update `KnowledgeAgent.generate_answer` to compute `depth_score = AdaptiveDepthEngine().calculate_depth(query)` and pass it into `ContextExplainer.build_system_prompt`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests/test_context_depth_integration.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add knowledge_engine.py tests/test_context_depth_integration.py
git commit -m "feat(agent): wire adaptive depth engine into system prompt synthesis"
```

---

### Task 3: Multi-Repository Declaration & Manifest Parser

**Files:**
- Create: `multi_repo.py`
- Test: `tests/test_multi_repo.py`

**Interfaces:**
- Consumes: `knowledge_rules: Optional[str]`, `env_vars: Dict[str, str]`
- Produces: `MultiRepoConfig.parse_related_repositories(owner: str, repo: str, knowledge_content: Optional[str] = None) -> List[Dict[str, str]]`

- [ ] **Step 1: Write unit tests for multi-repo configuration parsing**

```python
# tests/test_multi_repo.py
import unittest
import os
from multi_repo import MultiRepoConfig

class TestMultiRepoConfig(unittest.TestCase):
    def test_parse_from_knowledge_md_frontmatter_or_section(self):
        content = """
# Repository Guidelines

## Related Repositories
- `acme/backend-api`: Core FastAPI backend and database services
- `acme/shared-ui`: Shared design system components
"""
        related = MultiRepoConfig.parse_related_repositories("acme", "frontend-web", content)
        self.assertEqual(len(related), 2)
        self.assertEqual(related[0]["owner"], "acme")
        self.assertEqual(related[0]["repo"], "backend-api")
        self.assertEqual(related[1]["repo"], "shared-ui")

    def test_parse_from_env_var(self):
        os.environ["KNOWLEDGE_RELATED_REPOS"] = "acme/auth-service, acme/billing-api"
        try:
            related = MultiRepoConfig.parse_related_repositories("acme", "frontend-web", None)
            self.assertEqual(len(related), 2)
            self.assertEqual(related[0]["repo"], "auth-service")
            self.assertEqual(related[1]["repo"], "billing-api")
        finally:
            del os.environ["KNOWLEDGE_RELATED_REPOS"]

    def test_cross_repo_query_detection(self):
        self.assertTrue(MultiRepoConfig.is_cross_repo_query("layout.tsx is connected with which HTTP endpoint in backend repo?"))
        self.assertTrue(MultiRepoConfig.is_cross_repo_query("Which repositories are involved in this feature?"))
        self.assertFalse(MultiRepoConfig.is_cross_repo_query("How does auth work in this repo?"))

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests/test_multi_repo.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'multi_repo'`

- [ ] **Step 3: Implement `multi_repo.py`**

```python
# multi_repo.py
"""
Multi-Repository Intelligence Configuration & Target Resolver (multi_repo.py)
Enables cross-repository knowledge discovery across frontend, backend, and companion services.
"""

from __future__ import annotations
import os
import re
from typing import List, Dict, Optional, Any

class MultiRepoConfig:
    CROSS_REPO_KEYWORDS = [
        r"\b(?:backend(?:\s+repo)?|frontend(?:\s+repo)?|other\s+repo|cross-repo|multi-repo)\b",
        r"\b(?:which\s+repos(?:itories)?\s+are\s+involved|in\s+backend\s+repo|in\s+frontend\s+repo)\b",
        r"\b(?:api\s+repo|service\s+repo|microservice|companion\s+repo)\b",
        r"\b(?:connected\s+with\s+which\s+(?:http\s+)?endpoint\s+in)\b",
    ]

    @staticmethod
    def is_cross_repo_query(query: str) -> bool:
        if not query:
            return False
        q_lower = query.lower()
        return any(bool(re.search(pat, q_lower)) for pat in MultiRepoConfig.CROSS_REPO_KEYWORDS)

    @staticmethod
    def parse_related_repositories(
        current_owner: str,
        current_repo: str,
        knowledge_content: Optional[str] = None
    ) -> List[Dict[str, str]]:
        repos: List[Dict[str, str]] = []
        seen = set()

        # 1. Parse from environment variable KNOWLEDGE_RELATED_REPOS
        env_repos = os.getenv("KNOWLEDGE_RELATED_REPOS", "")
        if env_repos:
            for item in env_repos.split(","):
                item = item.strip()
                if not item:
                    continue
                if "/" in item:
                    parts = item.split("/", 1)
                    owner, repo = parts[0].strip(), parts[1].strip()
                else:
                    owner, repo = current_owner, item
                key = f"{owner}/{repo}".lower()
                if key != f"{current_owner}/{current_repo}".lower() and key not in seen:
                    seen.add(key)
                    repos.append({"owner": owner, "repo": repo, "description": ""})

        # 2. Parse from KNOWLEDGE.md if present
        if knowledge_content:
            matches = re.findall(r"[-*]\s*`?([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)`?(?:\s*:\s*(.*))?", knowledge_content)
            for full_name, desc in matches:
                parts = full_name.split("/", 1)
                owner, repo = parts[0].strip(), parts[1].strip()
                key = f"{owner}/{repo}".lower()
                if key != f"{current_owner}/{current_repo}".lower() and key not in seen:
                    seen.add(key)
                    repos.append({"owner": owner, "repo": repo, "description": desc.strip() if desc else ""})

        return repos
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests/test_multi_repo.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add multi_repo.py tests/test_multi_repo.py
git commit -m "feat(multi-repo): add related repositories parser and cross-repo query detector"
```

---

### Task 4: Multi-Repository Context Retrieval & Cross-Repo Citations

**Files:**
- Modify: `knowledge_engine.py`
- Test: `tests/test_multi_repo_retriever.py`

**Interfaces:**
- Consumes: `MultiRepoConfig`, `GitHubClient`
- Produces: `ContextRetriever.discover_context(...)` populated with `cross_repo_evidence: Dict[str, Any]` and multi-repo file citations in `CitationFormatter`.

- [ ] **Step 1: Write integration tests for cross-repo context retrieval and citations**

```python
# tests/test_multi_repo_retriever.py
import unittest
from unittest.mock import patch, MagicMock
from knowledge_engine import ContextRetriever, CitationFormatter, IntentCategory
from multi_repo import MultiRepoConfig

class TestMultiRepoRetriever(unittest.TestCase):
    @patch("knowledge_engine.GitHubClient.fetch_repo_tree")
    @patch("knowledge_engine.GitHubClient.fetch_file_content")
    @patch("knowledge_engine.GitHubClient.fetch_commit_sha")
    def test_cross_repo_retrieval_for_endpoint_queries(self, mock_sha, mock_fetch_file, mock_tree):
        mock_sha.return_value = "main123"
        mock_tree.return_value = [
            "backend/app/main.py",
            "backend/app/routers/users.py",
            "backend/app/db.py"
        ]
        mock_fetch_file.side_effect = lambda token, o, r, path, ref=None: (
            "@app.get('/api/v1/layout')\ndef get_layout(): return {'status': 'ok'}" if "main.py" in path else None
        )

        with patch.object(MultiRepoConfig, "parse_related_repositories", return_value=[{"owner": "acme", "repo": "backend-api", "description": "Backend service"}]):
            evidence = ContextRetriever.discover_context(
                token="ghp_test",
                owner="acme",
                repo="frontend-web",
                query="@knowledge layout.tsx is connected with which HTTP endpoint in backend repo?",
                intent_info={"intent": IntentCategory.FEATURE_UNDERSTANDING, "keywords": ["endpoint", "backend"]}
            )

            self.assertIn("cross_repo_evidence", evidence)
            self.assertIn("acme/backend-api", evidence["cross_repo_evidence"])
            self.assertIn("backend/app/main.py", evidence["cross_repo_evidence"]["acme/backend-api"]["fetched_files"])

    def test_multi_repo_citation_formatting(self):
        citations = CitationFormatter.build_citations_section(
            owner="acme",
            repo="frontend-web",
            commit_sha="abc1234",
            files_read=["src/layout.tsx"],
            cross_repo_files={"acme/backend-api": {"sha": "def5678", "files": ["app/main.py"]}}
        )
        self.assertIn("frontend-web", citations)
        self.assertIn("acme/backend-api", citations)
        self.assertIn("app/main.py", citations)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests/test_multi_repo_retriever.py`
Expected: FAIL due to missing cross-repo arguments in `discover_context` / `CitationFormatter`.

- [ ] **Step 3: Modify `knowledge_engine.py`**

In `knowledge_engine.py`:
1. Integrate `MultiRepoConfig` inside `ContextRetriever.discover_context`.
2. When `MultiRepoConfig.is_cross_repo_query(query)` is true and related repos exist in config or `KNOWLEDGE.md`, discover trees and candidate files from related repos and populate `evidence["cross_repo_evidence"]`.
3. Update `CitationFormatter.build_citations_section` to support optional `cross_repo_files: Optional[Dict[str, Dict[str, Any]]] = None` and render structured markdown links for all participating repos.
4. Update `ContextExplainer.build_user_prompt` to include `--- CROSS-REPOSITORY EVIDENCE ---` sections when present.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests/test_multi_repo_retriever.py`
Expected: PASS.

- [ ] **Step 5: Run full test suite**

Run: `python -m unittest discover -s tests -p "test_*.py"`
Expected: PASS with 114+ tests passing.

- [ ] **Step 6: Commit**

```bash
git add knowledge_engine.py tests/test_multi_repo_retriever.py
git commit -m "feat(multi-repo): implement cross-repository context discovery and multi-repo citations"
```

---

### Task 5: End-to-End Verification, Documentation & PR Preparation

**Files:**
- Modify: `KNOWLEDGE.md` (add Multi-Repo and Adaptive Technicality guidelines)
- Modify: `Roadmap.md` (update status for Cross-Repository Intelligence)
- Modify: `README.md` (document multi-repo config and adaptive depth engine)

- [ ] **Step 1: Update `KNOWLEDGE.md` and `Roadmap.md`**

Add clear documentation on:
1. Internal Adaptive Technicality depth handling.
2. Cross-Repository Intelligence configuration and querying.
3. Update Roadmap status.

- [ ] **Step 2: Run all tests**

Run: `python -m unittest discover -s tests -p "test_*.py"`
Expected: PASS.

- [ ] **Step 3: Commit and push**

```bash
git add KNOWLEDGE.md Roadmap.md README.md
git commit -m "docs: document adaptive point system and multi-repository intelligence"
```
