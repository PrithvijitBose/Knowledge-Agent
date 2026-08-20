import re
from typing import Dict, Any, List, Optional
from knowledge_agent.config import get_max_file_chars, get_max_comment_chars, get_max_diff_chars
from knowledge_agent.github import GitHubClient
from knowledge_agent.intent import IntentCategory


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

        max_file = get_max_file_chars()
        max_comment = get_max_comment_chars()
        max_diff = get_max_diff_chars()

        knowledge_rules = GitHubClient.fetch_file_content(token, owner, repo, "KNOWLEDGE.md")
        commit_sha = GitHubClient.fetch_latest_commit_sha(token, owner, repo)
        fetched_files = {}
        if knowledge_rules:
            fetched_files["KNOWLEDGE.md"] = knowledge_rules[:max_file]

        evidence = {
            "intent": intent,
            "query": query,
            "owner": owner,
            "repo": repo,
            "commit_sha": commit_sha,
            "knowledge_rules": knowledge_rules,
            "fetched_files": fetched_files
        }

        # Route retrieval based on Intent Category
        if intent == IntentCategory.PR_UNDERSTANDING:
            target_pr = pr_number or (intent_info.get("pr_numbers", [])[0] if intent_info.get("pr_numbers") else None)
            if target_pr:
                pr = GitHubClient.fetch_pull_request(token, owner, repo, target_pr)
                pr_comments = GitHubClient.fetch_pr_comments(token, owner, repo, target_pr)
                review_comments = GitHubClient.fetch_pr_review_comments(token, owner, repo, target_pr)
                changed_files = GitHubClient.fetch_pr_files(token, owner, repo, target_pr)
                diff = GitHubClient.fetch_pr_diff(token, owner, repo, target_pr)

                evidence["pr"] = pr
                evidence["pr_comments"] = pr_comments or []
                evidence["review_comments"] = review_comments or []
                evidence["changed_files"] = changed_files or []
                evidence["diff"] = diff[:max_file] if diff else None

                # Fetch content of key changed files
                for f in (changed_files or [])[:5]:
                    filename = f.get("filename")
                    if filename and filename not in fetched_files:
                        content = GitHubClient.fetch_file_content(token, owner, repo, filename)
                        if content:
                            fetched_files[filename] = content[:max_comment]
            else:
                evidence["pr"] = None
                evidence["pr_comments"] = []
                evidence["review_comments"] = []
                evidence["changed_files"] = []
                evidence["diff"] = None

        elif intent == IntentCategory.REPO_ONBOARDING:
            readme = GitHubClient.fetch_file_content(token, owner, repo, "README.md")
            contributing = GitHubClient.fetch_file_content(token, owner, repo, "CONTRIBUTING.md")
            reqs = GitHubClient.fetch_file_content(token, owner, repo, "requirements.txt") or GitHubClient.fetch_file_content(token, owner, repo, "package.json")
            tree = GitHubClient.fetch_repo_tree(token, owner, repo)

            if readme:
                fetched_files["README.md"] = readme[:max_file]
            if contributing:
                fetched_files["CONTRIBUTING.md"] = contributing[:max_file]
            if reqs:
                fetched_files["DEPENDENCIES"] = reqs[:max_diff]

            evidence["tree"] = tree[:40]

        elif intent == IntentCategory.ARCHITECTURE_UNDERSTANDING:
            tree = GitHubClient.fetch_repo_tree(token, owner, repo)
            readme = GitHubClient.fetch_file_content(token, owner, repo, "README.md")
            if readme:
                fetched_files["README.md"] = readme[:max_file]

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
                        fetched_files[path] = content[:max_comment]

            evidence["architecture_files"] = architecture_candidates
            evidence["tree_sample"] = [p for p in tree if "/" not in p or p.count("/") <= 1][:30]

        elif intent == IntentCategory.FEATURE_UNDERSTANDING or intent == IntentCategory.HISTORICAL_DECISION:
            tree = GitHubClient.fetch_repo_tree(token, owner, repo)
            readme = GitHubClient.fetch_file_content(token, owner, repo, "README.md")
            if readme:
                fetched_files["README.md"] = readme[:max_comment]

            matching_files = [p for p in tree if any(kw in p.lower() for kw in keywords)][:5]
            for path in matching_files:
                if path not in fetched_files:
                    content = GitHubClient.fetch_file_content(token, owner, repo, path)
                    if content:
                        fetched_files[path] = content[:max_comment]

            evidence["matching_files"] = matching_files

        elif intent == IntentCategory.CONTRIBUTION_GUIDANCE:
            contributing = GitHubClient.fetch_file_content(token, owner, repo, "CONTRIBUTING.md")
            readme = GitHubClient.fetch_file_content(token, owner, repo, "README.md")
            reqs = GitHubClient.fetch_file_content(token, owner, repo, "requirements.txt") or GitHubClient.fetch_file_content(token, owner, repo, "package.json")

            if contributing:
                fetched_files["CONTRIBUTING.md"] = contributing[:max_file]
            if readme:
                fetched_files["README.md"] = readme[:max_comment]
            if reqs:
                fetched_files["DEPENDENCIES"] = reqs[:max_diff]

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
                        fetched_files[fname] = content[:max_comment]

            if not fetched_files or len(fetched_files) <= 1:
                readme = GitHubClient.fetch_file_content(token, owner, repo, "README.md")
                if readme and "README.md" not in fetched_files:
                    fetched_files["README.md"] = readme[:max_comment]

        return evidence

    # Aliases
    retrieve_context = discover_context
