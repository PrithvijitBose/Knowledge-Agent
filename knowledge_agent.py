import os
import httpx
from typing import Dict, Any, List, Tuple
import config
import github_auth

MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"


def detect_knowledge_query(issue: Dict[str, Any], comments: List[Dict[str, Any]]) -> Tuple[str, str]:
    """
    Detects if there is a query directed to @Knowledge in comments or issue body.
    Returns (query_text, author_username).
    """
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
    """
    Calls Mistral AI API (model: mistral-small-2506) to generate a concise summary/answer.
    """
    if not config.is_mistral_configured():
        return ""
        
    headers = {
        "Authorization": f"Bearer {config.MISTRAL_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    
    payload = {
        "model": config.MISTRAL_MODEL,
        "messages": [
            {"role": "system", "content": prompt_system},
            {"role": "user", "content": prompt_user}
        ],
        "temperature": 0.2,
        "max_tokens": 1000
    }
    
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(MISTRAL_API_URL, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            choices = data.get("choices", [])
            if choices and "message" in choices[0]:
                return choices[0]["message"].get("content", "").strip()
    except Exception as e:
        print(f"Error invoking Mistral AI API ({config.MISTRAL_MODEL}): {e}")
        return ""


def generate_knowledge_answer(
    access_token: str,
    owner: str,
    repo: str,
    issue: Dict[str, Any],
    comments: List[Dict[str, Any]],
    custom_query: str = ""
) -> Dict[str, Any]:
    """
    Core @Knowledge Agent execution engine:
    1. Reads KNOWLEDGE.md FIRST from GitHub API to establish repository rules & guidelines.
    2. Reads Issue Title, Body & Comments.
    3. Fetches referenced files/documents from GitHub API.
    4. Invokes Mistral AI (mistral-small-2506) following strict KNOWLEDGE.md rules.
    """
    if custom_query:
        query_text = custom_query
        query_author = "User"
    else:
        query_text, query_author = detect_knowledge_query(issue, comments)
    
    # 1. ALWAYS Fetch KNOWLEDGE.md FIRST
    knowledge_rules_content = github_auth.fetch_repo_file_content(access_token, owner, repo, "KNOWLEDGE.md")
    
    # 2. Extract referenced candidate files
    combined_text = f"{issue.get('title', '')}\n{issue.get('body', '')}\n"
    for c in comments:
        combined_text += f"\n{c.get('body', '')}"
        
    candidate_files = github_auth.extract_referenced_files(combined_text)
    
    # 3. Fetch candidate files
    fetched_files = {}
    if knowledge_rules_content:
        fetched_files["KNOWLEDGE.md"] = knowledge_rules_content[:3000]
        
    for file_path in candidate_files:
        if file_path == "KNOWLEDGE.md":
            continue
        content = github_auth.fetch_repo_file_content(access_token, owner, repo, file_path)
        if content:
            fetched_files[file_path] = content[:3000]
            
    # 4. Formulate System Prompt with KNOWLEDGE.md Rules Priority
    if knowledge_rules_content:
        system_prompt = (
            "You are @Knowledge, an engineering context assistant for this repository. "
            "You MUST STRICTLY follow all rules defined in KNOWLEDGE.md below before answering:\n\n"
            f"=== MANDATORY REPOSITORY RULES (KNOWLEDGE.md) ===\n{knowledge_rules_content}\n"
            "=================================================\n\n"
            "Key Requirements:\n"
            "- Source Priority: 1. Issue info, 2. Explicitly referenced docs, 3. README/CONTRIBUTING/KNOWLEDGE.md, 4. Source code.\n"
            "- No Hallucination: Never invent decisions, APIs, or requirements.\n"
            "- Insufficient Info: If sources lack info, output: '> I couldn\\'t find enough project-specific information to answer this reliably. Please contact a maintainer or ask them to provide the relevant documentation.'\n"
            "- Evidence: Trace every claim to a file/issue source.\n"
            "- Format: Clean, concise GitHub markdown."
        )
    else:
        system_prompt = (
            "You are @Knowledge, an AI GitHub assistant like CodeRabbit. "
            "Answer the user query accurately, concisely, and cleanly based on the repository content provided. "
            "Never invent details not present in the files."
        )
        
    # Build User Prompt
    repo_context = f"Repository: {owner}/{repo}\nIssue #{issue.get('number')}: {issue.get('title')}\n"
    repo_context += f"Issue Body:\n{issue.get('body', '')}\n\n"
    
    if comments:
        repo_context += "Comments Thread:\n"
        for c in comments:
            repo_context += f"- @{c.get('user', {}).get('login')}: {c.get('body')}\n"
            
    if fetched_files:
        repo_context += "\n--- REPOSITORY SOURCE FILES ---\n"
        for fname, fcontent in fetched_files.items():
            repo_context += f"\nFile [{fname}]:\n{fcontent}\n"
            
    user_prompt = f"{repo_context}\n\nContributor Question (@{query_author}): {query_text}\n\nPlease generate a response adhering to KNOWLEDGE.md rules:"
    
    # Call Mistral AI model (mistral-small-2506)
    llm_answer = call_mistral_api(system_prompt, user_prompt)
    
    if llm_answer:
        final_answer = llm_answer
        engine_used = f"Mistral AI ({config.MISTRAL_MODEL}) [KNOWLEDGE.md Enforced]"
    else:
        final_answer = _fallback_summarizer(query_author, query_text, fetched_files)
        engine_used = "Built-in Contextual Summarizer (Fallback)"
        
    return {
        "query": query_text,
        "author": query_author,
        "answer": final_answer,
        "engine": engine_used,
        "files_read": list(fetched_files.keys()),
        "files_content": fetched_files
    }


def _fallback_summarizer(query_author: str, query_text: str, fetched_files: Dict[str, str]) -> str:
    """Fallback summarizer if Mistral API is not configured."""
    summary_sections = []
    
    if "KNOWLEDGE.md" in fetched_files:
        summary_sections.append("#### 📜 Repository Rules (`KNOWLEDGE.md`)\n" + fetched_files["KNOWLEDGE.md"][:500])
        
    if "requirements.txt" in fetched_files:
        summary_sections.append("#### 📦 Dependencies (`requirements.txt`)\n" + 
            "\n".join([f"- `{line.strip()}`" for line in fetched_files["requirements.txt"].splitlines() if line.strip() and not line.startswith("#")])
        )
        
    if "README.md" in fetched_files:
        lines = [l.strip() for l in fetched_files["README.md"].splitlines() if l.strip()]
        summary_sections.append("#### 🚀 Repository README Summary\n" + "\n".join(lines[:12]))
        
    if not summary_sections:
        for fname, fcontent in fetched_files.items():
            summary_sections.append(f"#### 📄 File: `{fname}`\n" + fcontent[:400])
            
    return (
        f"Hi **@{query_author}**, here is the summarized knowledge extracted from the repository files:\n\n"
        + "\n\n".join(summary_sections)
    )
