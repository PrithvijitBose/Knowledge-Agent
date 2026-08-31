import re
from typing import Dict, Any, Optional
import providers
import memory_store
from knowledge_agent.github import GitHubClient
from knowledge_agent.intent import IntentCategory, IntentClassifier
from knowledge_agent.retriever import ContextRetriever
from knowledge_agent.prompt import ContextExplainer
from knowledge_agent.citations import CitationFormatter
from knowledge_agent.tracer import ExecutionTracer


class KnowledgeAgent:
    """Core AI synthesizer using intent-driven context selection and LLM providers."""

    @staticmethod
    def call_mistral_api(prompt_system: str, prompt_user: str) -> str:
        """Invokes Mistral AI API for backward compatibility."""
        return providers.MistralProvider().generate(prompt_system, prompt_user)

    @staticmethod
    def call_llm(
        prompt_system: str,
        prompt_user: str,
        provider_name: Optional[str] = None,
        model: Optional[str] = None
    ) -> str:
        """Invokes the active or specified LLM provider."""
        provider = providers.get_provider(provider_name, model=model)
        return provider.generate(prompt_system, prompt_user)

    @staticmethod
    def generate_answer(
        token: str,
        owner: str,
        repo: str,
        query: str,
        author: str = "Contributor",
        issue_number: Optional[int] = None,
        pr_number: Optional[int] = None,
        provider_name: Optional[str] = None,
        model: Optional[str] = None,
        depth_score: Optional[int] = None,
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

        # 2.5. Persistent Repository Memory (#6)
        memory = memory_store.MemoryStore()
        prior_entry = memory.get(owner, repo, intent_info["intent"], intent_info.get("keywords", []))
        if prior_entry:
            evidence["prior_context"] = {
                "summary": prior_entry.get("summary", ""),
                "files_read": prior_entry.get("files_read", []),
                "stale": memory.is_stale(prior_entry, evidence.get("commit_sha")),
            }

        # 3. Intent-Specific Prompt Synthesis
        if depth_score is None:
            try:
                from adaptive_depth import AdaptiveDepthEngine

                history_texts = []
                if evidence.get("comments"):
                    history_texts.extend([c.get("body", "") for c in evidence["comments"] if isinstance(c, dict)])
                if evidence.get("pr_comments"):
                    history_texts.extend([c.get("body", "") for c in evidence["pr_comments"] if isinstance(c, dict)])
                depth_score = AdaptiveDepthEngine().calculate_depth(query, history=history_texts if history_texts else None)
            except ImportError:
                pass

        system_prompt = ContextExplainer.build_system_prompt(
            intent=intent_info["intent"],
            knowledge_rules=evidence.get("knowledge_rules"),
            author=author,
            depth_score=depth_score,
        )
        user_prompt = ContextExplainer.build_user_prompt(evidence, query_author=author)

        # 4. LLM Call via Provider Router
        provider = providers.get_provider(provider_name, model=model)
        llm_answer = KnowledgeAgent.call_llm(system_prompt, user_prompt, provider_name=provider_name, model=model)

        files_read = [k for k in evidence.get("fetched_files", {}).keys() if k != "KNOWLEDGE.md"]
        cross_repo_evidence = evidence.get("cross_repo_evidence")

        has_issue_evidence = evidence.get("issue_fetch_ok") is True
        if llm_answer and (files_read or has_issue_evidence or evidence.get("pr") or cross_repo_evidence):
            memory.put(
                owner, repo, intent_info["intent"], intent_info.get("keywords", []),
                summary=llm_answer, files_read=files_read, commit_sha=evidence.get("commit_sha"),
            )

        if not llm_answer:
            llm_answer = KnowledgeAgent._fallback_answer(query, author, evidence)
        citations_text = CitationFormatter.build_citations_section(
            owner, repo, evidence.get("commit_sha"), files_read, cross_repo_files=cross_repo_evidence
        )

        discussion_comments = [
            *evidence.get("comments", []),
            *evidence.get("pr_comments", []),
        ]
        structured_context = {
            "linked_prs": evidence.get("referenced_prs", []) or ([evidence.get("pr", {}).get("number")] if evidence.get("pr") else []),
            "directives": [c.get("body", "") for c in discussion_comments if any(w in str(c.get("body", "")).lower() for w in ["don't", "must", "never", "only", "require", "do not"])],
            "referenced_files": evidence.get("fetched_files", {}),
            "fetched_files": evidence.get("fetched_files", {}),
            "cross_repo_evidence": cross_repo_evidence,
            "intent": intent_info["intent"],
            "evidence": evidence,
        }

        return {
            "query": query,
            "author": author,
            "intent": intent_info["intent"],
            "depth_score": depth_score,
            "answer": llm_answer,
            "citations": citations_text,
            "commit_sha": evidence.get("commit_sha"),
            "engine": f"{provider.name.capitalize()} AI ({provider.model}) [Knowledge KT Engine]",
            "files_read": files_read,
            "structured_context": structured_context,
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


def is_bot_triggered(comment_body: str) -> bool:
    """
    Checks whether a comment text contains a valid '@knowledge' or '/knowledge' command token.
    Uses boundary matching to avoid matching substrings in URLs or emails (e.g. not@knowledge.com).
    """
    if not comment_body:
        return False
    pattern = r'(?i)(?:^|[\s\(\[\{<"\'])((?:@|/)knowledge)(?:$|[\s\)\]\}>"\'\.,!?:;])'
    return bool(re.search(pattern, comment_body))


def process_github_comment(
    access_token: str,
    owner: str,
    repo: str,
    issue_number: int,
    comment_body: str,
    comment_author: str = "Contributor",
    target_type: Optional[str] = None
) -> bool:
    if not is_bot_triggered(comment_body):
        print("No @Knowledge or /knowledge trigger found. Skipping.")
        return False

    tracer = ExecutionTracer(owner, repo, issue_number, comment_author)
    print(f"🤖 Processing Knowledge context request from @{comment_author} on {owner}/{repo} #{issue_number}...")

    success = False
    result: Dict[str, Any] = {}
    try:
        is_pr_target = False
        if target_type == "pull_request":
            is_pr_target = True
        elif target_type == "issue":
            is_pr_target = False
        elif access_token:
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
        citations_text = result.get("citations", "")
        engine_used = result.get("engine", "Mistral AI Context Layer")
        formatted_reply = f"{answer_text}{citations_text}\n\n---\n*🧠 Answered by Knowledge Engineering Context Layer ({engine_used})*"

        print(f"💬 Posting reply back to GitHub {owner}/{repo} #{issue_number}...")
        success = GitHubClient.post_issue_comment(access_token, owner, repo, issue_number, formatted_reply)

        if success:
            print("🎉 Successfully posted response to GitHub!")
        else:
            print("❌ Failed to post response to GitHub.")

        return success
    finally:
        tracer.finish(success, result)
