"""
Knowledge Engine (knowledge_engine.py)
Unified Core Engine & Backward Compatibility Facade for Knowledge Agent.

All components are modularized in the `knowledge_agent` package:
- knowledge_agent.config: Configuration and environment variables
- knowledge_agent.github: GitHub REST API Client
- knowledge_agent.citations: Citation and permalink formatting
- knowledge_agent.intent: IntentCategory and IntentClassifier
- knowledge_agent.retriever: RelationshipExtractor and ContextRetriever
- knowledge_agent.prompt: ContextExplainer
- knowledge_agent.tracer: ExecutionTracer
- knowledge_agent.agent: KnowledgeAgent, is_bot_triggered, process_github_comment
- knowledge_agent.__main__: CLI entry point
"""

from adaptive_depth import AdaptiveDepthEngine
from multi_repo import MultiRepoConfig
from knowledge_agent import (
    __version__,
    GITHUB_CLIENT_ID,
    GITHUB_CLIENT_SECRET,
    REDIRECT_URI,
    MISTRAL_API_KEY,
    MISTRAL_MODEL,
    MISTRAL_API_URL,
    GITHUB_API_BASE,
    GITHUB_AUTH_URL,
    GITHUB_TOKEN_URL,
    is_github_configured,
    is_mistral_configured,
    is_llm_configured,
    get_max_file_chars,
    get_max_comment_chars,
    get_max_diff_chars,
    get_max_diff_budget,
    GitHubClient,
    CitationFormatter,
    IntentCategory,
    IntentClassifier,
    RelationshipExtractor,
    ContextRetriever,
    truncate_diff_hunk_aware,
    ContextExplainer,
    ExecutionTracer,
    KnowledgeAgent,
    is_bot_triggered,
    process_github_comment,
)
from knowledge_agent.__main__ import main

__all__ = [
    "__version__",
    "GITHUB_CLIENT_ID",
    "GITHUB_CLIENT_SECRET",
    "REDIRECT_URI",
    "MISTRAL_API_KEY",
    "MISTRAL_MODEL",
    "MISTRAL_API_URL",
    "GITHUB_API_BASE",
    "GITHUB_AUTH_URL",
    "GITHUB_TOKEN_URL",
    "is_github_configured",
    "is_mistral_configured",
    "is_llm_configured",
    "get_max_file_chars",
    "get_max_comment_chars",
    "get_max_diff_chars",
    "GitHubClient",
    "CitationFormatter",
    "IntentCategory",
    "IntentClassifier",
    "RelationshipExtractor",
    "ContextRetriever",
    "ContextExplainer",
    "ExecutionTracer",
    "KnowledgeAgent",
    "is_bot_triggered",
    "process_github_comment",
    "AdaptiveDepthEngine",
    "MultiRepoConfig",
    "main",
]

def format_citations_table(citations: list[dict]) -> str:
    """Format multiple file citations into a readable markdown table."""
    if not citations:
        return ""
    lines = [
        "| File | Lines | Link |",
        "| :--- | :--- | :--- |"
    ]
    for c in citations:
        file_path = c.get("file", "")
        start = c.get("start_line", "")
        end = c.get("end_line", "")
        line_range = f"L{start}-L{end}" if start and end else f"L{start}" if start else "—"
        url = c.get("url", "")
        link = f"[View source]({url})" if url else "—"
        lines.append(f"| `{file_path}` | {line_range} | {link} |")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
