"""Tests for memory_store.py (#6, Persistent Repository Memory)."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from memory_store import MemoryStore, topic_key


class TestTopicKey(unittest.TestCase):

    def test_same_keywords_different_order_same_key(self):
        self.assertEqual(
            topic_key("ARCHITECTURE_UNDERSTANDING", ["auth", "database"]),
            topic_key("ARCHITECTURE_UNDERSTANDING", ["database", "auth"]),
        )

    def test_case_insensitive(self):
        self.assertEqual(
            topic_key("ARCHITECTURE_UNDERSTANDING", ["Auth"]),
            topic_key("ARCHITECTURE_UNDERSTANDING", ["auth"]),
        )

    def test_different_intent_different_key(self):
        self.assertNotEqual(
            topic_key("ARCHITECTURE_UNDERSTANDING", ["auth"]),
            topic_key("ISSUE_UNDERSTANDING", ["auth"]),
        )

    def test_no_keywords_falls_back_to_general(self):
        self.assertEqual(topic_key("GENERAL_QUERY", []), "GENERAL_QUERY::general")


class TestMemoryStore(unittest.TestCase):

    def setUp(self):
        fd, self.tmp_path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.remove(self.tmp_path)  # store should handle a not-yet-existing file
        self.store = MemoryStore(path=self.tmp_path)

    def tearDown(self):
        if os.path.exists(self.tmp_path):
            os.remove(self.tmp_path)

    def test_get_on_empty_store_is_none(self):
        self.assertIsNone(self.store.get("owner", "repo", "ARCHITECTURE_UNDERSTANDING", ["auth"]))

    def test_put_then_get_round_trips(self):
        self.store.put(
            "owner", "repo", "ARCHITECTURE_UNDERSTANDING", ["auth"],
            summary="Auth flows through auth.py -> session.py.",
            files_read=["auth.py", "session.py"],
            commit_sha="abc123",
        )
        entry = self.store.get("owner", "repo", "ARCHITECTURE_UNDERSTANDING", ["auth"])
        self.assertIsNotNone(entry)
        self.assertEqual(entry["summary"], "Auth flows through auth.py -> session.py.")
        self.assertEqual(entry["files_read"], ["auth.py", "session.py"])
        self.assertEqual(entry["commit_sha"], "abc123")

    def test_different_repos_do_not_collide(self):
        self.store.put("owner", "repo-a", "ARCHITECTURE_UNDERSTANDING", ["auth"], summary="A", files_read=[], commit_sha="x")
        self.store.put("owner", "repo-b", "ARCHITECTURE_UNDERSTANDING", ["auth"], summary="B", files_read=[], commit_sha="x")
        self.assertEqual(self.store.get("owner", "repo-a", "ARCHITECTURE_UNDERSTANDING", ["auth"])["summary"], "A")
        self.assertEqual(self.store.get("owner", "repo-b", "ARCHITECTURE_UNDERSTANDING", ["auth"])["summary"], "B")

    def test_related_queries_share_the_same_entry(self):
        """'explain authentication' and 'how does auth work' both classify
        to the same (intent, keywords) -- this is the exact case the issue
        asks for: a later related question finds the earlier investigation."""
        self.store.put(
            "owner", "repo", "ARCHITECTURE_UNDERSTANDING", ["auth"],
            summary="First investigation of auth.", files_read=["auth.py"], commit_sha="x",
        )
        entry = self.store.get("owner", "repo", "ARCHITECTURE_UNDERSTANDING", ["auth"])
        self.assertEqual(entry["summary"], "First investigation of auth.")

    def test_put_overwrites_previous_entry_for_same_topic(self):
        self.store.put("owner", "repo", "ARCHITECTURE_UNDERSTANDING", ["auth"], summary="v1", files_read=[], commit_sha="x")
        self.store.put("owner", "repo", "ARCHITECTURE_UNDERSTANDING", ["auth"], summary="v2", files_read=[], commit_sha="y")
        entry = self.store.get("owner", "repo", "ARCHITECTURE_UNDERSTANDING", ["auth"])
        self.assertEqual(entry["summary"], "v2")
        self.assertEqual(entry["commit_sha"], "y")

    def test_put_empty_summary_is_a_noop(self):
        self.store.put("owner", "repo", "ARCHITECTURE_UNDERSTANDING", ["auth"], summary="", files_read=[], commit_sha="x")
        self.assertIsNone(self.store.get("owner", "repo", "ARCHITECTURE_UNDERSTANDING", ["auth"]))

    def test_summary_is_truncated(self):
        long_summary = "x" * 5000
        self.store.put("owner", "repo", "ARCHITECTURE_UNDERSTANDING", ["auth"], summary=long_summary, files_read=[], commit_sha="x")
        entry = self.store.get("owner", "repo", "ARCHITECTURE_UNDERSTANDING", ["auth"])
        self.assertLessEqual(len(entry["summary"]), 800)

    def test_corrupt_file_degrades_to_empty_not_a_crash(self):
        Path(self.tmp_path).write_text("{not valid json", encoding="utf-8")
        self.assertIsNone(self.store.get("owner", "repo", "ARCHITECTURE_UNDERSTANDING", ["auth"]))
        # And writing afterward should still work, overwriting the corrupt file.
        self.store.put("owner", "repo", "ARCHITECTURE_UNDERSTANDING", ["auth"], summary="ok", files_read=[], commit_sha="x")
        self.assertEqual(self.store.get("owner", "repo", "ARCHITECTURE_UNDERSTANDING", ["auth"])["summary"], "ok")

    def test_eviction_caps_entries_per_repo(self):
        import memory_store
        original_cap = memory_store.MAX_ENTRIES_PER_REPO
        memory_store.MAX_ENTRIES_PER_REPO = 3
        try:
            for i in range(5):
                self.store.put(
                    "owner", "repo", "ARCHITECTURE_UNDERSTANDING", [f"topic{i}"],
                    summary=f"finding {i}", files_read=[], commit_sha="x",
                )
            data = json.loads(Path(self.tmp_path).read_text(encoding="utf-8"))
            self.assertEqual(len(data["owner/repo"]), 3)
            # The most recent puts (topic2, topic3, topic4) should have survived.
            self.assertIn(topic_key("ARCHITECTURE_UNDERSTANDING", ["topic4"]), data["owner/repo"])
            self.assertNotIn(topic_key("ARCHITECTURE_UNDERSTANDING", ["topic0"]), data["owner/repo"])
        finally:
            memory_store.MAX_ENTRIES_PER_REPO = original_cap

    def test_is_stale_when_commit_sha_differs(self):
        entry = {"commit_sha": "abc123"}
        self.assertTrue(MemoryStore.is_stale(entry, "def456"))
        self.assertFalse(MemoryStore.is_stale(entry, "abc123"))

    def test_is_stale_when_either_sha_missing(self):
        self.assertTrue(MemoryStore.is_stale({"commit_sha": None}, "abc123"))
        self.assertTrue(MemoryStore.is_stale({"commit_sha": "abc123"}, None))
        self.assertTrue(MemoryStore.is_stale({}, "abc123"))

    # -- Alias canonicalization: "auth" vs "authentication" vs "oauth" -----

    def test_auth_and_authentication_share_one_slot(self):
        """The exact scenario the issue describes: two related questions
        must land in the same memory slot. IntentClassifier gives a plain
        "auth" query the keyword ["auth"], but an "authentication" query
        ["auth", "authentication"] -- both must canonicalize the same way."""
        self.store.put(
            "owner", "repo", "ARCHITECTURE_UNDERSTANDING", ["auth"],
            summary="Auth investigation.", files_read=["auth.py"], commit_sha="x",
        )
        entry = self.store.get("owner", "repo", "ARCHITECTURE_UNDERSTANDING", ["auth", "authentication"])
        self.assertIsNotNone(entry)
        self.assertEqual(entry["summary"], "Auth investigation.")

    def test_oauth_also_shares_the_auth_slot(self):
        self.store.put(
            "owner", "repo", "ARCHITECTURE_UNDERSTANDING", ["auth", "oauth"],
            summary="OAuth investigation.", files_read=[], commit_sha="x",
        )
        entry = self.store.get("owner", "repo", "ARCHITECTURE_UNDERSTANDING", ["auth"])
        self.assertIsNotNone(entry)
        self.assertEqual(entry["summary"], "OAuth investigation.")

    def test_unrelated_keywords_stay_in_separate_slots(self):
        self.store.put("owner", "repo", "ARCHITECTURE_UNDERSTANDING", ["auth"], summary="A", files_read=[], commit_sha="x")
        self.store.put("owner", "repo", "ARCHITECTURE_UNDERSTANDING", ["database"], summary="B", files_read=[], commit_sha="x")
        self.assertEqual(self.store.get("owner", "repo", "ARCHITECTURE_UNDERSTANDING", ["auth"])["summary"], "A")
        self.assertEqual(self.store.get("owner", "repo", "ARCHITECTURE_UNDERSTANDING", ["database"])["summary"], "B")

    # -- Defensive handling of a memory file with the wrong JSON shape -----

    def test_get_on_null_json_root_is_none_not_a_crash(self):
        Path(self.tmp_path).write_text("null", encoding="utf-8")
        self.assertIsNone(self.store.get("owner", "repo", "ARCHITECTURE_UNDERSTANDING", ["auth"]))

    def test_get_on_list_json_root_is_none_not_a_crash(self):
        Path(self.tmp_path).write_text("[]", encoding="utf-8")
        self.assertIsNone(self.store.get("owner", "repo", "ARCHITECTURE_UNDERSTANDING", ["auth"]))

    def test_get_on_non_dict_repo_entry_is_none_not_a_crash(self):
        Path(self.tmp_path).write_text(json.dumps({"owner/repo": []}), encoding="utf-8")
        self.assertIsNone(self.store.get("owner", "repo", "ARCHITECTURE_UNDERSTANDING", ["auth"]))

    def test_get_on_non_dict_topic_entry_is_none_not_a_crash(self):
        key = topic_key("ARCHITECTURE_UNDERSTANDING", ["auth"])
        Path(self.tmp_path).write_text(json.dumps({"owner/repo": {key: "not-a-dict"}}), encoding="utf-8")
        self.assertIsNone(self.store.get("owner", "repo", "ARCHITECTURE_UNDERSTANDING", ["auth"]))

    def test_put_recovers_from_a_wrongly_shaped_repo_entry(self):
        Path(self.tmp_path).write_text(json.dumps({"owner/repo": "not-a-dict"}), encoding="utf-8")
        self.store.put("owner", "repo", "ARCHITECTURE_UNDERSTANDING", ["auth"], summary="ok", files_read=[], commit_sha="x")
        self.assertEqual(self.store.get("owner", "repo", "ARCHITECTURE_UNDERSTANDING", ["auth"])["summary"], "ok")

    def test_eviction_skips_non_dict_entries_without_crashing(self):
        key = topic_key("ARCHITECTURE_UNDERSTANDING", ["zzz"])
        Path(self.tmp_path).write_text(json.dumps({"owner/repo": {key: "not-a-dict"}}), encoding="utf-8")
        import memory_store

        original_cap = memory_store.MAX_ENTRIES_PER_REPO
        memory_store.MAX_ENTRIES_PER_REPO = 1
        try:
            self.store.put(
                "owner", "repo", "ARCHITECTURE_UNDERSTANDING", ["fresh"],
                summary="new finding", files_read=[], commit_sha="x",
            )
        finally:
            memory_store.MAX_ENTRIES_PER_REPO = original_cap
        entry = self.store.get("owner", "repo", "ARCHITECTURE_UNDERSTANDING", ["fresh"])
        self.assertIsNotNone(entry)
        self.assertEqual(entry["summary"], "new finding")


if __name__ == "__main__":
    unittest.main()
