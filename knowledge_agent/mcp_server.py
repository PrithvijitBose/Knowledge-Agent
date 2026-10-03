"""
Model Context Protocol (MCP) Server — Engineering Context Layer (knowledge_agent/mcp_server.py)

Exposes Knowledge's bounded evidence engine, AST documentation verifier, and
issue/PR lineage to any MCP client (Claude Desktop, Cursor, Claude Code,
Windsurf, Devin) so coding agents can ground architectural answers in real
repository evidence instead of hallucinating them.

Design notes
------------
- The tool logic in `KnowledgeContextTools` is deliberately free of any `mcp`
  import so it stays hermetic and unit-testable offline. The official MCP SDK
  is imported lazily, only when a server is actually created or run.
- `mcp>=2` renamed `FastMCP` to `MCPServer`; both are supported so the module
  works across the 1.x and 2.x SDK lines.
- stdio is the default transport (Cursor / Claude Desktop spawn the process);
  SSE is available for clients that connect to a long-running HTTP endpoint.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

from knowledge_agent import __version__ as KNOWLEDGE_VERSION
from knowledge_agent.config import (
    get_max_comment_chars,
    get_max_diff_budget,
    get_max_file_chars,
)
from knowledge_agent.context_engine import ContextEngine
from knowledge_agent.doc_verifier import (
    CodeSymbolExtractor,
    DocClaimExtractor,
    DocDiscrepancyDetector,
)
from knowledge_agent.github import GitHubClient
from knowledge_agent.intent import IntentClassifier
from knowledge_agent.retriever import RelationshipExtractor


SERVER_NAME = "knowledge-agent"

SERVER_INSTRUCTIONS = """
Knowledge is an engineering context layer. Prefer these tools before guessing.

- knowledge_get_architecture_context: grounded mental model + evidence chain for a subsystem.
- knowledge_verify_doc_drift: documentation claims cross-referenced against real code symbols.
- knowledge_trace_issue_pr: bidirectional issue <-> PR lineage, directives, and touched files.

Always cite the returned evidence (file paths and line numbers). If the evidence
set is empty, say the repository does not show it instead of inventing it.
""".strip()

DEFAULT_CODE_EXTENSIONS: Tuple[str, ...] = (
    ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
)
DEFAULT_DOC_EXTENSIONS: Tuple[str, ...] = (".md", ".rst", ".txt")

SKIP_DIRECTORIES: Set[str] = {
    ".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv",
    ".env", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox", "dist",
    "build", ".next", ".idea", ".vscode", "site-packages", ".eggs",
}

MAX_FILE_BYTES = 400_000
DEFAULT_MAX_CODE_FILES = 60
DEFAULT_MAX_DOC_FILES = 15
DEFAULT_MAX_SYMBOLS = 40

STOPWORDS: Set[str] = {
    "a", "about", "an", "and", "any", "are", "as", "at", "be", "by", "can",
    "code", "does", "for", "from", "how", "i", "in", "is", "it", "of", "on",
    "or", "repo", "repository", "show", "that", "the", "this", "to", "what",
    "when", "where", "which", "who", "why", "with",
}


# ---------------------------------------------------------------------------
# SDK compatibility
# ---------------------------------------------------------------------------

MCP_IMPORT_ERROR = (
    "The official MCP SDK is not installed. Install it with `pip install \"knowledge-agent[mcp]\"` "
    "(or `pip install mcp`) to expose Knowledge's engineering context tools."
)


def _load_server_class():
    """
    Return the official MCP high-level server class for the installed SDK line.

    `mcp>=2` exposes `mcp.server.mcpserver.MCPServer`; `mcp<2` exposes
    `mcp.server.fastmcp.FastMCP`. Both expose `.tool()` and `.run()`.
    """
    try:
        from mcp.server.mcpserver import MCPServer  # type: ignore

        return MCPServer
    except ImportError:
        pass

    try:
        from mcp.server.fastmcp import FastMCP  # type: ignore

        return FastMCP
    except ImportError as exc:  # pragma: no cover - depends on local install
        raise ImportError(MCP_IMPORT_ERROR) from exc


def is_mcp_available() -> bool:
    """True when the official MCP Python SDK can be imported."""
    try:
        _load_server_class()
    except ImportError:
        return False
    return True


# ---------------------------------------------------------------------------
# Repository helpers
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> List[str]:
    return [
        token
        for token in re.split(r"[^a-zA-Z0-9_]+", (text or "").lower())
        if len(token) >= 3 and token not in STOPWORDS
    ]


def _looks_like_slug(value: str) -> bool:
    """
    True for `owner/repo` style references rather than a filesystem path.

    Written explicitly instead of using os.sep/os.altsep because on Windows
    `os.altsep` is "/", which would reject every GitHub slug.
    """
    if not value:
        return False
    if "\\" in value or ":" in value:
        return False
    if value.startswith((".", "/", "~")):
        return False
    if os.sep != "/" and os.sep in value:
        return False
    parts = value.split("/")
    return len(parts) == 2 and all(part.strip() for part in parts)


def _read_text(path: str) -> Optional[str]:
    try:
        if os.path.getsize(path) > MAX_FILE_BYTES:
            return None
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except (OSError, ValueError):
        return None


def _collect_local_files(
    root: str,
    extensions: Tuple[str, ...],
    max_files: int,
) -> Dict[str, str]:
    """Walk `root` collecting text files whose extension is in `extensions`."""
    collected: Dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRECTORIES)
        for filename in sorted(filenames):
            if not filename.endswith(extensions):
                continue
            absolute = os.path.join(dirpath, filename)
            relative = os.path.relpath(absolute, root).replace(os.sep, "/")
            content = _read_text(absolute)
            if content is None:
                continue
            collected[relative] = content
            if len(collected) >= max_files:
                return collected
    return collected


def _score_file(relative_path: str, content: str, keywords: List[str]) -> int:
    """Keyword-overlap relevance score for a candidate file."""
    if not keywords:
        return 0
    haystack = f"{relative_path}\n{content}".lower()
    path_lower = relative_path.lower()
    score = 0
    for keyword in keywords:
        occurrences = haystack.count(keyword)
        if occurrences:
            # A keyword in the path is a much stronger signal than in the body.
            score += occurrences + (5 if keyword in path_lower else 0)
    return score


def _first_matching_line(content: str, keyword: str, default: int = 1) -> int:
    for index, line in enumerate(content.splitlines(), 1):
        if keyword in line.lower():
            return index
    return default


def _truncate(text: str, limit: int) -> str:
    text = text or ""
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[truncated]"


def _resolve_repository(
    repo_path: str,
    token: Optional[str] = None,
) -> Tuple[str, Optional[str], Dict[str, str], str]:
    """
    Resolve `repo_path` into a readable file map.

    Supports a local directory (primary mode, fully offline) and, when a GitHub
    token is available, an `owner/repo` slug resolved through the API.

    Returns `(source_label, root_path, files, source_kind)`.
    """
    candidate = (repo_path or ".").strip()

    if candidate and os.path.isdir(candidate):
        return candidate, os.path.abspath(candidate), {}, "local"

    if candidate and _looks_like_slug(candidate) and token:
        owner, repo = candidate.split("/", 1)
        tree = GitHubClient.fetch_repo_tree(token, owner, repo) or []
        files: Dict[str, str] = {}
        max_file = get_max_file_chars()
        for path in tree:
            if path.endswith(DEFAULT_CODE_EXTENSIONS + DEFAULT_DOC_EXTENSIONS):
                content = GitHubClient.fetch_file_content(token, owner, repo, path)
                if content:
                    files[path] = content[:max_file]
        return f"{owner}/{repo}", None, files, "github"

    return candidate or ".", None, {}, "missing"


# ---------------------------------------------------------------------------
# Tool implementations (no MCP SDK dependency)
# ---------------------------------------------------------------------------

class KnowledgeContextTools:
    """
    Grounded engineering-context tools backed by Knowledge's bounded engines.

    Every method returns a JSON-serializable dict so the same result can be
    asserted in unit tests and serialized over any MCP transport.
    """

    def __init__(self, token: Optional[str] = None, owner: Optional[str] = None, repo: Optional[str] = None):
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.owner = owner or os.getenv("KNOWLEDGE_OWNER")
        self.repo = repo or os.getenv("KNOWLEDGE_REPO")

    # -- helpers ---------------------------------------------------------

    @staticmethod
    def _failure(tool: str, reason: str, **extra: Any) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "ok": False,
            "tool": tool,
            "reason": reason,
            "evidence": [],
            "unknowns": [reason],
        }
        payload.update(extra)
        return payload

    def _github_target(self, owner: Optional[str], repo: Optional[str]) -> Optional[Tuple[str, str]]:
        resolved_owner = owner or self.owner
        resolved_repo = repo or self.repo
        if not resolved_owner or not resolved_repo:
            slug = os.getenv("GITHUB_REPOSITORY", "")
            if slug.count("/") == 1:
                resolved_owner = resolved_owner or slug.split("/", 1)[0]
                resolved_repo = resolved_repo or slug.split("/", 1)[1]
        if resolved_owner and resolved_repo:
            return resolved_owner, resolved_repo
        return None

    # -- Tool 1: architecture context -----------------------------------

    def get_architecture_context(
        self,
        query: str,
        repo_path: str = ".",
        max_files: int = 12,
    ) -> Dict[str, Any]:
        """
        Return the grounded mental model and evidence chain for a subsystem.

        Ranks repository files against the query, extracts real symbols from
        their source, and returns the evidence chain that grounds each claim.
        """
        query = (query or "").strip()
        if not query:
            return self._failure(
                "knowledge_get_architecture_context",
                "A non-empty `query` is required to build an architecture context.",
            )

        source_label, root, remote_files, source_kind = _resolve_repository(repo_path, self.token)

        if source_kind == "missing":
            return self._failure(
                "knowledge_get_architecture_context",
                f"Repository path `{source_label}` is not a readable directory and could not be resolved.",
                query=query,
                repo_path=repo_path,
            )

        if remote_files:
            code_files: Dict[str, str] = {
                path: body for path, body in remote_files.items() if path.endswith(DEFAULT_CODE_EXTENSIONS)
            }
            doc_files: Dict[str, str] = {
                path: body for path, body in remote_files.items() if path.endswith(DEFAULT_DOC_EXTENSIONS)
            }
        else:
            assert root is not None
            code_files = _collect_local_files(root, DEFAULT_CODE_EXTENSIONS, DEFAULT_MAX_CODE_FILES)
            doc_files = _collect_local_files(root, DEFAULT_DOC_EXTENSIONS, DEFAULT_MAX_DOC_FILES)

        intent_info = IntentClassifier.classify(query)
        keywords = list(dict.fromkeys(_tokenize(query) + intent_info.get("keywords", [])))

        scored_code = sorted(
            ((_score_file(path, body, keywords), path) for path, body in code_files.items()),
            key=lambda pair: (-pair[0], pair[1]),
        )
        scored_docs = sorted(
            ((_score_file(path, body, keywords), path) for path, body in doc_files.items()),
            key=lambda pair: (-pair[0], pair[1]),
        )

        selected = [(score, path) for score, path in scored_code if score > 0][:max_files]
        if not selected:
            selected = scored_code[:max_files]

        max_symbols = DEFAULT_MAX_SYMBOLS
        functions: List[Dict[str, Any]] = []
        classes: List[Dict[str, Any]] = []
        routes: List[Dict[str, Any]] = []
        env_vars: Set[str] = set()
        evidence: List[Dict[str, Any]] = []
        subsystems: List[Dict[str, Any]] = []

        for score, path in selected:
            content = code_files[path]
            symbols = CodeSymbolExtractor.extract_symbols(path, content)
            file_functions = symbols["functions"]
            file_classes = symbols["classes"]

            for fn in file_functions.values():
                if len(functions) >= max_symbols:
                    break
                functions.append(fn)
            for cls in file_classes.values():
                if len(classes) >= max_symbols:
                    break
                classes.append(cls)
            routes.extend(symbols["routes"][:10])
            env_vars.update(symbols["env_vars"])

            subsystems.append({
                "file": path,
                "relevance_score": score,
                "function_count": len(file_functions),
                "class_count": len(file_classes),
                "key_symbols": [
                    *(f"{fn['name']}({', '.join(fn.get('args', []))})" for fn in list(file_functions.values())[:6]),
                    *(cls["name"] for cls in list(file_classes.values())[:4]),
                ],
            })

            anchor_keyword = next((kw for kw in keywords if kw in content.lower()), None)
            evidence.append({
                "file": path,
                "start_line": _first_matching_line(content, anchor_keyword) if anchor_keyword else 1,
                "end_line": _first_matching_line(content, anchor_keyword) if anchor_keyword else 1,
                "why": f"Contains query keywords and {len(file_functions)} function(s) / {len(file_classes)} class(es).",
                "excerpt": _truncate(
                    next((line for line in content.splitlines() if anchor_keyword and anchor_keyword in line.lower()), content[:200]),
                    300,
                ),
            })

        for score, path in [(s, p) for s, p in scored_docs if s > 0][:5]:
            doc_claims = DocClaimExtractor.extract_claims(path, doc_files[path])
            evidence.append({
                "file": path,
                "start_line": 1,
                "end_line": len(doc_files[path].splitlines()) or 1,
                "why": f"Documentation matches the query with {len(doc_claims)} verifiable claim(s).",
                "excerpt": doc_files[path][:300],
            })

        rules = ""
        if "KNOWLEDGE.md" in doc_files:
            rules = _truncate(doc_files["KNOWLEDGE.md"], get_max_file_chars())

        unknowns: List[str] = []
        if not functions and not classes:
            unknowns.append(
                f"No functions or classes matched `{query}` in {source_label}; evidence is insufficient."
            )

        return {
            "ok": True,
            "tool": "knowledge_get_architecture_context",
            "query": query,
            "repo_path": source_label,
            "source": source_kind,
            "intent": intent_info.get("intent"),
            "keywords": keywords[:15],
            "mental_model": {
                "subsystems": subsystems,
                "functions": functions[:DEFAULT_MAX_SYMBOLS],
                "classes": classes[:DEFAULT_MAX_SYMBOLS],
                "http_routes": routes[:30],
                "environment_variables": sorted(env_vars)[:40],
            },
            "repository_rules": rules,
            "evidence": evidence,
            "unknowns": unknowns,
        }

    # -- Tool 2: documentation drift -------------------------------------

    def verify_doc_drift(
        self,
        doc_path: str,
        code_dir: str,
    ) -> Dict[str, Any]:
        """
        Run `DocDiscrepancyDetector` over a document (or doc directory) and the
        code directory it describes, returning every doc-vs-code mismatch.
        """
        doc_path = (doc_path or "").strip()
        code_dir = (code_dir or "").strip()

        if not doc_path or not code_dir:
            return self._failure(
                "knowledge_verify_doc_drift",
                "Both `doc_path` and `code_dir` are required.",
            )

        if not os.path.exists(doc_path):
            return self._failure(
                "knowledge_verify_doc_drift",
                f"Documentation path `{doc_path}` does not exist.",
                doc_path=doc_path,
                code_dir=code_dir,
            )

        if not os.path.isdir(code_dir):
            return self._failure(
                "knowledge_verify_doc_drift",
                f"Code directory `{code_dir}` is not a directory.",
                doc_path=doc_path,
                code_dir=code_dir,
            )

        docs: Dict[str, str] = {}
        if os.path.isfile(doc_path):
            body = _read_text(doc_path)
            if body is not None:
                docs[os.path.basename(doc_path)] = body
        else:
            docs = _collect_local_files(doc_path, DEFAULT_DOC_EXTENSIONS, DEFAULT_MAX_DOC_FILES)

        code_files = _collect_local_files(code_dir, DEFAULT_CODE_EXTENSIONS, DEFAULT_MAX_CODE_FILES)

        if not docs:
            return self._failure(
                "knowledge_verify_doc_drift",
                f"No readable documentation files found under `{doc_path}`.",
                doc_path=doc_path,
                code_dir=code_dir,
            )

        report = DocDiscrepancyDetector.detect_discrepancies(docs=docs, code_files=code_files)

        return {
            "ok": True,
            "tool": "knowledge_verify_doc_drift",
            "doc_path": doc_path,
            "code_dir": code_dir,
            "docs_analyzed": sorted(docs),
            "code_files_analyzed": len(code_files),
            "total_discrepancies": report.get("total_discrepancies", 0),
            "claims_analyzed": report.get("claims_analyzed", 0),
            "discrepancies": report.get("discrepancies", []),
            "summary": report.get("summary", ""),
            "evidence": [
                {
                    "file": d.get("source_doc", ""),
                    "start_line": d.get("line", 1),
                    "end_line": d.get("line", 1),
                    "why": d.get("type", ""),
                    "excerpt": d.get("details", ""),
                }
                for d in report.get("discrepancies", [])
            ],
            "unknowns": (
                []
                if report.get("total_discrepancies", 0)
                else [f"No drift detected between `{doc_path}` and `{code_dir}` within inspected files."]
            ),
        }

    # -- Tool 3: issue / PR lineage --------------------------------------

    def trace_issue_pr(
        self,
        issue_number: int,
        owner: Optional[str] = None,
        repo: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Return the bidirectional lineage for an issue: maintainer directives,
        previous attempts, touched files, and the issues those PRs reference.
        """
        try:
            issue_number = int(issue_number)
        except (TypeError, ValueError):
            return self._failure(
                "knowledge_trace_issue_pr",
                "`issue_number` must be an integer.",
                issue_number=issue_number,
            )

        if issue_number <= 0:
            return self._failure(
                "knowledge_trace_issue_pr",
                "`issue_number` must be a positive integer.",
                issue_number=issue_number,
            )

        if not self.token:
            return self._failure(
                "knowledge_trace_issue_pr",
                "A GitHub token is required. Set GITHUB_TOKEN (or pass one when constructing the tools).",
                issue_number=issue_number,
            )

        target = self._github_target(owner, repo)
        if not target:
            return self._failure(
                "knowledge_trace_issue_pr",
                "Repository owner/name is required. Set KNOWLEDGE_OWNER and KNOWLEDGE_REPO, or GITHUB_REPOSITORY.",
                issue_number=issue_number,
            )

        target_owner, target_repo = target
        issue = GitHubClient.fetch_issue(self.token, target_owner, target_repo, issue_number)
        if not issue:
            return self._failure(
                "knowledge_trace_issue_pr",
                f"Issue #{issue_number} was not found in {target_owner}/{target_repo}.",
                issue_number=issue_number,
                owner=target_owner,
                repo=target_repo,
            )

        comments = GitHubClient.fetch_issue_comments(self.token, target_owner, target_repo, issue_number) or []

        context = ContextEngine.build_structured_context(
            access_token=self.token,
            owner=target_owner,
            repo=target_repo,
            issue=issue,
            comments=comments,
        )

        max_comment = get_max_comment_chars()
        max_budget = get_max_diff_budget()

        # Bidirectional leg: which issues do the referenced PRs themselves target?
        back_references: List[Dict[str, Any]] = []
        for pr in context.get("linked_prs", []):
            pr_body = pr.get("body") or ""
            referenced = RelationshipExtractor.extract_referenced_issues(pr_body)
            back_references.append({
                "pr_number": pr.get("number"),
                "pr_state": pr.get("state"),
                "references_issues": referenced,
                "url": pr.get("html_url"),
            })

        evidence = [
            {
                "file": f"{target_owner}/{target_repo}#issue-{issue_number}",
                "start_line": 1,
                "end_line": 1,
                "why": "Issue metadata and maintainer directives.",
                "excerpt": _truncate(issue.get("body") or "", max_comment),
            }
        ]
        for pr in context.get("linked_prs", []):
            evidence.append({
                "file": pr.get("html_url") or f"{target_owner}/{target_repo}/pull/{pr.get('number')}",
                "start_line": 1,
                "end_line": 1,
                "why": f"Linked PR #{pr.get('number')} ({pr.get('state')}) touching {len(pr.get('changed_files') or [])} file(s).",
                "excerpt": _truncate(pr.get("body") or "", max_comment),
            })

        unknowns: List[str] = []
        if not context.get("linked_prs"):
            unknowns.append(f"No linked pull requests were referenced from issue #{issue_number}.")
        if not context.get("maintainer_directives"):
            unknowns.append(f"No maintainer directives were detected on issue #{issue_number}.")
        unfetched = sorted(
            set(RelationshipExtractor.extract_referenced_files(
                "\n".join(
                    [(issue.get("title") or ""), (issue.get("body") or "")]
                    + [(c.get("body") or "") for c in comments if isinstance(c, dict)]
                )
            ))
            - set((context.get("fetched_files") or {}).keys())
        )
        unknowns.extend(f"Referenced file could not be fetched: {path}" for path in unfetched)

        return {
            "ok": True,
            "tool": "knowledge_trace_issue_pr",
            "issue_number": issue_number,
            "owner": target_owner,
            "repo": target_repo,
            "issue_title": context.get("issue_title"),
            "issue_author": context.get("issue_author"),
            "issue_body": _truncate(context.get("issue_body") or "", max_comment),
            "maintainer_directives": context.get("maintainer_directives", []),
            "contributor_discussions": context.get("contributor_discussions", []),
            "previous_attempts": context.get("linked_prs", []),
            "touched_files": sorted((context.get("fetched_files") or {}).keys()),
            "reverse_references": back_references,
            "diff_budget_chars": max_budget,
            "formatted_evidence": context.get("formatted_evidence", ""),
            "evidence": evidence,
            "unknowns": unknowns,
        }


# ---------------------------------------------------------------------------
# MCP server wiring
# ---------------------------------------------------------------------------

def _call(func, *args):
    """
    Run a tool with stdout pointed at stderr for the duration of the call.

    On stdio transport stdout carries the JSON-RPC wire. The SDK diverts the
    descriptor, but on Windows `sys.stdout` keeps its original open handle, so a
    diagnostic printed inside a tool (the GitHub client emits
    `GitHub API Error (...)` to stdout) can still reach the wire and corrupt the
    frame. Scoping the redirect to the tool call keeps diagnostics in the
    client's log without diverting the protocol, which writes outside this scope.
    """
    with contextlib.redirect_stdout(sys.stderr):
        result = func(*args)
    return json.dumps(result, indent=2, default=str)


def build_server(tools: Optional[KnowledgeContextTools] = None):
    """
    Create the official MCP server instance with all Knowledge tools registered.

    Raises ImportError with installation guidance when the `mcp` SDK is absent.
    """
    server_class = _load_server_class()
    tools = tools or KnowledgeContextTools()
    try:
        server = server_class(
            name=SERVER_NAME,
            instructions=SERVER_INSTRUCTIONS,
            version=KNOWLEDGE_VERSION,
        )
    except TypeError:
        # Older SDK lines do not accept an explicit version string.
        server = server_class(name=SERVER_NAME, instructions=SERVER_INSTRUCTIONS)

    @server.tool(
        name="knowledge_get_architecture_context",
        description=(
            "Grounded mental model and evidence chain for a subsystem: ranked files, real "
            "functions/classes/routes/env vars extracted from source, repository rules, and "
            "explicit unknowns. Use before writing or changing code in an unfamiliar area."
        ),
    )
    def knowledge_get_architecture_context(query: str, repo_path: str = ".") -> str:
        return _call(tools.get_architecture_context, query, repo_path)

    @server.tool(
        name="knowledge_verify_doc_drift",
        description=(
            "Cross-reference documentation claims against the real code symbols in a directory "
            "using the AST doc-verifier. Returns missing implementations, signature mismatches, "
            "and env-var drift with file and line evidence."
        ),
    )
    def knowledge_verify_doc_drift(doc_path: str, code_dir: str) -> str:
        return _call(tools.verify_doc_drift, doc_path, code_dir)

    @server.tool(
        name="knowledge_trace_issue_pr",
        description=(
            "Bidirectional issue <-> PR lineage: maintainer directives, contributor discussion, "
            "previous attempts with touched files, and the issues those PRs reference."
        ),
    )
    def knowledge_trace_issue_pr(issue_number: int) -> str:
        return _call(tools.trace_issue_pr, issue_number)

    return server


def run_stdio(tools: Optional[KnowledgeContextTools] = None) -> None:
    """
    Serve MCP over stdio (Claude Desktop, Cursor, Claude Code).

    stdout carries the JSON-RPC wire here, so it must stay free of diagnostics.
    The MCP SDK claims the real stdout descriptor and points `sys.stdout` at
    stderr itself while serving the transport, which is why stray prints from
    the GitHub client surface in the client's log instead of corrupting a frame.
    """
    build_server(tools).run(transport="stdio")


def run_sse(
    host: str = "127.0.0.1",
    port: int = 8765,
    tools: Optional[KnowledgeContextTools] = None,
) -> None:
    """Serve MCP over SSE for clients that connect to a long-running endpoint."""
    build_server(tools).run(transport="sse", host=host, port=port)


def run(transport: str = "stdio", host: str = "127.0.0.1", port: int = 8765) -> None:
    """Dispatch to the requested MCP transport."""
    if transport == "stdio":
        run_stdio()
    elif transport == "sse":
        run_sse(host=host, port=port)
    else:
        raise ValueError(f"Unsupported MCP transport: {transport!r}. Use 'stdio' or 'sse'.")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def build_mcp_parser():
    """Build the `knowledge-agent mcp` argument parser."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="knowledge-agent mcp",
        description="Run Knowledge as a Model Context Protocol (MCP) server.",
    )
    transport = parser.add_mutually_exclusive_group()
    transport.add_argument(
        "--stdio",
        action="store_true",
        help="Serve over stdio (default; used by Claude Desktop, Cursor, Claude Code).",
    )
    transport.add_argument(
        "--sse",
        action="store_true",
        help="Serve over SSE on a long-running HTTP endpoint.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host for the SSE transport (default: 127.0.0.1).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port for the SSE transport (default: 8765).",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """CLI handler for `knowledge-agent mcp`."""
    parser = build_mcp_parser()
    args = parser.parse_args(argv)

    transport = "sse" if args.sse else "stdio"

    if not is_mcp_available():
        parser.exit(1, f"{MCP_IMPORT_ERROR}\n")

    try:
        run(transport=transport, host=args.host, port=args.port)
    except KeyboardInterrupt:  # pragma: no cover - interactive
        return 0
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())