<div align="center">

# 🧠 Knowledge

**The Engineering Context Layer for Repositories. Native GitHub Bot & MCP Server.**

*Transform raw PR diffs, complex issue threads, and distributed architectures into grounded, hallucination-free engineering handoffs and developer context.*

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Model Context Protocol](https://img.shields.io/badge/MCP-Native_Server-7C3AED?style=for-the-badge&logo=anthropic&logoColor=white)](https://modelcontextprotocol.io/)
[![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-Bot_Runtime-2088FF?style=for-the-badge&logo=githubactions&logoColor=white)](https://github.com/features/actions)
[![FastAPI](https://img.shields.io/badge/FastAPI-Webhook_Server-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-Dashboard-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Multi-LLM](https://img.shields.io/badge/Multi--LLM-Mistral_•_OpenAI_•_Claude_•_Gemini_•_Groq_•_Ollama-FD6F00?style=for-the-badge)](https://github.com/PrithvijitBose/Knowledge-Agent)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)

[📖 **Integration Guide**](docs/Integration.md) • [🔌 **MCP Server Guide**](docs/MCP.md) • [🗺️ **Roadmap**](docs/Roadmap.md) • [📜 **KNOWLEDGE.md Specification**](KNOWLEDGE.md)

</div>

---

## The Problem (and how we are solving it)

| 📄 Generic Bots & Chat LLMs | 🧠 Knowledge Engineering Context Layer |
| :--- | :--- |
| **Hallucinated Code**: Confidently invents non-existent APIs, endpoints, and arguments. | **Strict Evidence Grounding**: Every claim cites verified lines: `[repo:path/file.py#L1-L20]`. Unverified claims are explicitly stamped "Unknown". |
| **Siloed & Single-Repo**: Incapable of tracing cross-service contracts or companion repos. | **Cross-Repository Intelligence**: Discovers trees & traces contracts across frontend, backend, and shared microservices. |
| **Silent Documentation Drift**: Stale READMEs and guides trick new engineers into broken setups. | **AST Doc-Verifier**: Statically cross-references docs against Python/TypeScript AST and route symbols to surface discrepancies. |
| **One-Size-Fits-All Jargon**: Dumps confusing code dumps to beginners or trivial fluff to seniors. | **Adaptive Depth Calibration**: 1–10 point system dynamically scales explanation from conceptual analogies to AST/schema traces. |
| **Context Overflows & Bloat**: Dumps unconstrained files into prompts, blowing token budgets. | **Hunk-Aware Bounded Context**: Strict char and diff budgeting extracts high-signal diff chunks and conversation threads. |
| **Walled Garden**: Locked exclusively into a single web chat UI or browser tab. | **Universal Interface**: Native GitHub Bot (Actions/Webhook), stdio/SSE MCP Server (Cursor/Claude), CLI, and Streamlit UI. |

> *"Software engineers spend up to 60% of their time deciphering undocumented PRs, tracing distributed services, and debugging stale documentation. Knowledge bridges the gap between raw codebase reality and high-signal, verified engineering handoffs."*

---

## What Knowledge is

Knowledge is an open-source engineering context layer designed to run natively inside your developer workflows. 

When a contributor or maintainer comments `@Knowledge <question>` or `/knowledge <question>` on any GitHub Issue or Pull Request, Knowledge:
1. **Classifies query intent** across 7 engineering categories.
2. **Retrieves bounded, hunk-aware evidence** across repository files, companion services, and discussion threads.
3. **Cross-references claims & AST symbols** to verify implementation against documentation.
4. **Enforces repository guardrails** parsed directly from `KNOWLEDGE.md`.
5. **Calibrates technical depth** (1–10 internal score) based on the user's inquiry style.
6. **Posts a structured engineering handoff** directly back into GitHub with exact line citations.

For AI coding agents (Cursor, Claude Desktop, Claude Code, Windsurf, Devin), Knowledge acts as a **Native Model Context Protocol (MCP) Server**, feeding real repository context instead of letting agents guess at your architecture.

---

### ✨ Core Pillars

* 🛡️ **Zero-Hallucination & Strict Line Citations**: Every claim is backed by immutable Git references, file lines, or commit diffs. Missing information is explicitly stamped as `"Unknown"`.
* 🎯 **Adaptive Technicality Calibration**: Dynamic 1–10 scoring engine scales context from high-level architectural analogies (1–3) to low-level AST, SQL schema, and HTTP endpoint traces (7–10) without leaking point values.
* 🌐 **Cross-Repository Intelligence**: Automatically connects companion repositories (e.g. tracing a React `layout.tsx` to a backend FastAPI endpoint or shared auth service).
* 🔍 **AST Doc-Verifier & Anti-Drift Engine**: Statically inspects Python and TypeScript AST to detect discrepancies between written documentation and actual code signatures.
* 🔌 **Native Model Context Protocol (MCP)**: Exposes architecture exploration, doc drift verification, and issue/PR lineage tools to modern IDE agents over stdio or SSE transports.
* 📜 **Maintainer Guardrail Enforcement**: Parses repository guidelines and protected boundary directives from `KNOWLEDGE.md` directly into the LLM system prompt.
* ⚡ **Multi-LLM Provider Architecture**: Zero-bloat REST adapters for Mistral AI, OpenAI, Anthropic Claude, Google Gemini, Groq, and local Ollama without heavy external SDK lock-in.

---

## 🚧 Current Stage

Knowledge is currently at **v0.3.1**, with its core evidence engine, multi-provider support, and MCP server fully active in production.

* 🟢 **Completed**: Native GitHub bot interactions, multi-LLM adapters (Mistral, OpenAI, Claude, Gemini, Groq, Ollama), bounded context retriever, AST doc-verifier, multi-repository intelligence, persistent repository memory, and Model Context Protocol (MCP) server.
* 🟡 **In Progress**: Human engineering Knowledge Transfer (KT) phrasing, interactive contribution guidance paths, and multi-file code drift auto-patching.
* 🔵 **Upcoming**: Repository learning roadmaps ("Teach me this repo in 30 minutes"), team engineering activity graphs, and unified engineering context platform.

*We build in the open. Feature requests, architecture feedback, and pull requests are welcomed!*

---

## System Architecture

```
                       ┌──────────────────────────────────────────────────────────┐
                       │                     DEVELOPER INPUT                      │
                       └────────────────────────────┬─────────────────────────────┘
                                                    │
         ┌──────────────────────────────────┬───────┴──────────┬─────────────────────────────────┐
         ▼                                  ▼                  ▼                                 ▼
┌───────────────────┐             ┌───────────────────┐┌───────────────────┐             ┌───────────────────┐
│ 🐙 GITHUB ACTION  │             │ 🔌 MCP SERVER     ││ ⚡ WEBHOOK SERVER │             │ 📊 STREAMLIT UI   │
│ Issue / PR Comment│             │ Cursor / Claude   ││ FastAPI (HMAC-256)│             │ Interactive Graph │
└─────────┬─────────┘             └─────────┬─────────┘└─────────┬─────────┘             └─────────┬─────────┘
          │                                 │                    │                                 │
          └─────────────────────────────────┴──────────┬─────────┴─────────────────────────────────┘
                                                       │
                                                       ▼
                                     ┌───────────────────────────────────┐
                                     │     INTENT CLASSIFIER (7 Modes)   │
                                     │  PR, Issue, Architecture, Onboard │
                                     └─────────────────┬─────────────────┘
                                                       │
                                                       ▼
                                     ┌───────────────────────────────────┐
                                     │     BOUNDED CONTEXT RETRIEVER     │
                                     │  Hunk-Aware Diff • Companion Repos│
                                     │  KNOWLEDGE.md Rules • AST Symbols │
                                     └─────────────────┬─────────────────┘
                                                       │
                                                       ▼
                                     ┌───────────────────────────────────┐
                                     │   ADAPTIVE DEPTH CALIBRATION      │
                                     │   1-10 Dynamic Technicality Score │
                                     └─────────────────┬─────────────────┘
                                                       │
                                                       ▼
                                     ┌───────────────────────────────────┐
                                     │     MULTI-LLM REST ENGINE         │
                                     │ Mistral • OpenAI • Claude • Ollama│
                                     └─────────────────┬─────────────────┘
                                                       │
                                                       ▼
                                     ┌───────────────────────────────────┐
                                     │   GROUNDED ENGINEERING HANDOFF    │
                                     │ Scope • Verification • Guardrails │
                                     │ Repository Line-Scoped Citations  │
                                     └───────────────────────────────────┘
```

---

## Deployment & Integration Models

Knowledge offers flexible integration pathways to match your workflow requirements:

```
                      ┌─────────────────────────────────────────────────────────┐
                      │              CHOOSE YOUR ACCESS MODEL                   │
                      └────────────────────────────┬────────────────────────────┘
                                                   │
         ┌─────────────────────────────────┼─────────────────────────────────┐
         ▼                                 ▼                                 ▼
┌───────────────────┐             ┌───────────────────┐             ┌───────────────────┐
│ 🟢 GITHUB ACTIONS │             │ 🟡 MCP SERVER     │             │ 🔵 WEBHOOK DAEMON │
│ 1-Minute Setup    │             │ Cursor & Claude   │             │ Dedicated Server  │
│ Zero-Config CI    │             │ Local IDE Agent   │             │ Custom Domain/App │
└───────────────────┘             └───────────────────┘             └───────────────────┘
```

| Deployment Tier | Best For | Prerequisites | Security Model |
| :--- | :--- | :--- | :--- |
| 🟢 **GitHub Actions** | Any GitHub repository (Issues & PRs) | Copy `.github/workflows/knowledge.yml` | Standard GitHub Actions token isolation |
| 🟡 **Native MCP Server** | Cursor, Claude Desktop, Claude Code | `pip install -e ".[mcp]"` | Local stdio or authenticated SSE stream |
| 🔵 **FastAPI Webhook** | High-volume organizations & real-time bots | Python 3.10+ server / container | HMAC-SHA256 GitHub signature verification |
| 🟣 **Streamlit Dashboard** | Local context exploration & visual graphs | `pip install -e ".[dashboard]"` | Local developer sandbox environment |

---

## ⚡ 1-Minute GitHub Action Setup

The fastest way to install Knowledge Bot into any repository is copying the workflow and adding your rulebook:

```text
Your-Repo/
├── .github/workflows/
│   └── knowledge.yml       # Copied from templates/knowledge.yml
├── knowledge_agent/        # Core package directory (copied whole)
├── knowledge_engine.py     # Unified core engine facade
└── KNOWLEDGE.md            # Repository rulebook & maintainer directives
```

> 💡 **Automated Setup Prompt**: Have Cursor or Claude Code do it for you! Simply paste [docs/Integration.md](docs/Integration.md) into your coding assistant.

### 🔐 Configure Repository Secret

Navigate to **Settings ➔ Secrets and variables ➔ Actions** in your repository and configure your preferred provider API key:

| Secret Name | Provider | Default Model | Environment Variable Override |
| :--- | :--- | :--- | :--- |
| `MISTRAL_API_KEY` | Mistral AI | `mistral-small-2506` | `MISTRAL_MODEL` |
| `OPENAI_API_KEY` | OpenAI | `gpt-4o-mini` | `OPENAI_MODEL` |
| `ANTHROPIC_API_KEY` | Anthropic Claude | `claude-3-5-haiku-20241022` | `ANTHROPIC_MODEL` |
| `GEMINI_API_KEY` | Google Gemini | `gemini-1.5-flash` | `GEMINI_MODEL` |
| `GROQ_API_KEY` | Groq Ultra-Fast | `llama-3.3-70b-versatile` | `GROQ_MODEL` |

### 💬 Triggering the Bot

Comment on any Issue or Pull Request:
```text
@Knowledge How is authentication wired between the frontend and backend in this repo?
```
```text
/knowledge Explain the changes in this PR and how to test them locally.
```

<details>
<summary><b>🛠️ Click here for Advanced Multi-Repo & Local Ollama Configurations</b></summary>

#### Multi-Repository Intelligence
To allow Knowledge to investigate companion repositories, declare them in `KNOWLEDGE.md`:
```markdown
## Related Repositories
- `acme/backend-api`: Core FastAPI backend, database models, and REST endpoints
- `acme/shared-ui`: Cross-project design system components
```
Or via environment variable:
```bash
export KNOWLEDGE_RELATED_REPOS="acme/backend-api, acme/shared-ui"
```

#### Air-Gapped Local Execution with Ollama
Run Knowledge completely offline without sending code to third-party APIs:
```bash
export LLM_PROVIDER=ollama
export OLLAMA_HOST=http://localhost:11434
export OLLAMA_MODEL=llama3.2:latest
```

#### Bounded Evidence Budgets
Fine-tune character truncation limits:
```bash
export KNOWLEDGE_MAX_FILE_CHARS=3000      # Primary files (README, KNOWLEDGE.md)
export KNOWLEDGE_MAX_COMMENT_CHARS=2500   # Code and architecture matches
export KNOWLEDGE_MAX_DIFF_CHARS=1500      # Manifest files and diffs
```
</details>

---

## 🔌 MCP Server (Cursor, Claude Desktop & Coding Agents)

Knowledge exposes its bounded evidence engine, AST doc-verifier, and issue/PR lineage directly to AI coding assistants via the [Model Context Protocol](https://modelcontextprotocol.io).

### Installation & Launch

```bash
# Install with MCP dependencies
pip install -e ".[mcp]"

# stdio transport (Cursor, Claude Desktop, Claude Code)
knowledge-agent mcp --stdio

# Or SSE transport (Shared or daemon instances)
knowledge-agent mcp --sse --host 127.0.0.1 --port 8765
```

### Configuration Snippets

<details open>
<summary><b>Claude Desktop (<code>claude_desktop_config.json</code>)</b></summary>

```json
{
  "mcpServers": {
    "knowledge": {
      "command": "knowledge-agent",
      "args": ["mcp", "--stdio"],
      "env": {
        "GITHUB_TOKEN": "ghp_your_github_pat_token",
        "KNOWLEDGE_OWNER": "your-org",
        "KNOWLEDGE_REPO": "your-repo"
      }
    }
  }
}
```
</details>

<details open>
<summary><b>Cursor (<code>.cursor/mcp.json</code>)</b></summary>

```json
{
  "mcpServers": {
    "knowledge": {
      "command": "knowledge-agent",
      "args": ["mcp", "--stdio"],
      "env": {
        "GITHUB_TOKEN": "ghp_your_github_pat_token",
        "KNOWLEDGE_OWNER": "your-org",
        "KNOWLEDGE_REPO": "your-repo"
      }
    }
  }
}
```
</details>

**Exposed MCP Tools:**
* `knowledge_get_architecture_context(query, repo_path)` — Grounded mental model and evidence chain for any subsystem.
* `knowledge_verify_doc_drift(doc_path, code_dir)` — AST discrepancy detection between documentation claims and code symbols.
* `knowledge_trace_issue_pr(issue_or_pr_number)` — Lineage tracing between issue discussions, PR diffs, and affected components.

*(Full tool signatures and SSE guides: [docs/MCP.md](docs/MCP.md))*

---

## 📊 Streamlit Dashboard & Webhook Server

### Interactive Streamlit Dashboard
Inspect repository context graphs, test query classifications, and visualize evidence clusters:
```bash
streamlit run apps/app.py
```

### Production FastAPI Webhook Server
Deploy real-time webhook endpoints with HMAC-SHA256 signature verification:
```bash
# Start FastAPI Webhook daemon on port 8000
python apps/webhook_server.py
```
> Set `GITHUB_WEBHOOK_SECRET` in your environment to automatically enforce cryptographic HMAC signature validation on all incoming GitHub webhooks.

---

## How to Contribute

Whether you are improving prompt fencing, expanding AST support to more languages, adding LLM adapters, or refining documentation—contributions are warmly welcomed!

### ⚡ Quick Start in 3 Steps

#### 1. Clone the Repository
```bash
git clone https://github.com/PrithvijitBose/Knowledge-Agent.git
cd Knowledge-Agent
```

#### 2. Set Up Virtual Environment & Dependencies
```bash
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux: source .venv/bin/activate

pip install -e ".[dev,mcp,dashboard,server]"
```

#### 3. Test CLI & Verify Help Output
```bash
knowledge-agent --help
# Or: python -m knowledge_agent --help
```

---

### 🧪 Running Tests

The test suite is **100% hermetic and offline** (utilizing mock fixtures and zero external network dependencies):

```bash
# Run the complete test suite (270+ tests)
python -m pytest

# Run specific test modules
python -m pytest tests/test_adaptive_depth.py
python -m pytest tests/test_doc_verifier.py
python -m pytest tests/test_mcp_server.py
```

---

### 🌿 Contribution Workflow

1. Create a feature branch: `git checkout -b feature/grounded-improvement`
2. Commit with conventional commit messages: `git commit -m "feat(retriever): add AST support for Go interfaces"`
3. Verify test suite passes: `python -m pytest`
4. Push your branch and open a Pull Request on GitHub.

---

## Community & Discussions

Connect with fellow contributors, suggest features, and get live help:

<div align="center">

[![GitHub Issues](https://img.shields.io/badge/GitHub-Issues-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/PrithvijitBose/Knowledge-Agent/issues)
[![GitHub Discussions](https://img.shields.io/badge/GitHub-Discussions-0969DA?style=for-the-badge&logo=github&logoColor=white)](https://github.com/PrithvijitBose/Knowledge-Agent/discussions)
[![Discord](https://img.shields.io/badge/Discord-Join_Community-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discord.gg/XkvEYcEba)

</div>

---

## License

Knowledge is open-source software licensed under the **[MIT License](LICENSE)**.

```text
MIT License

Copyright (c) 2026 Poorvith M P & Knowledge Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
```
*(See full license text in [LICENSE](LICENSE))*
