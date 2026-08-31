import unittest
from unittest.mock import patch, MagicMock
import httpx

import knowledge_engine
from knowledge_engine import GitHubClient, CitationFormatter, KnowledgeAgent


class TestCitationsAndPermalinks(unittest.TestCase):

    def test_format_file_permalink_with_sha(self):
        url = CitationFormatter.format_file_permalink("owner", "repo", "a1b2c3d4e5f6", "src/auth.py")
        self.assertEqual(url, "https://github.com/owner/repo/blob/a1b2c3d4e5f6/src/auth.py")

    def test_format_file_permalink_without_sha_fallback(self):
        url = CitationFormatter.format_file_permalink("owner", "repo", None, "README.md")
        self.assertEqual(url, "https://github.com/owner/repo/blob/main/README.md")

    def test_format_file_permalink_url_encoding(self):
        url = CitationFormatter.format_file_permalink(
            "owner", "repo", "commit_sha_123", "docs/getting started guide.md"
        )
        self.assertEqual(url, "https://github.com/owner/repo/blob/commit_sha_123/docs/getting%20started%20guide.md")

        url_special = CitationFormatter.format_file_permalink(
            "owner", "repo", "sha456", "path with spaces/file#name?.py"
        )
        self.assertEqual(url_special, "https://github.com/owner/repo/blob/sha456/path%20with%20spaces/file%23name%3F.py")

    def test_format_file_permalink_line_anchors(self):
        # Single line
        url_single = CitationFormatter.format_file_permalink(
            "owner", "repo", "sha123", "src/main.py", start_line=42
        )
        self.assertEqual(url_single, "https://github.com/owner/repo/blob/sha123/src/main.py#L42")

        # Line range
        url_range = CitationFormatter.format_file_permalink(
            "owner", "repo", "sha123", "src/main.py", start_line=10, end_line=25
        )
        self.assertEqual(url_range, "https://github.com/owner/repo/blob/sha123/src/main.py#L10-L25")

        # Equal start and end line
        url_equal = CitationFormatter.format_file_permalink(
            "owner", "repo", "sha123", "src/main.py", start_line=15, end_line=15
        )
        self.assertEqual(url_equal, "https://github.com/owner/repo/blob/sha123/src/main.py#L15")

    def test_build_citations_section(self):
        files = ["b_file.py", "a_file.py", "docs/my doc.md"]
        section = CitationFormatter.build_citations_section("owner", "repo", "commit123", files)
        self.assertIn("### 📚 Referenced Files & Citations", section)
        self.assertIn("- [`a_file.py`](https://github.com/owner/repo/blob/commit123/a_file.py)", section)
        self.assertIn("- [`b_file.py`](https://github.com/owner/repo/blob/commit123/b_file.py)", section)
        self.assertIn("- [`docs/my doc.md`](https://github.com/owner/repo/blob/commit123/docs/my%20doc.md)", section)

    def test_build_citations_section_empty(self):
        section = CitationFormatter.build_citations_section("owner", "repo", "commit123", [])
        self.assertEqual(section, "")

    @patch.object(httpx.Client, "get")
    def test_fetch_latest_commit_sha(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"sha": "9f830a6c9876543210fedcba9876543210abcdef"}
        mock_get.return_value = mock_resp

        sha = GitHubClient.fetch_latest_commit_sha("token", "owner", "repo")
        self.assertEqual(sha, "9f830a6c9876543210fedcba9876543210abcdef")

    @patch("builtins.print")
    @patch.object(GitHubClient, "fetch_pull_request", return_value=None)
    @patch.object(GitHubClient, "post_issue_comment", return_value=True)
    @patch.object(KnowledgeAgent, "generate_answer")
    def test_process_comment_includes_citations(self, mock_gen, mock_post, mock_fetch_pr, mock_print):
        mock_gen.return_value = {
            "answer": "Here is the answer.",
            "citations": "\n\n### 📚 Referenced Files & Citations\n- [`auth.py`](https://github.com/owner/repo/blob/sha/auth.py)",
            "engine": "Mistral AI"
        }
        knowledge_engine.process_github_comment("token", "owner", "repo", 1, "@Knowledge explain", "Alice")
        mock_post.assert_called_once()
        _, args, _ = mock_post.mock_calls[0]
        posted_body = args[4]
        self.assertIn("Here is the answer.", posted_body)
        self.assertIn("### 📚 Referenced Files & Citations", posted_body)
        self.assertIn("https://github.com/owner/repo/blob/sha/auth.py", posted_body)


if __name__ == "__main__":
    unittest.main()
