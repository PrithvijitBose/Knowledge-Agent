"""
Knowledge Engine (knowledge_engine.py)
Unified Core Engine for Knowledge — The Engineering Context Layer for Repositories.

This single file contains the complete core logic:
1. Config & Environment Management
2. GitHub REST API Client (Issues, PRs, Comments, File Contents)
3. Multi-Entry Context Graph Traversal (Issue Entrypoint, PR Entrypoint, Repository Onboarding)
4. Bidirectional Issue ↔ PR Relationship Parsing
5. Cognitive Priority Tiering (Must Understand, Useful Later, Ignore for Now)
6. Guardrail-Enforced Mistral AI LLM Prompt Synthesizer
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
# 3. BIDIRECTIONAL LINK & ENTRY POINT CLASSIFIER
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


class EntryPointClassifier:
    """Classifies user prompts and starting points into Issue, PR, or Repository Onboarding entry points."""

    @staticmethod
    def classify(query: str) -> str:
        query_lower = query.lower()
        if any(keyword in query_lower for keyword in ["pr #", "pull request", "why does pr", "pr context"]):
            return "PR"
        elif any(keyword in query_lower for keyword in ["learn this codebase", "new here", "how should i learn", "onboard", "overview", "prerequisites", "where do i start"]):
            return "REPO_ONBOARDING"
        elif any(keyword in query_lower for keyword in ["issue #", "working on issue"]):
            return "ISSUE"
        return "GENERAL"


# =====================================================================
# 4. MULTI-ENTRY CONTEXT GRAPH BUILDER
# =====================================================================

class EngineeringContextGraph:
    """
    Constructs an engineering context graph around any starting point in the repository:
    - Issue Entrypoint
    - PR Entrypoint
    - Repository Onboarding Entrypoint
    """

    @staticmethod
    def build_issue_context(token: str, owner: str, repo: str, issue_number: int, query: str = "") -> Dict[str, Any]:
        issue = GitHubClient.fetch_issue(token, owner, repo, issue_number)
        if not issue:
            issue = {"number": issue_number, "title": f"Issue #{issue_number}", "body": query, "user": {"login": "Contributor"}}

        comments = GitHubClient.fetch_issue_comments(token, owner, repo, issue_number)
        combined_text = f"{issue.get('title', '')}\n{issue.get('body', '')}\n" + "\n".join([c.get('body', '') for c in comments])
        
        referenced_prs = RelationshipExtractor.extract_referenced_prs(combined_text)
        candidate_files = RelationshipExtractor.extract_referenced_files(combined_text)

        # Fetch candidate files
        fetched_files = {}
        knowledge_rules = GitHubClient.fetch_file_content(token, owner, repo, "KNOWLEDGE.md")
        if knowledge_rules:
            fetched_files["KNOWLEDGE.md"] = knowledge_rules[:3000]

        for fname in candidate_files:
            if fname in fetched_files:
                continue
            content = GitHubClient.fetch_file_content(token, owner, repo, fname)
            if content:
                fetched_files[fname] = content[:3000]

        # Fetch PR details if referenced
        prs_context = []
        for pr_num in referenced_prs:
            pr = GitHubClient.fetch_pull_request(token, owner, repo, pr_num)
            if pr:
                pr_comments = GitHubClient.fetch_pr_comments(token, owner, repo, pr_num)
                prs_context.append({"pr": pr, "comments": pr_comments})

        return {
            "type": "ISSUE",
            "issue": issue,
            "comments": comments,
            "referenced_prs": referenced_prs,
            "prs_context": prs_context,
            "fetched_files": fetched_files,
            "knowledge_rules": knowledge_rules
        }

    @staticmethod
    def build_pr_context(token: str, owner: str, repo: str, pr_number: int, query: str = "") -> Dict[str, Any]:
        pr = GitHubClient.fetch_pull_request(token, owner, repo, pr_number)
        if not pr:
            return {"error": f"Pull Request #{pr_number} not found."}

        pr_comments = GitHubClient.fetch_pr_comments(token, owner, repo, pr_number)
        changed_files = GitHubClient.fetch_pr_files(token, owner, repo, pr_number)

        combined_text = f"{pr.get('title', '')}\n{pr.get('body', '')}\n" + "\n".join([c.get('body', '') for c in pr_comments])
        linked_issues = RelationshipExtractor.extract_referenced_issues(combined_text)
        candidate_files = RelationshipExtractor.extract_referenced_files(combined_text)

        for f in changed_files:
            filename = f.get("filename")
            if filename and filename not in candidate_files:
                candidate_files.append(filename)

        fetched_files = {}
        knowledge_rules = GitHubClient.fetch_file_content(token, owner, repo, "KNOWLEDGE.md")
        if knowledge_rules:
            fetched_files["KNOWLEDGE.md"] = knowledge_rules[:3000]

        for fname in candidate_files[:8]:
            if fname in fetched_files:
                continue
            content = GitHubClient.fetch_file_content(token, owner, repo, fname)
            if content:
                fetched_files[fname] = content[:3000]

        linked_issues_context = []
        for issue_num in linked_issues:
            iss = GitHubClient.fetch_issue(token, owner, repo, issue_num)
            if iss:
                linked_issues_context.append(iss)

        return {
            "type": "PR",
            "pr": pr,
            "pr_comments": pr_comments,
            "changed_files": changed_files,
            "linked_issues": linked_issues,
            "linked_issues_context": linked_issues_context,
            "fetched_files": fetched_files,
            "knowledge_rules": knowledge_rules
        }

    @staticmethod
    def build_repo_onboarding_context(token: str, owner: str, repo: str, query: str = "") -> Dict[str, Any]:
        knowledge_rules = GitHubClient.fetch_file_content(token, owner, repo, "KNOWLEDGE.md")
        readme = GitHubClient.fetch_file_content(token, owner, repo, "README.md")
        contributing = GitHubClient.fetch_file_content(token, owner, repo, "CONTRIBUTING.md")
        reqs = GitHubClient.fetch_file_content(token, owner, repo, "requirements.txt") or GitHubClient.fetch_file_content(token, owner, repo, "package.json")
        tree = GitHubClient.fetch_repo_tree(token, owner, repo)

        fetched_files = {}
        if knowledge_rules:
            fetched_files["KNOWLEDGE.md"] = knowledge_rules[:3000]
        if readme:
            fetched_files["README.md"] = readme[:3000]
        if contributing:
            fetched_files["CONTRIBUTING.md"] = contributing[:3000]
        if reqs:
            fetched_files["DEPENDENCIES"] = reqs[:1500]

        return {
            "type": "REPO_ONBOARDING",
            "repo": f"{owner}/{repo}",
            "tree": tree[:50],
            "fetched_files": fetched_files,
            "knowledge_rules": knowledge_rules
        }


# =====================================================================
# 5. MISTRAL AI PROMPT SYNTHESIZER & KNOWLEDGE AGENT
# =====================================================================

class KnowledgeAgent:
    """Core AI synthesizer enforcing KNOWLEDGE.md rules and generating structured context answers."""

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
    def generate_answer(token: str, owner: str, repo: str, query: str, issue_number: Optional[int] = None, pr_number: Optional[int] = None) -> Dict[str, Any]:
        entry_type = EntryPointClassifier.classify(query)

        if pr_number or entry_type == "PR":
            extracted_pr_nums = RelationshipExtractor.extract_referenced_prs(query)
            target_pr = pr_number or (extracted_pr_nums[0] if extracted_pr_nums else 1)
            ctx = EngineeringContextGraph.build_pr_context(token, owner, repo, target_pr, query)
        elif entry_type == "REPO_ONBOARDING":
            ctx = EngineeringContextGraph.build_repo_onboarding_context(token, owner, repo, query)
        else:
            target_issue = issue_number or 1
            ctx = EngineeringContextGraph.build_issue_context(token, owner, repo, target_issue, query)

        knowledge_rules = ctx.get("knowledge_rules", "")

        # Formulate system prompt enforcing KNOWLEDGE.md
        if knowledge_rules:
            system_prompt = (
                "You are @Knowledge, the Engineering Context Layer for this repository.\n"
                "Your identity is NOT a code-generation bot, PR reviewer, or AI IDE.\n"
                "Your purpose is: Help a contributor understand what they need to know BEFORE they work on an unfamiliar repository.\n"
                "You MUST STRICTLY adhere to the mandatory repository guardrails below:\n\n"
                f"=== MANDATORY REPOSITORY RULES (KNOWLEDGE.md) ===\n{knowledge_rules}\n"
                "=================================================\n\n"
                "Key Directives:\n"
                "- Optimize for contributor independence and understanding, NOT writing code.\n"
                "- Source Priority: 1. Target Issue/PR info, 2. Explicitly referenced docs, 3. README/CONTRIBUTING/KNOWLEDGE.md, 4. Source code.\n"
                "- Never invent or hallucinate APIs, requirements, or architecture.\n"
                "- For Repo Onboarding: Categorize context into 3 cognitive tiers: '1. Must Understand', '2. Useful Later', '3. Ignore for Now'. Include Prerequisites and Guided Exploration Path ('Why am I reading this next?').\n"
                "- Include evidence citations for claims."
            )
        else:
            system_prompt = (
                "You are @Knowledge, the Engineering Context Layer for this repository.\n"
                "Help the contributor understand what they need to know before changing code. Do not hallucinate."
            )

        # Build user prompt based on context type
        user_prompt = f"Repository: {owner}/{repo}\nContributor Query: {query}\n\n"
        
        if ctx["type"] == "PR":
            pr = ctx.get("pr", {})
            user_prompt += f"--- TARGET PULL REQUEST #{pr.get('number')} ---\nTitle: {pr.get('title')}\nBody:\n{pr.get('body')}\n"
            if ctx.get("changed_files"):
                user_prompt += "\nChanged Files:\n" + "\n".join([f"- {f.get('filename')} (+{f.get('additions')}/-{f.get('deletions')})" for f in ctx["changed_files"]])
            if ctx.get("pr_comments"):
                user_prompt += "\nReview Discussions:\n" + "\n".join([f"- @{c.get('user',{}).get('login')}: {c.get('body')}" for c in ctx["pr_comments"][:5]])
        elif ctx["type"] == "REPO_ONBOARDING":
            user_prompt += f"--- REPOSITORY OVERVIEW ---\nTree Sample (Total files: {len(ctx.get('tree', []))}):\n"
            user_prompt += "\n".join([f"- {path}" for path in ctx.get("tree", [])[:25]])
        else:
            iss = ctx.get("issue", {})
            user_prompt += f"--- TARGET ISSUE #{iss.get('number')} ---\nTitle: {iss.get('title')}\nBody:\n{iss.get('body')}\n"
            if ctx.get("referenced_prs"):
                user_prompt += f"\nReferenced PRs: {ctx.get('referenced_prs')}\n"

        if ctx.get("fetched_files"):
            user_prompt += "\n--- REPOSITORY SOURCE FILES & DOCS ---\n"
            for fname, fcontent in ctx["fetched_files"].items():
                user_prompt += f"\nFile [{fname}]:\n{fcontent}\n"

        # Generate response using Mistral AI
        llm_answer = KnowledgeAgent.call_mistral_api(system_prompt, user_prompt)
        
        if not llm_answer:
            llm_answer = KnowledgeAgent._fallback_answer(query, ctx)

        return {
            "query": query,
            "type": ctx["type"],
            "answer": llm_answer,
            "engine": f"Mistral AI ({MISTRAL_MODEL}) [Knowledge Context Layer]",
            "files_read": list(ctx.get("fetched_files", {}).keys())
        }

    @staticmethod
    def _fallback_answer(query: str, ctx: Dict[str, Any]) -> str:
        fetched_files = ctx.get("fetched_files", {})
        sections = [f"### 🧠 Engineering Context Summary\n\n**Query**: {query}\n"]
        
        if "KNOWLEDGE.md" in fetched_files:
            sections.append("#### 📜 Repository Rules (`KNOWLEDGE.md`)\n" + fetched_files["KNOWLEDGE.md"][:600])
        if "README.md" in fetched_files:
            sections.append("#### 🚀 Repository README Overview\n" + fetched_files["README.md"][:600])

        sections.append(
            "\n#### 🎯 Cognitive Priority Tiering\n"
            "- **Must Understand**: Core architecture and `KNOWLEDGE.md` guardrails.\n"
            "- **Useful Later**: Secondary utility modules.\n"
            "- **Ignore for Now**: Infrastructure and build scripts."
        )

        return "\n\n".join(sections)


# =====================================================================
# 6. HEADLESS CLI BOT ENTRYPOINT
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

    print(f"🤖 Processing @Knowledge context request on {owner}/{repo} Issue/PR #{issue_number}...")

    # Classify whether query targets PR or Issue
    is_pr_target = "pr #" in comment_body.lower() or "pull request" in comment_body.lower()
    pr_num = issue_number if is_pr_target else None
    issue_num = issue_number if not is_pr_target else None

    result = KnowledgeAgent.generate_answer(
        token=access_token,
        owner=owner,
        repo=repo,
        query=comment_body,
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
        comment_body=args.comment
    )
