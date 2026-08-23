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
    """Configuration and parser for cross-repository intelligence."""

    CROSS_REPO_KEYWORDS = [
        r"\b(?:backend(?:\s+repo)?|frontend(?:\s+repo)?|other\s+repo|cross-repo|multi-repo)\b",
        r"\b(?:which\s+repos(?:itories)?\s+are\s+involved|in\s+backend\s+repo|in\s+frontend\s+repo)\b",
        r"\b(?:api\s+repo|service\s+repo|microservice|companion\s+repo|companion\s+service)\b",
        r"\b(?:connected\s+with\s+which\s+(?:http\s+)?endpoint\s+in)\b",
        r"\b(?:across\s+repos|across\s+repositories|in\s+another\s+repo|in\s+the\s+other\s+repo)\b",
        r"\b(?:related\s+repo|related\s+repositories)\b",
    ]

    @staticmethod
    def is_cross_repo_query(query: Optional[str]) -> bool:
        """Detects if a user query refers to cross-repository context."""
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
        """
        Parses related repositories from environment variables and KNOWLEDGE.md.
        Deduplicates and excludes the current repository.
        Returns a list of dicts with 'owner', 'repo', and 'description'.
        """
        repos: List[Dict[str, str]] = []
        seen: Dict[str, Dict[str, str]] = {}
        current_key = f"{current_owner}/{current_repo}".lower()

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
                if key != current_key and key not in seen:
                    entry = {"owner": owner, "repo": repo, "description": ""}
                    seen[key] = entry
                    repos.append(entry)

        # 2. Parse from KNOWLEDGE.md if present
        if knowledge_content:
            # Match bullet items like:
            # - `owner/repo`: description
            # - owner/repo: description
            # - [owner/repo](url) - description
            # - `owner/repo`
            pattern = re.compile(
                r"^\s*[-*+]\s+`?\[?([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)\]?(?:\([^)]*\))?`?(?:\s*(?::| -|-|—)\s*(.*))?$",
                re.MULTILINE
            )
            for match in pattern.finditer(knowledge_content):
                full_name = match.group(1)
                desc = match.group(2) or ""
                parts = full_name.split("/", 1)
                owner, repo = parts[0].strip(), parts[1].strip()
                key = f"{owner}/{repo}".lower()
                clean_desc = desc.strip()
                clean_desc = re.sub(r"^:\s*", "", clean_desc).strip()
                if key != current_key:
                    if key not in seen:
                        entry = {"owner": owner, "repo": repo, "description": clean_desc}
                        seen[key] = entry
                        repos.append(entry)
                    elif clean_desc and not seen[key]["description"]:
                        seen[key]["description"] = clean_desc

        return repos
