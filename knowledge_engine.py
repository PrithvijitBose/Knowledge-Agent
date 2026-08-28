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
    GitHubClient,
    CitationFormatter,
    IntentCategory,
    IntentClassifier,
    RelationshipExtractor,
    ContextRetriever,
    ContextExplainer,
    ExecutionTracer,
    KnowledgeAgent,
    is_bot_triggered,
    process_github_comment,
)
from knowledge_agent.__main__ import main

if __name__ == "__main__":
    main()
