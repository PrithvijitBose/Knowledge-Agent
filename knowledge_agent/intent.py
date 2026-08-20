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
