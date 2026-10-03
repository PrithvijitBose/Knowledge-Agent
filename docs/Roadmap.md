# Roadmap — Knowledge Agent Development

This document tracks what **Knowledge already does**, what is **currently being refined**, and where the project can go in the future.

---

## 🟢 Done

| Title | Meaning | Example | Status |
|---|---|---|---|
| **Repository Knowledge** | Understand and investigate an unfamiliar repository using its actual sources. | “Explain how authentication works in this repo.” | `Done` |
| **Issue Context** | Use issue titles, descriptions, and comments as engineering context. | “What do I need to understand before working on Issue #42?” | `Done` |
| **PR Context** | Include Pull Requests and their discussions as part of repository understanding. | “What does this PR change and which issue is it related to?” | `Done` |
| **Repository Investigation** | Search beyond a single issue and identify relevant files and components. | “Where should I start investigating this issue?” | `Done` |
| **Evidence & Source Attribution** | Connect important claims to actual repository evidence. | `backend/app/main.py`, line 10 | `Done` |
| **Anti-Hallucination Handling** | Refuse to invent information when the repository doesn't provide enough evidence. | “I couldn't find evidence for JWT implementation.” | `Done` |
| **Unknown Detection** | Explicitly identify information that could not be verified. | “Unknown: no evidence of GitHub OAuth implementation.” | `Done` |
| **Adaptive Technicality Calibration** | Internal 1–10 depth point calibration dynamically tailoring explanations from conceptual to low-level implementation. | “Explain simpler” vs “Explain AST bytecode & endpoints” | `Done` |
| **Cross-Repository Intelligence** | Cross-repository context discovery and relationship tracing across companion services (frontend, backend, shared packages). | “Is layout.tsx connected to which endpoint in the backend repo?” | `Done` |
| **Context Relationships** | Reliably follow bidirectional relationships between issues, PRs, files, documentation, and implementation. | `Issue → PR → Changed Files → Component` | `Done` |
| **Intent-Aware Investigation** | Classify contributor intent into dedicated categories to dynamically guide context discovery and retrieval. | “I need to fix this issue” → investigate the issue's relevant code first. | `Done` |
| **Persistent Repository Memory** | Retain useful engineering context so Knowledge doesn't repeatedly rediscover the same information across queries. | “We already understood authentication. Now explain authorization.” | `Done` |
| **Documentation vs Implementation** | Cross-reference documentation claims against source code AST, routes, and symbols to surface discrepancies and drift. | README says OAuth exists → verify the implementation in code AST. | `Done` |

---

## 🟡 Ongoing

| Title | Meaning | Example | Status |
|---|---|---|---|
| **Human Engineering KT** | Make Knowledge consistently explain code like an experienced engineer rather than producing templates. | “Explain how the landing page works and why these components connect.” | `Ongoing` |
| **Contribution Guidance** | Help contributors understand where and how to investigate without prematurely prescribing a solution. | “Where should I start?” → provide an investigation path. | `Ongoing` |
| **Repository Learning Paths** | Turn repository investigation into a practical learning sequence for new contributors. | “I just joined. What should I learn first?” | `Ongoing` |

---

## 🔵 Future

| Title | Meaning | Example | Status |
|---|---|---|---|
| **Interactive Repository Learning** | Let contributors progressively learn a repository through an interactive KT experience. | “Teach me this repository in 30 minutes.” | `Future` |
| **Team Engineering Intelligence** | Help teams understand project areas, contribution activity, and engineering context. | “Which parts of this project are actively being worked on?” | `Future` |
| **Engineering Context Platform** | Evolve Knowledge from a GitHub bot into a general engineering-context layer for developers. | “I'm new here. Teach me the repo, explain this issue, trace the code, and explain the PR solving it.” | `Future` |

---

## Vision

```text
DONE
Repository Understanding
        ↓
Issue + PR Context
        ↓
Evidence Grounding & Citations
        ↓
Adaptive Technicality Calibration
        ↓
Cross-Repository Intelligence
        ↓
Context Relationships (Issue ↔ PR ↔ Files)
        ↓
Intent-Aware Investigation
        ↓
Persistent Repository Memory
        ↓
Documentation vs Implementation Verification
        ↓
ONGOING
Human Engineering KT
        ↓
Contribution Guidance
        ↓
Repository Learning Paths
        ↓
FUTURE
Interactive Repository Learning
        ↓
Team Engineering Intelligence
        ↓
Engineering Context Platform
```
