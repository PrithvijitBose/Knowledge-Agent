"""
Knowledge Engine (knowledge_engine.py)
Unified Core Engine for Knowledge — The Engineering Context Layer for Repositories.

Features:
1. Config & Environment Management
2. GitHub REST API Client (Issues, PRs, Comments, File Contents, Tree)
3. Intent-Driven Context Discovery (Decoupled Intent Classification & Minimal Evidence Retrieval)
4. Intent-Specific Personalized Response Synthesizer (Issue, PR, Onboarding, Architecture, Feature, Historical, Contribution)
5. Bidirectional Issue ↔ PR Relationship Parsing
6. Guardrail-Enforced Mistral AI Prompt Engine adhering to KNOWLEDGE.md
7. Headless CLI Runner for GitHub Actions
"""

import sys
import os
import re
import urllib.parse
import base64
import argparse
from typing import Dict, Any, List, Optional, Tuple
import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# =====================================================================
# 1. CONFIGURATION & ENVIRONMENT
# =====================================================================

GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")
REDIRECT_URI = os.getenv("REDIRECT_URI", "http://localhost:8501")

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-small-2506")
MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"
GITHUB_API_BASE = "https://api.github.com"
GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"


def is_github_configured() -> bool:
    """Check if GitHub OAuth credentials are configured."""
    return bool(
        GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET and
        GITHUB_CLIENT_ID != "your_github_client_id" and
        GITHUB_CLIENT_SECRET != "your_github_client_secret"
    )


def is_mistral_configured() -> bool:
    """Check if Mistral API key is configured."""
    return bool(MISTRAL_API_KEY and MISTRAL_API_KEY != "your_mistral_api_key")


# =====================================================================
# 2. GITHUB REST API CLIENT
# =====================================================================

class GitHubClient:
    """GitHub REST API wrapper for fetching issues, PRs, comments, and file contents."""

    @staticmethod
    def _get_headers(token: str) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Knowledge-Engineering-Context-App",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    @staticmethod
    def fetch_user(token: str) -> Optional[Dict[str, Any]]:
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(f"{GITHUB_API_BASE}/user", headers=GitHubClient._get_headers(token))
                res.raise_for_status()
                return res.json()
        except Exception as e:
            print(f"GitHub API Error (fetch_user): {e}")
            return None

    @staticmethod
    def fetch_repositories(token: str, visibility: str = "all") -> List[Dict[str, Any]]:
        params = {"sort": "updated", "direction": "desc", "per_page": 100, "visibility": visibility}
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(f"{GITHUB_API_BASE}/user/repos", headers=GitHubClient._get_headers(token), params=params)
                res.raise_for_status()
                return res.json()
        except Exception as e:
            print(f"GitHub API Error (fetch_repositories): {e}")
            return []

    @staticmethod
    def fetch_issue(token: str, owner: str, repo: str, issue_number: int) -> Optional[Dict[str, Any]]:
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues/{issue_number}", headers=GitHubClient._get_headers(token))
                res.raise_for_status()
                return res.json()
        except Exception as e:
            print(f"GitHub API Error (fetch_issue #{issue_number}): {e}")
            return None

    @staticmethod
    def fetch_repo_issues(token: str, owner: str, repo: str) -> List[Dict[str, Any]]:
        params = {"state": "all", "sort": "updated", "direction": "desc", "per_page": 30}
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues", headers=GitHubClient._get_headers(token), params=params)
                res.raise_for_status()
                return [i for i in res.json() if "pull_request" not in i]
        except Exception as e:
            print(f"GitHub API Error (fetch_repo_issues): {e}")
            return []

    @staticmethod
    def fetch_pull_request(token: str, owner: str, repo: str, pr_number: int) -> Optional[Dict[str, Any]]:
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}", headers=GitHubClient._get_headers(token))
                res.raise_for_status()
                return res.json()
        except Exception as e:
            print(f"GitHub API Error (fetch_pull_request #{pr_number}): {e}")
            return None

    @staticmethod
    def fetch_pr_files(token: str, owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/files", headers=GitHubClient._get_headers(token))
                res.raise_for_status()
                return res.json()
        except Exception as e:
            print(f"GitHub API Error (fetch_pr_files #{pr_number}): {e}")
            return []

    @staticmethod
    def fetch_issue_comments(token: str, owner: str, repo: str, issue_number: int) -> List[Dict[str, Any]]:
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues/{issue_number}/comments", headers=GitHubClient._get_headers(token))
                res.raise_for_status()
                return res.json()
        except Exception as e:
            print(f"GitHub API Error (fetch_issue_comments #{issue_number}): {e}")
            return []

    @staticmethod
    def fetch_pr_comments(token: str, owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        comments = []
        try:
            with httpx.Client(timeout=10.0) as client:
                headers = GitHubClient._get_headers(token)
                res_issue = client.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues/{pr_number}/comments", headers=headers)
                if res_issue.status_code == 200:
                    comments.extend(res_issue.json())
                res_pr = client.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/comments", headers=headers)
                if res_pr.status_code == 200:
                    comments.extend(res_pr.json())
        except Exception as e:
            print(f"GitHub API Error (fetch_pr_comments #{pr_number}): {e}")
        return comments

    @staticmethod
    def fetch_file_content(token: str, owner: str, repo: str, file_path: str) -> Optional[str]:
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{file_path}", headers=GitHubClient._get_headers(token))
                res.raise_for_status()
                data = res.json()
                if "content" in data and data.get("encoding") == "base64":
                    decoded_bytes = base64.b64decode(data["content"])
                    return decoded_bytes.decode("utf-8", errors="replace")
                return None
        except Exception as e:
            print(f"GitHub API Error (fetch_file_content '{file_path}'): {e}")
            return None

    @staticmethod
    def fetch_repo_tree(token: str, owner: str, repo: str) -> List[str]:
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/trees/main?recursive=1", headers=GitHubClient._get_headers(token))
                if res.status_code != 200:
                    res = client.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/trees/master?recursive=1", headers=GitHubClient._get_headers(token))
                if res.status_code == 200:
                    tree_data = res.json().get("tree", [])
                    return [item["path"] for item in tree_data if item.get("type") == "blob"]
        except Exception as e:
            print(f"GitHub API Error (fetch_repo_tree): {e}")
        return []

    @staticmethod
    def post_issue_comment(token: str, owner: str, repo: str, issue_number: int, comment_body: str) -> bool:
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(
                    f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues/{issue_number}/comments",
                    headers=GitHubClient._get_headers(token),
                    json={"body": comment_body}
                )
                res.raise_for_status()
                return True
        except Exception as e:
            print(f"GitHub API Error (post_issue_comment #{issue_number}): {e}")
            return False


# =====================================================================
# 3. BIDIRECTIONAL RELATIONSHIPS & INTENT CLASSIFIER
# =====================================================================

class RelationshipExtractor:
    """Parses text for explicit and implicit bidirectional relationships between Issues, PRs, and Files."""

    @staticmethod
    def extract_referenced_prs(text: str) -> List[int]:
        if not text:
            return []
        patterns = [
            r'(?:PR|pr|Pull Request|pull)\s*#(\d+)',
            r'github\.com\/[^\/]+\/[^\/]+\/pull\/(\d+)',
            r'pull\/(\d+)'
        ]
        numbers = set()
        for pat in patterns:
            for match in re.findall(pat, text, re.IGNORECASE):
                try:
                    numbers.add(int(match))
                except ValueError:
                    pass
        return sorted(list(numbers))

    @staticmethod
    def extract_referenced_issues(text: str) -> List[int]:
        if not text:
            return []
        patterns = [
            r'(?:Fixes|Closes|Resolves|Issue|issue)\s*#(\d+)',
            r'github\.com\/[^\/]+\/[^\/]+\/issues\/(\d+)',
            r'issues\/(\d+)'
        ]
        numbers = set()
        for pat in patterns:
            for match in re.findall(pat, text, re.IGNORECASE):
                try:
                    numbers.add(int(match))
                except ValueError:
                    pass
        return sorted(list(numbers))

    @staticmethod
    def extract_referenced_files(text: str) -> List[str]:
        if not text:
            return []
        pattern = r'\b([a-zA-Z0-9_\-\/\.]+\.(?:md|txt|py|json|yml|yaml|env|toml|js|ts|jsx|tsx|html|css|go|rs|java|c|cpp|h))\b'
        matches = re.findall(pattern, text)
        defaults = ["KNOWLEDGE.md", "README.md", "CONTRIBUTING.md", "requirements.txt", "config.py", "package.json"]
        return list(set(matches + defaults))


class IntentCategory:
    ISSUE_UNDERSTANDING = "ISSUE_UNDERSTANDING"
    PR_UNDERSTANDING = "PR_UNDERSTANDING"
    REPO_ONBOARDING = "REPO_ONBOARDING"
    ARCHITECTURE_UNDERSTANDING = "ARCHITECTURE_UNDERSTANDING"
    FEATURE_UNDERSTANDING = "FEATURE_UNDERSTANDING"
    HISTORICAL_DECISION = "HISTORICAL_DECISION"
    CONTRIBUTION_GUIDANCE = "CONTRIBUTION_GUIDANCE"
    GENERAL_QUERY = "GENERAL_QUERY"


class IntentClassifier:
    """Classifies contributor query into decoupled intent categories and extracts topic keywords."""

    @staticmethod
    def classify(query: str) -> Dict[str, Any]:
        query_lower = query.lower()

        # Extract target entities
        prs = RelationshipExtractor.extract_referenced_prs(query)
        issues = RelationshipExtractor.extract_referenced_issues(query)
        files = RelationshipExtractor.extract_referenced_files(query)

        # Keyword topic extraction
        topic_keywords = []
        for kw in ["auth", "authentication", "login", "oauth", "database", "api", "router", "frontend", "backend", "test", "docker", "deploy"]:
            if kw in query_lower:
                topic_keywords.append(kw)

        # 1. PR Understanding
        if prs or any(k in query_lower for k in ["why does pr", "pr #", "pull request", "pr context", "pr review"]):
            return {"intent": IntentCategory.PR_UNDERSTANDING, "pr_numbers": prs, "keywords": topic_keywords}

        # 2. Repo Onboarding
        if any(k in query_lower for k in ["just joined", "new here", "learn this codebase", "how should i learn", "onboard", "where do i start", "prerequisites"]):
            return {"intent": IntentCategory.REPO_ONBOARDING, "keywords": topic_keywords}

        # 3. Contribution Guidance
        if any(k in query_lower for k in ["contribute", "run tests", "setup dev", "installation", "build", "how do i run", "how to run", "how to build", "how to test"]):
            return {"intent": IntentCategory.CONTRIBUTION_GUIDANCE, "keywords": topic_keywords}

        # 4. Architecture Understanding
        if any(k in query_lower for k in ["architecture", "how does", "how do ", "work in this", "design", "component", "flow", "structure"]):
            if any(k in query_lower for k in ["auth", "authentication", "security", "database", "api", "routing", "workflow"]):
                return {"intent": IntentCategory.ARCHITECTURE_UNDERSTANDING, "topic": "subsystem", "keywords": topic_keywords}
            return {"intent": IntentCategory.ARCHITECTURE_UNDERSTANDING, "topic": "general", "keywords": topic_keywords}
            return {"intent": IntentCategory.CONTRIBUTION_GUIDANCE, "keywords": topic_keywords}

        # 7. Issue Understanding
        if issues or any(k in query_lower for k in ["issue #", "working on issue", "before contributing to issue", "fix issue"]):
            return {"intent": IntentCategory.ISSUE_UNDERSTANDING, "issue_numbers": issues, "keywords": topic_keywords}

        return {"intent": IntentCategory.GENERAL_QUERY, "keywords": topic_keywords}


# =====================================================================
# 4. INTENT-DRIVEN TARGETED CONTEXT DISCOVERY
# =====================================================================

class ContextRetriever:
    """Gathers only the minimal, high-signal evidence required for the query intent."""

    @staticmethod
    def discover_context(
        token: str,
        owner: str,
        repo: str,
        query: str,
        intent_info: Dict[str, Any],
        issue_number: Optional[int] = None,
        pr_number: Optional[int] = None
    ) -> Dict[str, Any]:
        intent = intent_info.get("intent", IntentCategory.GENERAL_QUERY)
        keywords = intent_info.get("keywords", [])

        knowledge_rules = GitHubClient.fetch_file_content(token, owner, repo, "KNOWLEDGE.md")
        fetched_files = {}
        if knowledge_rules:
            fetched_files["KNOWLEDGE.md"] = knowledge_rules[:3000]

        evidence = {
            "intent": intent,
            "query": query,
            "owner": owner,
            "repo": repo,
            "knowledge_rules": knowledge_rules,
            "fetched_files": fetched_files
        }

        # Route retrieval based on Intent Category
        if intent == IntentCategory.PR_UNDERSTANDING:
            target_pr = pr_number or (intent_info.get("pr_numbers", [1])[0] if intent_info.get("pr_numbers") else 1)
            pr = GitHubClient.fetch_pull_request(token, owner, repo, target_pr)
            pr_comments = GitHubClient.fetch_pr_comments(token, owner, repo, target_pr)
            changed_files = GitHubClient.fetch_pr_files(token, owner, repo, target_pr)

            evidence["pr"] = pr
            evidence["pr_comments"] = pr_comments
            evidence["changed_files"] = changed_files

            # Fetch content of key changed files
            for f in changed_files[:5]:
                filename = f.get("filename")
                if filename and filename not in fetched_files:
                    content = GitHubClient.fetch_file_content(token, owner, repo, filename)
                    if content:
                        fetched_files[filename] = content[:2500]

        elif intent == IntentCategory.REPO_ONBOARDING:
            readme = GitHubClient.fetch_file_content(token, owner, repo, "README.md")
            contributing = GitHubClient.fetch_file_content(token, owner, repo, "CONTRIBUTING.md")
            reqs = GitHubClient.fetch_file_content(token, owner, repo, "requirements.txt") or GitHubClient.fetch_file_content(token, owner, repo, "package.json")
            tree = GitHubClient.fetch_repo_tree(token, owner, repo)

            if readme:
                fetched_files["README.md"] = readme[:3000]
            if contributing:
                fetched_files["CONTRIBUTING.md"] = contributing[:3000]
            if reqs:
                fetched_files["DEPENDENCIES"] = reqs[:1500]

            evidence["tree"] = tree[:40]

        elif intent == IntentCategory.ARCHITECTURE_UNDERSTANDING:
            tree = GitHubClient.fetch_repo_tree(token, owner, repo)
            readme = GitHubClient.fetch_file_content(token, owner, repo, "README.md")
            if readme:
                fetched_files["README.md"] = readme[:3000]

            # Search tree for architecture/subsystem related files
            architecture_candidates = []
            for path in tree:
                path_lower = path.lower()
                if any(kw in path_lower for kw in keywords + ["arch", "docs", "design", "security", "auth", "core", "agent", "auth"]):
                    architecture_candidates.append(path)

            for path in architecture_candidates[:6]:
                if path not in fetched_files:
                    content = GitHubClient.fetch_file_content(token, owner, repo, path)
                    if content:
                        fetched_files[path] = content[:2500]

            evidence["architecture_files"] = architecture_candidates
            evidence["tree_sample"] = [p for p in tree if "/" not in p or p.count("/") <= 1][:30]

        elif intent == IntentCategory.FEATURE_UNDERSTANDING or intent == IntentCategory.HISTORICAL_DECISION:
            tree = GitHubClient.fetch_repo_tree(token, owner, repo)
            readme = GitHubClient.fetch_file_content(token, owner, repo, "README.md")
            if readme:
                fetched_files["README.md"] = readme[:2500]

            matching_files = [p for p in tree if any(kw in p.lower() for kw in keywords)][:5]
            for path in matching_files:
                if path not in fetched_files:
                    content = GitHubClient.fetch_file_content(token, owner, repo, path)
                    if content:
                        fetched_files[path] = content[:2500]

            evidence["matching_files"] = matching_files

        elif intent == IntentCategory.CONTRIBUTION_GUIDANCE:
            contributing = GitHubClient.fetch_file_content(token, owner, repo, "CONTRIBUTING.md")
            readme = GitHubClient.fetch_file_content(token, owner, repo, "README.md")
            reqs = GitHubClient.fetch_file_content(token, owner, repo, "requirements.txt") or GitHubClient.fetch_file_content(token, owner, repo, "package.json")

            if contributing:
                fetched_files["CONTRIBUTING.md"] = contributing[:3000]
            if readme:
                fetched_files["README.md"] = readme[:2500]
            if reqs:
                fetched_files["DEPENDENCIES"] = reqs[:1500]

        else: # ISSUE_UNDERSTANDING or GENERAL_QUERY
            target_issue = issue_number or (intent_info.get("issue_numbers", [1])[0] if intent_info.get("issue_numbers") else 1)
            iss = GitHubClient.fetch_issue(token, owner, repo, target_issue)
            comments = GitHubClient.fetch_issue_comments(token, owner, repo, target_issue)

            evidence["issue"] = iss or {"number": target_issue, "title": f"Issue #{target_issue}", "body": query}
            evidence["comments"] = comments

            combined_text = f"{evidence['issue'].get('title', '')}\n{evidence['issue'].get('body', '')}\n" + "\n".join([c.get('body', '') for c in comments])
            ref_prs = RelationshipExtractor.extract_referenced_prs(combined_text)
            ref_files = RelationshipExtractor.extract_referenced_files(combined_text)

            evidence["referenced_prs"] = ref_prs

            for fname in ref_files[:6]:
                if fname not in fetched_files:
                    content = GitHubClient.fetch_file_content(token, owner, repo, fname)
                    if content:
                        fetched_files[fname] = content[:2500]

        return evidence


# =====================================================================
# 5. INTENT-SPECIFIC PERSONALIZED RESPONSE SYNTHESIZER
# =====================================================================

class ContextExplainer:
    """Formats personalized system & user prompts customized for each intent class."""

    @staticmethod
    def build_system_prompt(intent: str, knowledge_rules: Optional[str], author: str = "Contributor") -> str:
        base = (
            "You are @Knowledge, the Engineering Context Layer for this repository.\n"
            "Your identity is NOT an AI coding bot or PR reviewer. Your sole purpose is: Help a contributor understand what they need to know BEFORE changing code.\n"
            "Personalization Directive: Address the contributor @{author} directly, answer their exact specific query FIRST, and adapt your explanation structure strictly to their intent.\n"
        )

        if knowledge_rules:
            base += f"\n=== MANDATORY REPOSITORY RULES (KNOWLEDGE.md) ===\n{knowledge_rules}\n=================================================\n\n"
            base += (
                "Key Rules:\n"
                "- Source Priority: 1. Target Issue/PR/Feature evidence, 2. Explicit docs, 3. README/CONTRIBUTING/KNOWLEDGE.md, 4. Source code.\n"
                "- No Hallucination: Never invent APIs or requirements not backed by repo files.\n"
                "- Insufficient Info: If sources lack details, explicitly defer to maintainers.\n"
            )

        if intent == IntentCategory.ISSUE_UNDERSTANDING:
            base += (
                "\nStructure your response as:\n"
                "1. **Direct Answer to @{author}'s Issue Query**\n"
                "2. **What Must Be Understood First**\n"
                "3. **Relevant Source Files & Docs**\n"
                "4. **Known Constraints & Unknowns (Maintainer Input Required)**\n"
                "5. **Suggested Exploration Path**"
            )
        elif intent == IntentCategory.PR_UNDERSTANDING:
            base += (
                "\nStructure your response as:\n"
                "1. **Context & Purpose of PR**\n"
                "2. **Linked Issues & Engineering Motivation**\n"
                "3. **Key Changed Files & Architectural Impact**\n"
                "4. **Reviewer Discussion & Historical Decisions**"
            )
        elif intent == IntentCategory.REPO_ONBOARDING:
            base += (
                "\nStructure your response as:\n"
                "1. **Welcome & Repository Purpose**\n"
                "2. **Prerequisites & Stack**\n"
                "3. **Cognitive Priority Tiering**:\n"
                "   - **Must Understand** (safe minimum required before contributing)\n"
                "   - **Useful Later**\n"
                "   - **Ignore for Now**\n"
                "4. **Guided Learning Path** ('Why am I reading this next?')"
            )
        elif intent == IntentCategory.ARCHITECTURE_UNDERSTANDING:
            base += (
                "\nStructure your response as:\n"
                "1. **High-Level Subsystem Architecture**\n"
                "2. **Core Components & Key Source Files**\n"
                "3. **Data / Request Execution Flow**\n"
                "4. **Architectural Constraints & Design Decisions**"
            )
        elif intent == IntentCategory.FEATURE_UNDERSTANDING:
            base += (
                "\nStructure your response as:\n"
                "1. **Feature Implementation Overview**\n"
                "2. **Primary Code Entrypoints**\n"
                "3. **How It Intersects With Other Modules**\n"
                "4. **Key Files to Inspect**"
            )
        else:
            base += (
                "\nStructure your response cleanly in Markdown focusing specifically on the user's question without dumping generic repository overviews."
            )

        return base.replace("{author}", author)

    @staticmethod
    def build_user_prompt(evidence: Dict[str, Any], query_author: str = "Contributor") -> str:
        intent = evidence.get("intent", IntentCategory.GENERAL_QUERY)
        query = evidence.get("query", "")
        owner = evidence.get("owner", "")
        repo = evidence.get("repo", "")
        fetched_files = evidence.get("fetched_files", {})

        prompt = f"Repository: {owner}/{repo}\nContributor (@{query_author}) Query: {query}\nIntent Category: {intent}\n\n"

        if intent == IntentCategory.PR_UNDERSTANDING and "pr" in evidence:
            pr = evidence["pr"]
            prompt += f"--- TARGET PULL REQUEST #{pr.get('number')} ---\nTitle: {pr.get('title')}\nBody:\n{pr.get('body')}\n"
            if evidence.get("changed_files"):
                prompt += "\nChanged Files:\n" + "\n".join([f"- {f.get('filename')} (+{f.get('additions')}/-{f.get('deletions')})" for f in evidence["changed_files"]])
            if evidence.get("pr_comments"):
                prompt += "\nReview Discussion:\n" + "\n".join([f"- @{c.get('user',{}).get('login')}: {c.get('body')}" for c in evidence["pr_comments"][:5]])

        elif intent == IntentCategory.ARCHITECTURE_UNDERSTANDING:
            if evidence.get("architecture_files"):
                prompt += "Subsystem / Architecture Files Found:\n" + "\n".join([f"- {p}" for p in evidence["architecture_files"]]) + "\n\n"
            if evidence.get("tree_sample"):
                prompt += "Top-Level Repository Structure:\n" + "\n".join([f"- {p}" for p in evidence["tree_sample"]]) + "\n\n"

        elif intent == IntentCategory.REPO_ONBOARDING:
            if evidence.get("tree"):
                prompt += f"Repository Tree Sample (Total files: {len(evidence['tree'])}):\n" + "\n".join([f"- {p}" for p in evidence["tree"][:25]]) + "\n\n"

        elif "issue" in evidence and evidence["issue"]:
            iss = evidence["issue"]
            prompt += f"--- TARGET ISSUE #{iss.get('number')} ---\nTitle: {iss.get('title')}\nBody:\n{iss.get('body')}\n"
            if evidence.get("comments"):
                prompt += "\nComments Thread:\n" + "\n".join([f"- @{c.get('user',{}).get('login')}: {c.get('body')}" for c in evidence["comments"][:5]])

        if fetched_files:
            prompt += "\n--- RETRIEVED HIGH-SIGNAL EVIDENCE FILES ---\n"
            for fname, fcontent in fetched_files.items():
                prompt += f"\nFile [{fname}]:\n{fcontent}\n"

        prompt += f"\nPlease answer @{query_author}'s question directly adhering to KNOWLEDGE.md rules and intent structure:"
        return prompt


# =====================================================================
# 6. MISTRAL AI LLM SYNTHESIZER & KNOWLEDGE AGENT
# =====================================================================

class KnowledgeAgent:
    """Core AI synthesizer using intent-driven context selection and Mistral AI."""

    @staticmethod
    def call_mistral_api(prompt_system: str, prompt_user: str) -> str:
        if not is_mistral_configured():
            return ""

        headers = {
            "Authorization": f"Bearer {MISTRAL_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = {
            "model": MISTRAL_MODEL,
            "messages": [
                {"role": "system", "content": prompt_system},
                {"role": "user", "content": prompt_user}
            ],
            "temperature": 0.2,
            "max_tokens": 1200
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                res = client.post(MISTRAL_API_URL, headers=headers, json=payload)
                res.raise_for_status()
                data = res.json()
                choices = data.get("choices", [])
                if choices and "message" in choices[0]:
                    return choices[0]["message"].get("content", "").strip()
        except Exception as e:
            print(f"Error invoking Mistral AI API ({MISTRAL_MODEL}): {e}")
            return ""

    @staticmethod
    def generate_answer(
        token: str,
        owner: str,
        repo: str,
        query: str,
        author: str = "Contributor",
        issue_number: Optional[int] = None,
        pr_number: Optional[int] = None
    ) -> Dict[str, Any]:
        # 1. Intent Classification
        intent_info = IntentClassifier.classify(query)

        # 2. Targeted Context Retrieval
        evidence = ContextRetriever.discover_context(
            token=token,
            owner=owner,
            repo=repo,
            query=query,
            intent_info=intent_info,
            issue_number=issue_number,
            pr_number=pr_number
        )

        # 3. Intent-Specific Personalized Prompt Synthesis
        system_prompt = ContextExplainer.build_system_prompt(
            intent=intent_info["intent"],
            knowledge_rules=evidence.get("knowledge_rules"),
            author=author
        )
        user_prompt = ContextExplainer.build_user_prompt(evidence, query_author=author)

        # 4. LLM Call
        llm_answer = KnowledgeAgent.call_mistral_api(system_prompt, user_prompt)

        if not llm_answer:
            llm_answer = KnowledgeAgent._fallback_answer(query, author, evidence)

        return {
            "query": query,
            "author": author,
            "intent": intent_info["intent"],
            "answer": llm_answer,
            "engine": f"Mistral AI ({MISTRAL_MODEL}) [Intent-Driven Engine]",
            "files_read": list(evidence.get("fetched_files", {}).keys())
        }

    @staticmethod
    def _fallback_answer(query: str, author: str, evidence: Dict[str, Any]) -> str:
        intent = evidence.get("intent", IntentCategory.GENERAL_QUERY)
        fetched_files = evidence.get("fetched_files", {})

        sections = [f"Hi **@{author}**, here is the engineering context tailored to your question:\n\n**Query**: *\"{query}\"*\n"]

        if intent == IntentCategory.ARCHITECTURE_UNDERSTANDING:
            sections.append("#### 🏗️ Subsystem Architecture Overview")
            if evidence.get("architecture_files"):
                sections.append("Key architecture files found:\n" + "\n".join([f"- `{f}`" for f in evidence["architecture_files"]]))
            if "README.md" in fetched_files:
                sections.append("```\n" + fetched_files["README.md"][:500] + "\n```")

        elif intent == IntentCategory.REPO_ONBOARDING:
            sections.append("#### 🎯 Cognitive Priority Tiering")
            sections.append("- **Must Understand**: Core repository rules in `KNOWLEDGE.md` and basic project structure.")
            sections.append("- **Useful Later**: Secondary module implementations.")
            sections.append("- **Ignore for Now**: Infrastructure and build pipelines.")

        elif intent == IntentCategory.PR_UNDERSTANDING and "pr" in evidence:
            pr = evidence["pr"]
            sections.append(f"#### 🔀 Pull Request #{pr.get('number')}: {pr.get('title')}")
            sections.append(f"**Description**:\n{pr.get('body') or 'No description provided.'}")

        else:
            if "KNOWLEDGE.md" in fetched_files:
                sections.append("#### 📜 Repository Guardrails (`KNOWLEDGE.md`)\n" + fetched_files["KNOWLEDGE.md"][:500])
            if "README.md" in fetched_files:
                sections.append("#### 🚀 Project Overview\n" + fetched_files["README.md"][:500])

        return "\n\n".join(sections)


# =====================================================================
# 7. HEADLESS CLI BOT ENTRYPOINT
# =====================================================================

def process_github_comment(
    access_token: str,
    owner: str,
    repo: str,
    issue_number: int,
    comment_body: str,
    comment_author: str = "Contributor"
) -> bool:
    if "@Knowledge" not in comment_body and "@knowledge" not in comment_body:
        print("No @Knowledge mention found. Skipping.")
        return False

    print(f"🤖 Processing @Knowledge context request from @{comment_author} on {owner}/{repo} #{issue_number}...")

    is_pr_target = "pr #" in comment_body.lower() or "pull request" in comment_body.lower()
    pr_num = issue_number if is_pr_target else None
    issue_num = issue_number if not is_pr_target else None

    result = KnowledgeAgent.generate_answer(
        token=access_token,
        owner=owner,
        repo=repo,
        query=comment_body,
        author=comment_author,
        issue_number=issue_num,
        pr_number=pr_num
    )

    answer_text = result.get("answer", "")
    engine_used = result.get("engine", "Mistral AI Context Layer")

    formatted_reply = f"{answer_text}\n\n---\n*🧠 Answered by @Knowledge Engineering Context Layer ({engine_used})*"

    print(f"💬 Posting reply back to GitHub {owner}/{repo} #{issue_number}...")
    success = GitHubClient.post_issue_comment(access_token, owner, repo, issue_number, formatted_reply)

    if success:
        print("🎉 Successfully posted response to GitHub!")
    else:
        print("❌ Failed to post response to GitHub.")

    return success


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Knowledge Engine CLI Runner")
    parser.add_argument("--owner", required=True, help="GitHub repository owner")
    parser.add_argument("--repo", required=True, help="GitHub repository name")
    parser.add_argument("--issue", type=int, required=True, help="Issue or PR number")
    parser.add_argument("--comment", required=True, help="Comment body containing @Knowledge")
    parser.add_argument("--token", help="GitHub OAuth or Personal Access Token")
    parser.add_argument("--author", default="Contributor", help="Author of the comment")

    args = parser.parse_args()

    token = args.token or os.getenv("GITHUB_TOKEN") or GITHUB_CLIENT_SECRET
    if not token:
        print("Error: GitHub Token required via --token or GITHUB_TOKEN environment variable.")
        sys.exit(1)

    process_github_comment(
        access_token=token,
        owner=args.owner,
        repo=args.repo,
        issue_number=args.issue,
        comment_body=args.comment,
        comment_author=args.author
    )
