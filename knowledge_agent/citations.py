import urllib.parse
from typing import List, Optional


class CitationFormatter:
    """Generates clickable GitHub permalinks with commit SHAs for evidence files."""

    @staticmethod
    def format_file_permalink(
        owner: str,
        repo: str,
        commit_sha: Optional[str],
        file_path: str,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
    ) -> str:
        ref = commit_sha if commit_sha else "main"
        encoded_path = urllib.parse.quote(file_path, safe="/")
        url = f"https://github.com/{owner}/{repo}/blob/{ref}/{encoded_path}"
        if start_line is not None and end_line is not None:
            if start_line == end_line:
                url += f"#L{start_line}"
            else:
                url += f"#L{start_line}-L{end_line}"
        elif start_line is not None:
            url += f"#L{start_line}"
        return url

    @staticmethod
    def build_citations_section(owner: str, repo: str, commit_sha: Optional[str], files_read: List[str]) -> str:
        if not files_read:
            return ""
        lines = ["\n\n### 📚 Referenced Files & Citations"]
        for f in sorted(files_read):
            link = CitationFormatter.format_file_permalink(owner, repo, commit_sha, f)
            lines.append(f"- [`{f}`]({link})")
        return "\n".join(lines)
