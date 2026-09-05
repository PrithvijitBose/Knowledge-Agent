"""
Knowledge Agent — The Engineering Context Layer for Repositories.
"""

__version__ = "0.3.1"

from knowledge_agent.config import (
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
)
from knowledge_agent.github import GitHubClient
from knowledge_agent.citations import CitationFormatter
from knowledge_agent.intent import IntentCategory, IntentClassifier
from knowledge_agent.retriever import RelationshipExtractor, ContextRetriever, truncate_diff_hunk_aware
from knowledge_agent.prompt import ContextExplainer
from knowledge_agent.tracer import ExecutionTracer
from knowledge_agent.agent import KnowledgeAgent, is_bot_triggered, process_github_comment

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
    "get_max_diff_budget",
    "GitHubClient",
    "CitationFormatter",
    "IntentCategory",
    "IntentClassifier",
    "RelationshipExtractor",
    "ContextRetriever",
    "truncate_diff_hunk_aware",
    "ContextExplainer",
    "ExecutionTracer",
    "KnowledgeAgent",
    "is_bot_triggered",
    "process_github_comment",
]
