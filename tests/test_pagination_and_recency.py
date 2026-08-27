"""Tests for #27: comment/issue-list fetchers used to stop at page 1
(oldest-first, GitHub's default), and build_user_prompt sliced with [:5],
taking the *oldest* five comments instead of the most recent five. Long
threads silently lost whatever was actually being discussed."""

import unittest
from unittest.mock import MagicMock, patch

import httpx

from knowledge_engine import GitHubClient, ContextExplainer, IntentCategory


def _page_response(items, status_code=200):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = items
    return resp


def _comment(n):
    return {"id": n, "user": {"login": "dev"}, "body": f"comment {n}"}


class TestPagination(unittest.TestCase):

    @patch.object(httpx.Client, "get")
    def test_fetch_issue_comments_walks_multiple_pages(self, mock_get):
        page1 = [_comment(i) for i in range(100)]
        page2 = [_comment(i) for i in range(100, 150)]  # under per_page: last page
        mock_get.side_effect = [_page_response(page1), _page_response(page2)]

        result = GitHubClient.fetch_issue_comments("token", "owner", "repo", 1)

        self.assertEqual(len(result), 150)
        self.assertEqual(mock_get.call_count, 2)

    @patch.object(httpx.Client, "get")
    def test_fetch_issue_comments_stops_at_max_pages(self, mock_get):
        full_page = [_comment(i) for i in range(100)]
        mock_get.return_value = _page_response(full_page)  # always a full page

        result = GitHubClient.fetch_issue_comments("token", "owner", "repo", 1)

        self.assertEqual(mock_get.call_count, 5)  # default max_pages
        self.assertEqual(len(result), 500)

    @patch.object(httpx.Client, "get")
    def test_fetch_issue_comments_single_page_stops_early(self, mock_get):
        mock_get.return_value = _page_response([_comment(1), _comment(2)])

        result = GitHubClient.fetch_issue_comments("token", "owner", "repo", 1)

        self.assertEqual(len(result), 2)
        mock_get.assert_called_once()

    @patch.object(httpx.Client, "get")
    def test_fetch_issue_comments_empty_thread(self, mock_get):
        mock_get.return_value = _page_response([])
        result = GitHubClient.fetch_issue_comments("token", "owner", "repo", 1)
        self.assertEqual(result, [])
        mock_get.assert_called_once()

    @patch.object(httpx.Client, "get")
    def test_fetch_repo_issues_paginates_and_filters_prs(self, mock_get):
        page1 = [{"number": i, "title": f"issue {i}"} for i in range(100)]
        page1.append({"number": 999, "title": "a PR", "pull_request": {}})
        mock_get.side_effect = [_page_response(page1), _page_response([])]

        result = GitHubClient.fetch_repo_issues("token", "owner", "repo")

        self.assertEqual(len(result), 100)
        self.assertTrue(all("pull_request" not in i for i in result))

    @patch.object(httpx.Client, "get")
    def test_fetch_pr_comments_paginates_both_endpoints(self, mock_get):
        issue_page = [_comment(i) for i in range(100)]
        mock_get.side_effect = [
            _page_response(issue_page),  # issue-comments page 1 (full)
            _page_response([]),  # issue-comments page 2 (empty, stop)
            _page_response([_comment(200)]),  # pulls-comments page 1 (partial, stop)
        ]

        result = GitHubClient.fetch_pr_comments("token", "owner", "repo", 5)

        self.assertEqual(len(result), 101)

    @patch.object(httpx.Client, "get")
    def test_pagination_stops_on_non_200(self, mock_get):
        full_page = [_comment(i) for i in range(100)]
        mock_get.side_effect = [_page_response(full_page), _page_response([], status_code=500)]

        result = GitHubClient.fetch_issue_comments("token", "owner", "repo", 1)

        self.assertEqual(len(result), 100)
        self.assertEqual(mock_get.call_count, 2)


class TestRecentCommentsInPrompt(unittest.TestCase):

    def test_issue_prompt_uses_most_recent_comments_not_oldest(self):
        comments = [{"user": {"login": "dev"}, "body": f"comment {i}"} for i in range(20)]
        evidence = {
            "intent": IntentCategory.ISSUE_UNDERSTANDING,
            "query": "q", "owner": "o", "repo": "r",
            "fetched_files": {},
            "issue": {"number": 1, "title": "T", "body": "B"},
            "comments": comments,
        }
        prompt = ContextExplainer.build_user_prompt(evidence, query_author="Dev")
        # The most recent comments (15-19) must appear; the earliest ones must not.
        for i in range(15, 20):
            self.assertIn(f"comment {i}", prompt)
        for i in range(0, 15):
            self.assertNotIn(f"comment {i}\n", prompt)

    def test_pr_discussion_uses_most_recent_comments(self):
        comments = [{"user": {"login": "dev"}, "body": f"discuss {i}"} for i in range(10)]
        evidence = {
            "intent": IntentCategory.PR_UNDERSTANDING,
            "query": "q", "owner": "o", "repo": "r",
            "fetched_files": {},
            "pr": {"number": 5, "title": "T", "body": "B"},
            "pr_comments": comments,
        }
        prompt = ContextExplainer.build_user_prompt(evidence, query_author="Dev")
        for i in range(5, 10):
            self.assertIn(f"discuss {i}", prompt)
        self.assertNotIn("discuss 0\n", prompt)

    def test_review_comments_uses_most_recent(self):
        review_comments = [
            {"path": "a.py", "line": i, "user": {"login": "dev"}, "body": f"review {i}"}
            for i in range(10)
        ]
        evidence = {
            "intent": IntentCategory.PR_UNDERSTANDING,
            "query": "q", "owner": "o", "repo": "r",
            "fetched_files": {},
            "pr": {"number": 5, "title": "T", "body": "B"},
            "review_comments": review_comments,
        }
        prompt = ContextExplainer.build_user_prompt(evidence, query_author="Dev")
        for i in range(5, 10):
            self.assertIn(f"review {i}", prompt)
        self.assertNotIn("review 0\n", prompt)

    def test_few_comments_all_included(self):
        """Sanity check: when there are fewer than 5 comments, nothing breaks."""
        comments = [{"user": {"login": "dev"}, "body": "only comment"}]
        evidence = {
            "intent": IntentCategory.ISSUE_UNDERSTANDING,
            "query": "q", "owner": "o", "repo": "r",
            "fetched_files": {},
            "issue": {"number": 1, "title": "T", "body": "B"},
            "comments": comments,
        }
        prompt = ContextExplainer.build_user_prompt(evidence, query_author="Dev")
        self.assertIn("only comment", prompt)


if __name__ == "__main__":
    unittest.main()
