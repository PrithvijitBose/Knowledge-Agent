import re
from typing import Dict, Any, List, Optional
from knowledge_agent.config import get_max_file_chars, get_max_comment_chars, get_max_diff_chars, get_max_diff_budget
from knowledge_agent.github import GitHubClient
from knowledge_agent.intent import IntentCategory


def compress_hunk_lines(lines: List[str], max_consecutive_unchanged: int = 3) -> List[str]:
    """Compresses runs of unchanged lines in a diff hunk."""
    compressed: List[str] = []
    unchanged_run: List[str] = []

    def flush_unchanged():
        nonlocal unchanged_run
        if not unchanged_run:
            return
        if len(unchanged_run) <= max_consecutive_unchanged:
            compressed.extend(unchanged_run)
        else:
            compressed.append(unchanged_run[0])
            compressed.append(unchanged_run[1])
            omitted = len(unchanged_run) - 3
            compressed.append(f"  ... [{omitted} unchanged lines omitted] ...")
            compressed.append(unchanged_run[-1])
        unchanged_run = []

    for line in lines:
        if line.startswith(" ") or line == "":
            unchanged_run.append(line)
        else:
            flush_unchanged()
            compressed.append(line)
    flush_unchanged()
    return compressed


def truncate_diff_hunk_aware(diff_text: Optional[str], max_budget: int = 14000) -> Optional[str]:
    """
    Applies a hunk-aware truncation algorithm to git unified diffs within a character budget.
    Preserves diff headers (diff --git, --- a/, +++ b/), hunk headers (@@ ... @@ [func]),
    and file paths, while compressing large unchanged blocks and truncating gracefully if
    the aggregate budget is reached.
    """
    if not diff_text:
        return diff_text

    if max_budget <= 0:
        return ""

    if len(diff_text) <= max_budget and "\n@@ " not in diff_text and not diff_text.startswith("@@ "):
        return diff_text[:max_budget]

    if "diff --git" not in diff_text and "--- " not in diff_text and "@@ " not in diff_text:
        return diff_text[:max_budget]

    raw_lines = diff_text.splitlines()
    file_diffs: List[Dict[str, Any]] = []
    current_file: Optional[Dict[str, Any]] = None
    current_hunk: Optional[Dict[str, Any]] = None

    for line in raw_lines:
        if line.startswith("diff --git ") or (line.startswith("--- ") and current_file is None):
            if current_hunk is not None and current_file is not None:
                current_file["hunks"].append(current_hunk)
                current_hunk = None
            if current_file is not None:
                file_diffs.append(current_file)
            current_file = {"header_lines": [line], "hunks": []}
        elif current_file is None:
            current_file = {"header_lines": [line], "hunks": []}
        elif line.startswith("@@ "):
            if current_hunk is not None and current_file is not None:
                current_file["hunks"].append(current_hunk)
            current_hunk = {"hunk_header": line, "lines": []}
        elif current_hunk is not None:
            current_hunk["lines"].append(line)
        else:
            if current_file is not None:
                current_file["header_lines"].append(line)

    if current_hunk is not None and current_file is not None:
        current_file["hunks"].append(current_hunk)
    if current_file is not None:
        file_diffs.append(current_file)

    result_lines: List[str] = []
    current_chars = 0
    truncated = False

    def append_omitted_msg(msg: str):
        nonlocal current_chars
        while result_lines and (current_chars + len(msg) + 1 > max_budget):
            popped = result_lines.pop()
            current_chars -= (len(popped) + 1)
        if current_chars + len(msg) + (1 if result_lines else 0) <= max_budget:
            result_lines.append(msg)
            current_chars += len(msg) + 1

    for file_idx, f_diff in enumerate(file_diffs):
        file_header_block = "\n".join(f_diff["header_lines"])
        if current_chars + len(file_header_block) + 1 > max_budget:
            remaining_files = len(file_diffs) - file_idx
            append_omitted_msg(f"... [diff truncated: {remaining_files} file(s) omitted due to character budget] ...")
            truncated = True
            break

        result_lines.append(file_header_block)
        current_chars += len(file_header_block) + 1

        for hunk_idx, hunk in enumerate(f_diff["hunks"]):
            hunk_header = hunk["hunk_header"]
            compressed_lines = compress_hunk_lines(hunk["lines"])
            hunk_block = hunk_header + ("\n" + "\n".join(compressed_lines) if compressed_lines else "")

            if current_chars + len(hunk_block) + 1 <= max_budget:
                result_lines.append(hunk_block)
                current_chars += len(hunk_block) + 1
            else:
                if current_chars + len(hunk_header) + 1 < max_budget:
                    result_lines.append(hunk_header)
                    current_chars += len(hunk_header) + 1
                    for l in compressed_lines:
                        if current_chars + len(l) + 1 <= max_budget - 50:
                            result_lines.append(l)
                            current_chars += len(l) + 1
                        else:
                            break
                remaining_hunks = len(f_diff["hunks"]) - hunk_idx
                append_omitted_msg(f"... [diff truncated: {remaining_hunks} hunk(s) omitted] ...")
                truncated = True
                break

        if truncated:
            break

    final_diff = "\n".join(result_lines)
    if len(final_diff) > max_budget:
        final_diff = final_diff[:max_budget]
    return final_diff


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
        # Position-ordered, not numerically sorted: callers that take index 0
        # as "the first referenced PR" (intent classification, the bidirectional
        # evidence chain) mean the first one mentioned in the text, and
        # "Fixes #43; Closes #12" must resolve to #43, not the lower number.
        matches: List[tuple] = []
        for pat in patterns:
            for m in re.finditer(pat, text, re.IGNORECASE):
                try:
                    matches.append((m.start(), int(m.group(1))))
                except ValueError:
                    pass
        matches.sort(key=lambda pair: pair[0])
        seen = set()
        ordered: List[int] = []
        for _, num in matches:
            if num not in seen:
                seen.add(num)
                ordered.append(num)
        return ordered

    @staticmethod
    def extract_referenced_issues(text: str) -> List[int]:
        if not text:
            return []
        patterns = [
            r'(?:Fixes|Closes|Resolves|Issue|issue)\s*#(\d+)',
            r'github\.com\/[^\/]+\/[^\/]+\/issues\/(\d+)',
            r'issues\/(\d+)'
        ]
        # Same position-ordered contract as extract_referenced_prs.
        matches: List[tuple] = []
        for pat in patterns:
            for m in re.finditer(pat, text, re.IGNORECASE):
                try:
                    matches.append((m.start(), int(m.group(1))))
                except ValueError:
                    pass
        matches.sort(key=lambda pair: pair[0])
        seen = set()
        ordered: List[int] = []
        for _, num in matches:
            if num not in seen:
                seen.add(num)
                ordered.append(num)
        return ordered

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
        max_diff = get_max_diff_budget()

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

        # Route retrieval based on Intent Category or explicitly provided PR number
        if pr_number or intent == IntentCategory.PR_UNDERSTANDING:
            intent = IntentCategory.PR_UNDERSTANDING
            evidence["intent"] = intent
            target_pr = pr_number or (intent_info.get("pr_numbers", [])[0] if intent_info.get("pr_numbers") else None)
            if target_pr:
                pr = GitHubClient.fetch_pull_request(token, owner, repo, target_pr)
                pr_comments = GitHubClient.fetch_pr_comments(token, owner, repo, target_pr)
                review_comments = GitHubClient.fetch_pr_review_comments(token, owner, repo, target_pr)
                changed_files = GitHubClient.fetch_pr_files(token, owner, repo, target_pr)
                diff = GitHubClient.fetch_pr_diff(token, owner, repo, target_pr)

                pr_head_sha = ((pr or {}).get("head") or {}).get("sha")
                if pr_head_sha:
                    evidence["commit_sha"] = pr_head_sha

                evidence["pr"] = pr
                evidence["pr_comments"] = pr_comments or []
                evidence["review_comments"] = review_comments or []
                evidence["changed_files"] = changed_files or []
                evidence["diff"] = truncate_diff_hunk_aware(diff, max_budget=max_diff) if diff else None

                # Fetch content of key changed files using PR head sha
                for f in (changed_files or [])[:5]:
                    filename = f.get("filename")
                    if filename and filename not in fetched_files:
                        content = GitHubClient.fetch_file_content(
                            token, owner, repo, filename, ref=pr_head_sha
                        )
                        if content:
                            fetched_files[filename] = content[:max_comment]

                # Follow the PR -> Issue relationship: "Fixes #43" in the PR
                # body/comments means issue #43's own context belongs in the
                # evidence too, not just the PR's own description.
                pr_text = f"{(pr or {}).get('body', '')}\n" + "\n".join(
                    c.get("body", "") for c in (pr_comments or [])
                )
                ref_issues = RelationshipExtractor.extract_referenced_issues(pr_text)
                evidence["referenced_issues"] = ref_issues
                if ref_issues:
                    linked_issue = GitHubClient.fetch_issue(token, owner, repo, ref_issues[0])
                    if linked_issue:
                        evidence["linked_issue"] = linked_issue
            else:
                evidence["pr"] = None
                evidence["pr_comments"] = []
                evidence["review_comments"] = []
                evidence["changed_files"] = []
                evidence["diff"] = None
                evidence["referenced_issues"] = []

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
                if any(kw in path_lower for kw in [*keywords, "arch", "docs", "design", "security", "auth", "core", "agent"]):
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
                evidence["issue_fetch_ok"] = iss is not None
                comments = GitHubClient.fetch_issue_comments(token, owner, repo, target_issue)
                evidence["issue"] = iss or {"number": target_issue, "title": f"Issue #{target_issue}", "body": query}
                evidence["comments"] = comments or []
            else:
                evidence["issue_fetch_ok"] = False
                evidence["issue"] = None
                evidence["comments"] = []

            combined_text = query
            if evidence.get("issue"):
                combined_text = f"{evidence['issue'].get('title', '')}\n{evidence['issue'].get('body', '')}\n" + "\n".join([c.get('body', '') for c in evidence.get("comments", [])])
            
            ref_prs = RelationshipExtractor.extract_referenced_prs(combined_text)
            ref_files = RelationshipExtractor.extract_referenced_files(combined_text)

            evidence["referenced_prs"] = ref_prs

            # Follow the Issue -> PR relationship instead of just recording
            # the numbers: fetch the first referenced PR and pull its changed
            # files in as evidence, completing Issue -> PR -> Changed Files.
            if ref_prs:
                linked_pr = GitHubClient.fetch_pull_request(token, owner, repo, ref_prs[0])
                if linked_pr:
                    evidence["linked_pr"] = linked_pr
                    # The PR's own branch, not the repo's default branch --
                    # fetching without a ref would show whatever main
                    # currently has, not what this PR actually changed.
                    pr_head_sha = (linked_pr.get("head") or {}).get("sha")
                    linked_pr_files = GitHubClient.fetch_pr_files(token, owner, repo, ref_prs[0])
                    evidence["linked_pr_files"] = linked_pr_files or []
                    for f in (linked_pr_files or [])[:5]:
                        filename = f.get("filename")
                        if filename and filename not in fetched_files:
                            content = GitHubClient.fetch_file_content(
                                token, owner, repo, filename, ref=pr_head_sha
                            )
                            if content:
                                fetched_files[filename] = content[:max_comment]

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
