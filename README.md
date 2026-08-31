# Knowledge — Engineering Context Layer (Native GitHub Bot)

**Knowledge** is an engineering context layer bot designed to run natively inside GitHub Issues and Pull Requests. When a contributor or maintainer comments `@Knowledge <question>` or `/knowledge <question>`, the engine classifies query intent, retrieves bounded evidence across repository files and conversation threads, enforces repository rules from `KNOWLEDGE.md`, and posts a structured engineering handoff directly back to GitHub.

---

## Features

- **GitHub-Native Interaction:** Triggered automatically by commenting `@Knowledge <question>` or `/knowledge <question>` on any Issue or PR.
- **Adaptive Technicality Calibration:** Internal 1–10 point system dynamically calibrates response technicality from conceptual analogies (1–3) to low-level implementation/AST/schema traces (7–10) without leaking point values.
- **Cross-Repository Intelligence:** Discovers context and traces relationships across companion services (frontend, backend, shared packages) with repository-scoped citations.
- **Multi-LLM Provider Architecture:** Native REST adapters for Mistral AI, OpenAI, Anthropic Claude, Google Gemini, Groq, and local Ollama without heavy SDK dependencies.
- **Intent-Driven Context Retrieval:** Classifies queries across 7 intent categories (PR understanding, repo onboarding, architecture explanation, contribution guidance, feature flows, historical decisions, and issue onboarding) to collect high-signal evidence.
- **Mandatory Guardrail Enforcement:** Parses repository guidelines from `KNOWLEDGE.md` and injects them into system instructions.
- **Hermetic Testing:** 100% offline unit tests with mock fixtures and automated GitHub Actions CI matrix across Python 3.10, 3.11, and 3.12.
- **Dual Deployment Options:** Serverless GitHub Actions runner or standalone FastAPI webhook server with HMAC-SHA256 signature verification.
- **Streamlit Web Dashboard:** Interactive UI for exploring repository context graphs, testing questions, and visualizing evidence sets.

---

## 1-Minute GitHub Action Setup

The easiest path is to give [Integration.md](Integration.md) to a repository-aware coding agent. It will inspect the target project, fetch the runtime files, create the workflow and `KNOWLEDGE.md`, and report the secrets and smoke test still needed from a maintainer.

To add Knowledge Bot manually, copy these files into your project:

```text
Your-Repo/
├── .github/workflows/
│   └── knowledge.yml       # Copied from templates/knowledge.yml
├── knowledge_engine.py     # Unified core engine
├── adaptive_depth.py       # Adaptive technicality depth engine
├── multi_repo.py           # Multi-repository configuration & target resolver
├── providers.py            # Multi-LLM provider adapters
└── KNOWLEDGE.md            # Repository rulebook & guidelines
```

### GitHub Secrets Configuration

In your repository settings (**Settings ➔ Secrets and variables ➔ Actions**), add your LLM API key:

| Secret Name | Description | Default Model |
| :--- | :--- | :--- |
| `MISTRAL_API_KEY` | Mistral AI API Key | `mistral-small-2506` |
| `OPENAI_API_KEY` | OpenAI API Key | `gpt-4o-mini` |
| `ANTHROPIC_API_KEY` | Anthropic Claude API Key | `claude-3-5-haiku-20241022` |
| `GEMINI_API_KEY` | Google Gemini API Key | `gemini-1.5-flash` |
| `GROQ_API_KEY` | Groq Ultra-fast API Key | `llama-3.3-70b-versatile` |

---

## Multi-Repository Intelligence Configuration

Knowledge can investigate relationships across multiple companion repositories (e.g. tracing a frontend React component to a backend FastAPI endpoint or shared microservices).

### 1. Declaring Companion Repositories in `KNOWLEDGE.md`

Add a `## Related Repositories` section to your `KNOWLEDGE.md`:

```markdown
## Related Repositories
- `acme/backend-api`: Core FastAPI backend, database services, and REST routes
- `acme/shared-ui`: Design system components and cross-project UI primitives
- `acme/auth-service`: OAuth2/OIDC token verification service
```

### 2. Declaring Companion Repositories via Environment Variable

Alternatively, configure companion repositories globally or in CI via `KNOWLEDGE_RELATED_REPOS`:

```bash
export KNOWLEDGE_RELATED_REPOS="acme/backend-api, acme/shared-ui, acme/auth-service"
```

### 3. Cross-Repository Querying

When contributors ask cross-repository questions (e.g. `@Knowledge layout.tsx is connected with which HTTP endpoint in backend repo?`), Knowledge discovers trees and candidate files from all declared companion repositories and formats repository-scoped citations:
`[owner/repo:path/to/file.py#L1-L20](https://github.com/owner/repo/blob/sha/path/to/file.py#L1-L20)`.

---

## Adaptive Technicality Calibration (Internal Point System)

Knowledge automatically tunes its explanation depth using an internal 1–10 scoring engine (base 5):

- **Conceptual / High Accessibility (Score 1–3):** Activated by simplification cues (*"explain simpler"*, *"ELI5"*, *"for beginners"*). Uses intuitive analogies and high-level architectural walkthroughs.
- **Balanced Engineering KT (Score 4–6):** Default balanced technical context for professional contributors.
- **Deep Technical Implementation (Score 7–10):** Activated by low-level technical terms (*"AST"*, *"bytecode"*, *"HTTP endpoint"*, *"SQL schema"*, *"concurrency"*). Traces exact function signatures, routes, and state transitions.

> [!NOTE]
> Point scores are strictly internal heuristics and are never leaked to users in responses or comments.

---

## Multi-LLM Provider Configuration

Knowledge auto-detects configured provider keys from your environment. You can explicitly set the active provider using `LLM_PROVIDER`:

```bash
# Set active provider
export LLM_PROVIDER=openai  # mistral | openai | anthropic | gemini | groq | ollama

# Set provider-specific model override (optional)
export OPENAI_MODEL=gpt-4o
export ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
export GEMINI_MODEL=gemini-1.5-pro
export GROQ_MODEL=llama-3.3-70b-versatile
```

### Evidence Truncation Limits (Optional)

Configure context bounding limits via environment variables:

| Variable | Description | Default |
| :--- | :--- | :--- |
| `KNOWLEDGE_MAX_FILE_CHARS` | Maximum characters read per primary evidence file (`KNOWLEDGE.md`, `README.md`, `CONTRIBUTING.md`) and per PR diff | `3000` |
| `KNOWLEDGE_MAX_COMMENT_CHARS` | Maximum characters read per secondary evidence file (changed files, architecture and keyword matches) | `2500` |
| `KNOWLEDGE_MAX_DIFF_CHARS` | Maximum characters read from dependency manifests (`requirements.txt`, `package.json`) | `1500` |

### Local / Air-Gapped Execution with Ollama

To run Knowledge without third-party API calls using local Ollama models:

```bash
export LLM_PROVIDER=ollama
export OLLAMA_HOST=http://localhost:11434
export OLLAMA_MODEL=llama3.2:latest
```

---

## Local Development & Testing

```bash
# Clone the repository
git clone https://github.com/PrithvijitBose/Knowledge-Agent.git
cd Knowledge-Agent

# Install in development mode
pip install -e .

# Or install dependencies from requirements.txt
pip install -r requirements.txt

# Run CLI directly
knowledge-agent --help
# Or: python -m knowledge_agent --help

# Run all hermetic unit tests offline
python -m pytest
```

---

## Webhook Server Deployment

For real-time webhook deployments with custom domains:

```bash
# Start FastAPI Webhook Server on port 8000
python webhook_server.py
```

Set `GITHUB_WEBHOOK_SECRET` in your environment to automatically enforce HMAC-SHA256 signature verification on inbound webhooks.

---

## License

This project is licensed under the [MIT License](LICENSE).
