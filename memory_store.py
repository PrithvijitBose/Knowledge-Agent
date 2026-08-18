"""Persistent repository memory (#6).

Knowledge investigates a repository from zero on every single @Knowledge
comment, even when the same topic was already investigated minutes ago in
the same thread. Issue #6 asks for exactly the example it gives: "We
already investigated authentication. Now explain authorization in
relation to it" should be able to build on the earlier finding instead of
starting over.

This is a lightweight, file-backed memory -- JSON on disk, no database.
It never replaces fresh evidence retrieval: ContextRetriever still runs
its normal investigation on every single call, unconditionally. A memory
hit is surfaced as labeled prior context the model is told to verify
against what it just found, never as an established fact it's allowed to
skip re-checking. That is what "avoid storing unsupported assumptions as
facts" (the issue's own acceptance criterion) means in practice here:
memory augments an investigation, it never substitutes for one.

Persistence across GitHub Actions runs (the runner's filesystem is thrown
away after every job) is the caller's problem, not this module's -- see
the actions/cache step added to knowledge.yml. Locally, or under a
webhook server with a persistent disk, the file just accumulates on its
own.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Explicit opt-in for the persistent location: production sets
# KNOWLEDGE_MEMORY_PATH=.knowledge/memory.json in knowledge.yml, matching the
# path actions/cache saves and restores. Without it, this defaults to a
# per-process file under the system temp dir instead of a repo-relative path
# -- so importing this module (or running the test suite, which calls
# generate_answer() without ever mocking MemoryStore) can never silently
# write a real file into a checkout, and a fresh test run never inherits
# state left behind by a previous one.
DEFAULT_MEMORY_PATH = os.getenv(
    "KNOWLEDGE_MEMORY_PATH",
    os.path.join(tempfile.gettempdir(), f"knowledge_memory_{os.getpid()}.json"),
)

# Per-repository cap on stored topics. Bounded so a very active repo's memory
# file can't grow without limit -- the oldest entries are evicted first.
MAX_ENTRIES_PER_REPO = 50

SUMMARY_MAX_CHARS = 800


def topic_key(intent: str, keywords: List[str]) -> str:
    """Groups related questions into the same memory slot.

    "Explain authentication" and "how does auth work in this repo" both
    classify to ARCHITECTURE_UNDERSTANDING with keyword "auth", so both
    hash to the same key -- a later related question can find the earlier
    investigation. Keywords are sorted and deduplicated so ordering in the
    question never matters.
    """
    normalized = "+".join(sorted(set(k.lower() for k in keywords if k))) or "general"
    return f"{intent}::{normalized}"


class MemoryStore:
    """JSON-file-backed store, one file per checkout.

    Safe to use from a fresh checkout every time: if the file doesn't
    exist yet, every lookup is just a clean miss, exactly as if memory
    never existed. Never raises -- a corrupt or unwritable memory file
    degrades to "no memory," not a broken run.
    """

    def __init__(self, path: Optional[str] = None):
        self.path = Path(path or DEFAULT_MEMORY_PATH)

    def _load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            return {}

    def _save(self, data: Dict[str, Any]) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError as e:
            print(f"MemoryStore: could not write {self.path}: {e}")

    def get(self, owner: str, repo: str, intent: str, keywords: List[str]) -> Optional[Dict[str, Any]]:
        """Returns the stored entry for this repo/topic, or None on a miss."""
        data = self._load()
        repo_entries = data.get(f"{owner}/{repo}", {})
        return repo_entries.get(topic_key(intent, keywords))

    def put(
        self,
        owner: str,
        repo: str,
        intent: str,
        keywords: List[str],
        *,
        summary: str,
        files_read: List[str],
        commit_sha: Optional[str],
    ) -> None:
        """Stores (or overwrites) the finding for this repo/topic."""
        if not summary:
            return
        data = self._load()
        repo_entries = data.setdefault(f"{owner}/{repo}", {})
        repo_entries[topic_key(intent, keywords)] = {
            "summary": summary[:SUMMARY_MAX_CHARS],
            "files_read": files_read,
            "commit_sha": commit_sha,
            "intent": intent,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        self._evict_oldest(repo_entries)
        self._save(data)

    @staticmethod
    def _evict_oldest(repo_entries: Dict[str, Any]) -> None:
        overflow = len(repo_entries) - MAX_ENTRIES_PER_REPO
        if overflow <= 0:
            return
        oldest_first = sorted(repo_entries.items(), key=lambda kv: kv[1].get("updated_at", ""))
        for stale_key, _ in oldest_first[:overflow]:
            repo_entries.pop(stale_key, None)

    @staticmethod
    def is_stale(entry: Dict[str, Any], current_commit_sha: Optional[str]) -> bool:
        """True when the codebase has moved on since this entry was stored.

        Missing commit SHAs (either side) are treated as stale -- prefer a
        false "might be stale" over confidently reusing a finding we can't
        actually verify is still current.
        """
        if not current_commit_sha or not entry.get("commit_sha"):
            return True
        return entry["commit_sha"] != current_commit_sha
