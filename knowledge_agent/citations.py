from typing import List, Optional


class CitationFormatter:
    """Generates clickable GitHub permalinks with commit SHAs for evidence files."""

    @staticmethod
    def format_file_permalink(owner: str, repo: str, commit_sha: Optional[str], file_path: str) -> str:
        ref = commit_sha if commit_sha else "main"
        return f"https://github.com/{owner}/{repo}/blob/{ref}/{file_path}"

    @staticmethod
    def build_citations_section(owner: str, repo: str, commit_sha: Optional[str], files_read: List[str]) -> str:
        if not files_read:
            return ""
        lines = ["\n\n### 📚 Referenced Files & Citations"]
        for f in sorted(files_read):
            link = CitationFormatter.format_file_permalink(owner, repo, commit_sha, f)
            lines.append(f"- [`{f}`]({link})")
        return "\n".join(lines)
