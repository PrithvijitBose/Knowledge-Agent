"""
knowledge_agent.py — Backward-compatibility Shim
Re-exports LLM synthesizer and detection logic from `knowledge_engine.py`.
"""

from typing import Dict, Any, List, Tuple
import knowledge_engine


def detect_knowledge_query(issue: Dict[str, Any], comments: List[Dict[str, Any]]) -> Tuple[str, str]:
    for c in reversed(comments):
        body = c.get("body", "")
        if "@Knowledge" in body or "@knowledge" in body:
            author = c.get("user", {}).get("login", "Contributor")
            return body.strip(), author

    issue_body = issue.get("body", "")
    if "@Knowledge" in issue_body or "@knowledge" in issue_body:
        author = issue.get("user", {}).get("login", "Maintainer")
        return issue_body.strip(), author

    return "What are the prerequisites and setup instructions for this repository?", "User"


def call_mistral_api(prompt_system: str, prompt_user: str) -> str:
    return knowledge_engine.KnowledgeAgent.call_mistral_api(prompt_system, prompt_user)


def generate_knowledge_answer(
    access_token: str,
    owner: str,
    repo: str,
    issue: Dict[str, Any],
    comments: List[Dict[str, Any]],
    custom_query: str = ""
) -> Dict[str, Any]:
    query_text = custom_query or issue.get("body", "") or "What should I understand first?"
    issue_num = issue.get("number", 1)
    return knowledge_engine.KnowledgeAgent.generate_answer(
        token=access_token,
        owner=owner,
        repo=repo,
        query=query_text,
        issue_number=issue_num
    )
