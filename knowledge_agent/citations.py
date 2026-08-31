import urllib.parse
from typing import Any, Dict, List, Optional


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
    def build_citations_section(
        owner: str,
        repo: str,
        commit_sha: Optional[str],
        files_read: List[str],
        cross_repo_files: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> str:
        sections = []
        if files_read:
            lines = ["\n\n### 📚 Referenced Files & Citations"]
            for f in sorted(files_read):
                link = CitationFormatter.format_file_permalink(owner, repo, commit_sha, f)
                lines.append(f"- [`{f}`]({link})")
            sections.append("\n".join(lines))

        if cross_repo_files:
            cross_lines = ["### 📚 Related Repository Citations"]
            has_cross = False
            for repo_key, repo_info in cross_repo_files.items():
                if "/" in repo_key:
                    rel_owner, rel_repo = repo_key.split("/", 1)
                else:
                    rel_owner, rel_repo = owner, repo_key

                rel_sha = None
                rel_files = []
                if isinstance(repo_info, dict):
                    rel_sha = repo_info.get("sha")
                    rel_files = (
                        repo_info.get("files")
                        or repo_info.get("files_read")
                        or list(repo_info.get("fetched_files", {}).keys())
                    )
                elif isinstance(repo_info, list):
                    rel_files = repo_info

                for f in sorted(rel_files):
                    has_cross = True
                    link = CitationFormatter.format_file_permalink(rel_owner, rel_repo, rel_sha, f)
                    label_sha = f"@{rel_sha[:7]}" if rel_sha else ""
                    cross_lines.append(f"- [`{rel_owner}/{rel_repo}{label_sha}:{f}`]({link})")

            if has_cross:
                sections.append("\n\n" + "\n".join(cross_lines))

        if not sections:
            return ""
        return "".join(sections)

