# Knowledge Agent — LLM Integration & Behavior Contract

This document specifies the integration protocol, behavioral expectations, input/output schemas, and operating constraints for AI coding agents and LLMs integrating with **Knowledge**.

---

## 1. Purpose & Core Philosophy

**Knowledge** is a **pre-implementation context engine** for GitHub contributors and autonomous coding agents.

- **Primary Goal:** Provide factual, verified repository context and issue breakdown *before* coding begins.
- **Out of Scope:** Knowledge is **not** a speculative code generation engine. It does not create arbitrary code solutions or make unilateral architecture choices on behalf of repository maintainers.

---

## 2. Agent Interaction Protocol

When an AI coding agent begins working on an unfamiliar GitHub issue or task, it must query Knowledge prior to making file edits:

```
[GitHub Issue / Contributor Prompt]
               │
               ▼
   ┌───────────────────────┐
   │    Knowledge Agent    │
   │ (Pre-Impl Context Engine) │
   └───────────┬───────────┘
               │
               ▼ Structured Output
   ├── 1. Issue Intent & Objective
   ├── 2. Relevant Files & Architecture
   ├── 3. Verified Constraints & Invariants
   ├── 4. Open Questions & Uncertainties
   └── 5. Maintainer Escalation Points (if any)
               │
               ▼
[Implementation & Coding Phase]
```

---

## 3. Input & Output Contract

### Expected Inputs
When querying Knowledge, provide:
- `issue_url` / `issue_number` *(Required)*: The target GitHub issue reference.
- `issue_title` & `issue_body` *(Required)*: Full raw text of the issue.
- `conversation_context` *(Optional)*: Comments, maintainer directives, or triage labels.

### Expected Output Structure
Knowledge responds in a clean markdown schema:

```markdown
### 1. Objective Summary
[Concise summary of what is requested and why]

### 2. Relevant Files & Code Locations
- `path/to/component`: [Why this file is relevant]
- `path/to/tests`: [Associated test coverage location]

### 3. Key Constraints & Non-Negotiables
- [Rule 1: Dependencies to preserve]
- [Rule 2: Behavioral requirements]

### 4. Open Questions / Missing Context
- [Question 1: Ambiguity that cannot be resolved from code]

### 5. Escalation Flag
- `maintainer_decision_required`: [true | false]
- `reason`: [Explanation if true]
```

---

## 4. Grounding & Anti-Hallucination Rules

1. **Source Hierarchy:**
   1. Issue description & maintainer comments *(Highest priority)*
   2. Referenced documentation & pull requests
   3. Repository documentation (`README.md`, `CONTRIBUTING.md`, architecture docs)
   4. Current codebase implementation
2. **Strict Grounding:** Do not invent APIs, file paths, or architectural decisions. If a detail is not documented or visible in code, explicitly flag it as unknown.
3. **Escalation Trigger:** Whenever requirements conflict or an architectural ambiguity exists, state:
   > *"I couldn't find enough project-specific information to answer this reliably. Please contact a maintainer or ask them to clarify [specific point]."*

---

## 5. Agent Hard Constraints

- **Never bypass maintainer guidelines:** Do not modify protected files (e.g. CI workflows, security policies) without explicit maintainer approval.
- **Never guess business logic:** If the acceptance criteria are ambiguous, list the specific clarification questions.
- **Preserve existing style:** Adhere strictly to the project's established conventions, linters, and type annotations.

---

## 6. Example Prompts

### Querying Knowledge for Issue Onboarding
```text
Task: Onboard to Issue #42 ("Add support for custom webhook payloads")
Repository: owner/repo
Action: Query Knowledge Agent to extract relevant modules, schemas, and constraints before implementing.
```

### Knowledge Response Example
```text
Objective: Allow users to specify custom JSON payloads for outgoing webhooks.
Relevant Files:
- `src/webhooks/dispatcher.py`: Handles HTTP POST payloads
- `src/webhooks/schemas.py`: Pydantic payload models
- `tests/test_webhooks.py`: Unit test suite
Constraints: Must maintain backwards compatibility with default payload shape.
Open Questions: Should custom payloads support Jinja2 template variables? (Maintainer input recommended).
```
