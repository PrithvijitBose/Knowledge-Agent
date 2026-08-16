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
import base64
import argparse
from typing import Dict, Any, List, Optional
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
    def fetch_repo_default_branch(token: str, owner: str, repo: str) -> str:
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}", headers=GitHubClient._get_headers(token))
                if res.status_code == 200:
                    return res.json().get("default_branch", "main")
        except Exception as e:
            print(f"GitHub API Error (fetch_repo_default_branch): {e}")
        return "main"

    @staticmethod
    def fetch_repo_tree(token: str, owner: str, repo: str, branch: Optional[str] = None) -> List[str]:
        target_branch = branch or GitHubClient.fetch_repo_default_branch(token, owner, repo)
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/trees/{target_branch}?recursive=1", headers=GitHubClient._get_headers(token))
                if res.status_code != 200 and target_branch != "main":
                    res = client.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/trees/main?recursive=1", headers=GitHubClient._get_headers(token))
                if res.status_code != 200 and target_branch != "master":
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
        return sorted(list(set(matches)))


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

        # 5. Feature Understanding
        if any(k in query_lower for k in ["feature", "implement", "how is", "how are", "functionality", "capability"]):
            return {"intent": IntentCategory.FEATURE_UNDERSTANDING, "keywords": topic_keywords}

        # 6. Historical Decision
        if any(k in query_lower for k in ["why was", "why did", "decision", "history", "originally", "changed from"]):
            return {"intent": IntentCategory.HISTORICAL_DECISION, "keywords": topic_keywords}

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
            target_pr = pr_number or (intent_info.get("pr_numbers", [])[0] if intent_info.get("pr_numbers") else None)
            if target_pr:
                pr = GitHubClient.fetch_pull_request(token, owner, repo, target_pr)
                pr_comments = GitHubClient.fetch_pr_comments(token, owner, repo, target_pr)
                changed_files = GitHubClient.fetch_pr_files(token, owner, repo, target_pr)

                evidence["pr"] = pr
                evidence["pr_comments"] = pr_comments or []
                evidence["changed_files"] = changed_files or []

                # Fetch content of key changed files
                for f in (changed_files or [])[:5]:
                    filename = f.get("filename")
                    if filename and filename not in fetched_files:
                        content = GitHubClient.fetch_file_content(token, owner, repo, filename)
                        if content:
                            fetched_files[filename] = content[:2500]
            else:
                evidence["pr"] = None
                evidence["pr_comments"] = []
                evidence["changed_files"] = []

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
            target_issue = issue_number or (intent_info.get("issue_numbers", [])[0] if intent_info.get("issue_numbers") else None)
            if target_issue:
                iss = GitHubClient.fetch_issue(token, owner, repo, target_issue)
                comments = GitHubClient.fetch_issue_comments(token, owner, repo, target_issue)
                evidence["issue"] = iss or {"number": target_issue, "title": f"Issue #{target_issue}", "body": query}
                evidence["comments"] = comments or []
            else:
                evidence["issue"] = None
                evidence["comments"] = []

            combined_text = query
            if evidence.get("issue"):
                combined_text = f"{evidence['issue'].get('title', '')}\n{evidence['issue'].get('body', '')}\n" + "\n".join([c.get('body', '') for c in evidence.get("comments", [])])
            
            ref_prs = RelationshipExtractor.extract_referenced_prs(combined_text)
            ref_files = RelationshipExtractor.extract_referenced_files(combined_text)

            evidence["referenced_prs"] = ref_prs

            for fname in ref_files[:6]:
                if fname not in fetched_files:
                    content = GitHubClient.fetch_file_content(token, owner, repo, fname)
                    if content:
                        fetched_files[fname] = content[:2500]

            if not fetched_files or len(fetched_files) <= 1:
                readme = GitHubClient.fetch_file_content(token, owner, repo, "README.md")
                if readme and "README.md" not in fetched_files:
                    fetched_files["README.md"] = readme[:2500]

        return evidence



# =====================================================================
# 5. INTENT-SPECIFIC PERSONALIZED RESPONSE SYNTHESIZER
# =====================================================================

class ContextExplainer:
    """Formats system & user prompts aligned with KNOWLEDGE.md investigation philosophy."""

    @staticmethod
    def build_system_prompt(intent: str, knowledge_rules: Optional[str], author: str = "Contributor") -> str:
        base = (
            "You are @Knowledge, an engineering context assistant for this repository.\n"
            "Act like an experienced senior engineer sitting beside @{author}, helping them understand a real codebase.\n\n"
            "Your responsibility is to investigate the repository, build a reliable mental model from the available evidence, and then teach that mental model to @{author} naturally.\n\n"
            "OPERATING PRINCIPLES:\n\n"
            "1. **Investigate before explaining**: A filename does NOT prove what role a file plays. Before making any architectural or behavioral claim, you must have inspected the actual source content. "
            "Do NOT say 'route.ts appears to be the entry point' based on the name alone — only say it if the source content demonstrates it.\n\n"
            "2. **Follow relationships, don't just collect files**: Don't stop after finding matching filenames. "
            "Trace the actual connections: entry point → function it calls → service/API it uses → data it receives → next component. "
            "The goal is to understand connections, not merely identify files.\n\n"
            "3. **Learning paths must be evidence-based**: If @{author} asks what to read first, actually investigate and construct a sequence based on dependency and conceptual flow. "
            "Do NOT return a group of files and tell the user to investigate them. Do the investigation, then teach the result.\n\n"
            "4. **Explain WHY for every recommendation**: Never say 'These are the core files.' Instead say 'Start here because this is where the request enters the system' or 'Read this next because the previous component calls into it.'\n\n"
            "5. **Build the mental model internally before writing**: Determine what the user wants to learn, which evidence is relevant, which components are connected, how they interact, and what's the smallest evidence set needed. Then produce the answer. Do NOT expose the investigation as a checklist.\n\n"
            "6. **Documentation ≠ Implementation**: Documentation explains intent. Source code establishes actual behavior. Issues/PRs provide historical context. If documentation says one thing and implementation shows another, identify the discrepancy.\n\n"
            "7. **Names are clues, not evidence**: `auth.ts` sounds like authentication — but that's a clue for investigation, not proof of behavior. Do NOT infer architecture from naming conventions.\n\n"
            "8. **No premature fallback**: If initial evidence is insufficient, investigate further (inspect imports, calls, references, connected files) before giving up. But keep investigation bounded — don't retrieve the entire repository.\n\n"
            "9. **Evidence distinction**: Distinguish between explicit evidence (repo establishes it), implementation inference (code demonstrates it), and unknown (evidence doesn't establish it). Never present inference as established fact.\n\n"
            "10. **No rigid response templates**: Do NOT force answers into predefined structures like 'Recommended Learning Path', 'Must Understand / Useful Later / Ignore for Now', 'Cognitive Priority Tiering', '30-Minute Exploration Path', or 'Architecture & Component Flow'. The answer structure should emerge from the question and what was discovered.\n\n"
            "11. **No generic filler**: Do NOT automatically include project descriptions, README summaries, generic project trees, setup instructions, CONTRIBUTING.md, or 'start with the README' unless directly relevant. Every piece of context must earn its place.\n\n"
            "12. **Natural human KT**: Be human, direct, conversational, technically precise. Don't use robotic introductions. Vary your presentation. The response should feel like an engineer who has actually investigated the repository explaining what they found.\n\n"
            "13. **Never mention agent rules**: NEVER mention, cite, or output 'KNOWLEDGE.md', system rules, anti-hallucination policies, or agent configuration in your response. Use them only internally.\n\n"
            "14. **Insufficient info**: If evidence is insufficient, state what was established, what remains unknown, and do not fill gaps with assumptions. "
            "If necessary: '> I couldn't find enough project-specific information to answer this reliably. Please contact a maintainer or ask them to provide the relevant documentation.'\n\n"
            "15. **Self-verification before answering**: Internally verify — Did I inspect actual content? Did I follow relationships? Did I distinguish evidence from inference? Did I explain WHY? "
            "If this answer could be pasted unchanged into another repo and still sound correct, it's too generic.\n\n"
            "CORE PRINCIPLE: Find relevant files → Read them → Follow their relationships → Establish evidence → Build the mental model → Teach @{author}.\n"
            "Never make @{author} perform the investigation that Knowledge was asked to perform.\n"
        )

        if knowledge_rules:
            base += f"\n=== INTERNAL EVIDENCE GUARDRAILS ===\n{knowledge_rules}\n====================================\n\n"

        if intent == IntentCategory.ISSUE_UNDERSTANDING:
            base += (
                "\nInvestigation strategy: Issue understanding.\n"
                "- Investigate the Issue body, comments, referenced PRs, and related implementation.\n"
                "- Explain what the Issue is asking, what context @{author} needs, and where to start.\n"
                "- If the Issue references files, actually retrieve and inspect those files to explain the connection.\n"
                "- If the Issue is ambiguous, identify what's missing and defer to maintainers."
            )
        elif intent == IntentCategory.PR_UNDERSTANDING:
            base += (
                "\nInvestigation strategy: PR understanding.\n"
                "- Investigate the PR description, discussion, changed files, linked Issues, and surrounding implementation.\n"
                "- Explain what changed, why, and what @{author} should inspect to understand the impact.\n"
                "- Trace the relationships between changed files — don't just list them."
            )
        elif intent == IntentCategory.REPO_ONBOARDING:
            base += (
                "\nInvestigation strategy: Repository onboarding.\n"
                "- Investigate the actual project: what it builds, its architecture, important entry points, representative flows.\n"
                "- Construct a learning order based on actual dependency/conceptual flow, and explain why each step matters.\n"
                "- Do NOT return a generic checklist. The learning path must come from the repository evidence.\n"
                "- Do NOT just list files — explain the connections between them."
            )
        elif intent == IntentCategory.ARCHITECTURE_UNDERSTANDING:
            base += (
                "\nInvestigation strategy: Architecture understanding.\n"
                "- Trace the relevant subsystem: entry points, components, state/data flow, design patterns.\n"
                "- Explain how components communicate and connect — not just what they are named.\n"
                "- Conclude with where to start tracing, and why that starting point matters."
            )
        elif intent == IntentCategory.FEATURE_UNDERSTANDING:
            base += (
                "\nInvestigation strategy: Feature understanding.\n"
                "- Trace the feature: where the flow begins, what calls what, where data comes from, where it's transformed, where the result is produced.\n"
                "- Explain how the pieces work together and where to start exploring."
            )
        elif intent == IntentCategory.CONTRIBUTION_GUIDANCE:
            base += (
                "\nInvestigation strategy: Contribution preparation.\n"
                "- Investigate relevant architecture, conventions, implementation flow, and existing discussions.\n"
                "- Help @{author} understand what they need before contributing — not just where files are."
            )
        elif intent == IntentCategory.HISTORICAL_DECISION:
            base += (
                "\nInvestigation strategy: Historical decision.\n"
                "- Investigate commit history, PR discussions, Issue threads, and documentation for evidence of why a decision was made.\n"
                "- Distinguish between what the evidence establishes vs. what you are inferring."
            )
        else:
            base += (
                "\nInvestigation strategy: General query.\n"
                "- Answer @{author}'s question directly using the most relevant repository evidence available.\n"
                "- Investigate before answering — don't just match filenames."
            )

        return base.replace("{author}", author)

    @staticmethod
    def build_user_prompt(evidence: Dict[str, Any], query_author: str = "Contributor") -> str:
        intent = evidence.get("intent", IntentCategory.GENERAL_QUERY)
        query = evidence.get("query", "")
        owner = evidence.get("owner", "")
        repo = evidence.get("repo", "")
        fetched_files = evidence.get("fetched_files", {})

        prompt = f"Repository: {owner}/{repo}\nContributor (@{query_author}) asks: {query}\nDetected intent: {intent}\n\n"

        if intent == IntentCategory.PR_UNDERSTANDING and "pr" in evidence:
            pr = evidence["pr"]
            prompt += f"--- PULL REQUEST #{pr.get('number')} ---\nTitle: {pr.get('title')}\nBody:\n{pr.get('body')}\n"
            if evidence.get("changed_files"):
                prompt += "\nChanged Files:\n" + "\n".join([f"- {f.get('filename')} (+{f.get('additions')}/-{f.get('deletions')})" for f in evidence["changed_files"]])
            if evidence.get("pr_comments"):
                prompt += "\nDiscussion:\n" + "\n".join([f"- @{c.get('user',{}).get('login')}: {c.get('body')}" for c in evidence["pr_comments"][:5]])

        elif intent == IntentCategory.ARCHITECTURE_UNDERSTANDING:
            if evidence.get("architecture_files"):
                prompt += "Architecture-related files found:\n" + "\n".join([f"- {p}" for p in evidence["architecture_files"]]) + "\n\n"
            if evidence.get("tree_sample"):
                prompt += "Repository structure:\n" + "\n".join([f"- {p}" for p in evidence["tree_sample"]]) + "\n\n"

        elif intent == IntentCategory.REPO_ONBOARDING:
            if evidence.get("tree"):
                prompt += f"Repository tree ({len(evidence['tree'])} files):\n" + "\n".join([f"- {p}" for p in evidence["tree"][:25]]) + "\n\n"

        elif "issue" in evidence and evidence["issue"]:
            iss = evidence["issue"]
            prompt += f"--- ISSUE #{iss.get('number')} ---\nTitle: {iss.get('title')}\nBody:\n{iss.get('body')}\n"
            if evidence.get("comments"):
                prompt += "\nComments:\n" + "\n".join([f"- @{c.get('user',{}).get('login')}: {c.get('body')}" for c in evidence["comments"][:5]])

        if fetched_files:
            prompt += "\n--- EVIDENCE FILES ---\n"
            for fname, fcontent in fetched_files.items():
                if fname == "KNOWLEDGE.md":
                    continue
                prompt += f"\nFile [{fname}]:\n{fcontent}\n"

        prompt += (
            f"\nAnswer @{query_author}'s question naturally. "
            "Explain what things do, why they matter, how they connect, and where to start. "
            "Do not use rigid templates or robotic introductions. "
            "Ground claims in evidence. State what's unknown."
        )
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

        # 3. Intent-Specific Prompt Synthesis
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

        discussion_comments = [
            *evidence.get("comments", []),
            *evidence.get("pr_comments", []),
        ]
        structured_context = {
            "linked_prs": evidence.get("referenced_prs", []) or ([evidence.get("pr", {}).get("number")] if evidence.get("pr") else []),
            "directives": [c.get("body", "") for c in discussion_comments if any(w in str(c.get("body", "")).lower() for w in ["don't", "must", "never", "only", "require", "do not"])],
            "referenced_files": evidence.get("fetched_files", {}),
            "fetched_files": evidence.get("fetched_files", {}),
            "intent": intent_info["intent"],
            "evidence": evidence
        }

        return {
            "query": query,
            "author": author,
            "intent": intent_info["intent"],
            "answer": llm_answer,
            "engine": f"Mistral AI ({MISTRAL_MODEL}) [Knowledge KT Engine]",
            "files_read": [k for k in evidence.get("fetched_files", {}).keys() if k != "KNOWLEDGE.md"],
            "structured_context": structured_context
        }


    @staticmethod
    def _fallback_answer(query: str, author: str, evidence: Dict[str, Any]) -> str:
        intent = evidence.get("intent", IntentCategory.GENERAL_QUERY)
        fetched_files = evidence.get("fetched_files", {})
        sections = []

        if intent == IntentCategory.ARCHITECTURE_UNDERSTANDING:
            arch_files = evidence.get("architecture_files", [])
            if arch_files:
                file_list = ", ".join([f"`{f}`" for f in arch_files[:4]])
                sections.append(f"**@{author}**, based on the repository evidence, the architecture-relevant files are: {file_list}.")
                sections.append(f"Start with `{arch_files[0]}` — it appears to be a core entry point for this subsystem. From there, trace how it connects to the other files listed above.")
            else:
                sections.append(f"**@{author}**, I wasn't able to find architecture-specific files for this subsystem in the repository.")
            if "README.md" in fetched_files:
                sections.append(f"\nThe project documentation provides additional context:\n\n{fetched_files['README.md'][:500]}")

        elif intent == IntentCategory.REPO_ONBOARDING:
            sections.append(f"**@{author}**, here is what I found about this repository.")
            if "README.md" in fetched_files:
                sections.append(f"The `README.md` explains what this project builds:\n\n{fetched_files['README.md'][:500]}")
            sections.append("\nOnce you understand the project's purpose, explore the main source directories to find the primary entry points. Trace one feature flow end-to-end before diving into secondary modules.")

        elif intent == IntentCategory.PR_UNDERSTANDING and "pr" in evidence:
            pr = evidence["pr"]
            sections.append(f"**@{author}**, Pull Request #{pr.get('number')} ({pr.get('title')}) addresses the following:")
            sections.append(f"\n{pr.get('body') or 'No description was provided for this PR.'}")
            sections.append("\nInspect the changed files in the PR to understand which components were modified and trace the impact.")

        else:
            sections.append(f"**@{author}**, here is the context I found based on the repository evidence.")
            if "README.md" in fetched_files:
                sections.append(f"\n{fetched_files['README.md'][:500]}")
            sections.append("\nStart with the main entry point files in the root directory to trace the execution flow.")

        sections.append("\n> I couldn't find enough project-specific information to answer this reliably. Please contact a maintainer or ask them to provide the relevant documentation.")

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
    if not is_pr_target and access_token:
        # Check if the target number is a pull request on GitHub
        pr_check = GitHubClient.fetch_pull_request(access_token, owner, repo, issue_number)
        if pr_check and "id" in pr_check:
            is_pr_target = True

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

    formatted_reply = f"{answer_text}\n\n---\n*🧠 Answered by Knowledge Engineering Context Layer ({engine_used})*"

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

    token = args.token or os.getenv("GITHUB_TOKEN")
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
