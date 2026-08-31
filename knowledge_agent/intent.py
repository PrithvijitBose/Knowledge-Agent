import re
from typing import Dict, Any, List


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
        from knowledge_agent.retriever import RelationshipExtractor

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

        base_result = {
            "keywords": topic_keywords,
            "pr_numbers": prs,
            "issue_numbers": issues,
            "files": files,
        }

        # 1. PR Understanding
        if prs or any(k in query_lower for k in ["why does pr", "pr #", "pull request", "pr context", "pr review"]):
            return {**base_result, "intent": IntentCategory.PR_UNDERSTANDING}

        # 2. Repo Onboarding
        if any(k in query_lower for k in ["just joined", "new here", "learn this codebase", "how should i learn", "onboard", "where do i start", "prerequisites"]):
            return {**base_result, "intent": IntentCategory.REPO_ONBOARDING}

        # 3. Contribution Guidance
        if any(k in query_lower for k in ["contribute", "run tests", "setup dev", "installation", "build", "how do i run", "how to run", "how to build", "how to test"]):
            return {**base_result, "intent": IntentCategory.CONTRIBUTION_GUIDANCE}

        # 4. Architecture Understanding
        if any(k in query_lower for k in ["architecture", "how does", "how do ", "work in this", "design", "component", "flow", "structure"]):
            if any(k in query_lower for k in ["auth", "authentication", "security", "database", "api", "routing", "workflow"]):
                return {**base_result, "intent": IntentCategory.ARCHITECTURE_UNDERSTANDING, "topic": "subsystem"}
            return {**base_result, "intent": IntentCategory.ARCHITECTURE_UNDERSTANDING, "topic": "general"}

        # 5. Feature Understanding
        if any(k in query_lower for k in ["feature", "implement", "how is", "how are", "functionality", "capability"]):
            return {**base_result, "intent": IntentCategory.FEATURE_UNDERSTANDING}

        # 6. Historical Decision
        if any(k in query_lower for k in ["why was", "why did", "decision", "history", "originally", "changed from"]):
            return {**base_result, "intent": IntentCategory.HISTORICAL_DECISION}

        # 7. Issue Understanding
        if issues or any(k in query_lower for k in ["issue #", "working on issue", "before contributing to issue", "fix issue"]):
            return {**base_result, "intent": IntentCategory.ISSUE_UNDERSTANDING}

        return {**base_result, "intent": IntentCategory.GENERAL_QUERY}
