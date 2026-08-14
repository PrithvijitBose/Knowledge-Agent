# Knowledge — Engineering Context Layer (Native GitHub Bot)

**Knowledge** is an engineering context layer bot designed to run natively inside GitHub Issues and Pull Requests. When a contributor or maintainer comments `@Knowledge <question>` or `/knowledge <question>`, the engine classifies query intent, retrieves bounded evidence across repository files and conversation threads, enforces repository rules from `KNOWLEDGE.md`, and posts a structured engineering handoff directly back to GitHub.

---

## Features

- **GitHub-Native Interaction:** Triggered automatically by commenting `@Knowledge <question>` or `/knowledge <question>` on any Issue or PR.
- **Multi-LLM Provider Architecture:** Native REST adapters for Mistral AI, OpenAI, Anthropic Claude, Google Gemini, Groq, and local Ollama without heavy SDK dependencies.
- **Intent-Driven Context Retrieval:** Classifies queries across 7 intent categories (PR understanding, repo onboarding, architecture explanation, contribution guidance, feature flows, historical decisions, and issue onboarding) to collect high-signal evidence.
- **Mandatory Guardrail Enforcement:** Parses repository guidelines from `KNOWLEDGE.md` and injects them into system instructions.
- **Hermetic Testing:** 100% offline unit tests with mock fixtures and automated GitHub Actions CI matrix across Python 3.10, 3.11, and 3.12.
- **Dual Deployment Options:** Serverless GitHub Actions runner or standalone FastAPI webhook server with HMAC-SHA256 signature verification.
- **Streamlit Web Dashboard:** Interactive UI for exploring repository context graphs, testing questions, and visualizing evidence sets.

---

## 1-Minute GitHub Action Setup

To add Knowledge Bot to any repository, copy these 3 files into your project:

```
Your-Repo/
├── .github/workflows/
│   └── knowledge.yml       # GitHub Action workflow
├── knowledge_engine.py     # Unified core engine
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

# Install dependencies
pip install -r requirements.txt

# Run all hermetic unit tests offline
python -m unittest discover -s . -p "test_*.py"
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
