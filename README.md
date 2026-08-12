# Knowledge - Native GitHub AI Assistant & Context Engine (CodeRabbit Style)

**Knowledge** is an engineering context assistant powered by **Context Engine V1** and **Mistral AI (`mistral-small-2506`)**. It operates **100% natively inside GitHub** (like CodeRabbit), via **Serverless GitHub Actions**, or through an interactive **Streamlit Web Dashboard**.

Instead of simply summarizing the current issue text in isolation, **Knowledge** expands the surrounding context—extracting linked Pull Requests (merged & closed attempts), maintainer directives, contributor threads, and referenced documentation—to generate a structured **Engineering Handoff** for contributors.

---

## ⚡ Issue Context Expansion (Context Engine V1)

### The Architecture

```
                                 GitHub API
                                     │
                                     ▼
                               Current Issue
                                     │
             ┌───────────────────────┼───────────────────────┐
             ▼                       ▼                       ▼
      Issue Comments            Linked PRs              References
  (Maintainer Directives)    (Merged & Closed)       (Docs & Source Code)
             │                       │                       │
             └───────────────────────┼───────────────────────┘
                                     ▼
                               Context Engine
                            (`context_engine.py`)
                                     │
                                     ▼
                         Structured Evidence Set
                                     │
                                     ▼
                              Knowledge Agent
                            (`knowledge_agent.py`)
                                     │
                                     ▼
                           Mistral AI Synthesis
                           (`mistral-small-2506`)
                                     │
                                     ▼
                            Engineering Handoff
```

### What Context Engine V1 Collects
1. **Current Issue Details**: Title, body, author, number.
2. **Categorized Issue Comments**:
   - **Maintainer Directives**: Highlights explicit constraints (e.g. *"Don't modify the OAuth flow"*).
   - **Contributor Discussions**: Captures community context & Q&A.
3. **Surrounding Historical PRs**: Automatically scans for referenced PRs (`#143`, `PR #151`, `pull/143`, GitHub PR URLs) and fetches:
   - PR State (`🟢 Merged` vs `🔴 Closed / Failed Attempt`)
   - PR Summary & Purpose
   - Touched files
4. **Explicit References & `KNOWLEDGE.md` Rules**: Reads repository guardrails and referenced codebase files before generating recommendations.

---

## 🚀 Key Features

- **🤖 Native GitHub Bot (CodeRabbit Style)**: Responds directly in GitHub issue threads via zero-server GitHub Actions.
- **🧠 Issue Context Expansion**: Surrounds issues with historical PR context, maintainer notes, and component entry points.
- **📋 Engineering Handoff Output**: Outputs clear guidance covering:
  - **🎯 Before Starting** (Entry points & maintainer constraints)
  - **📜 Historical Context & PR Lessons** (Why previous attempts failed or what structure was introduced)
  - **🚀 Recommended Exploration Steps**
  - **🔗 Evidence & References**
- **📜 `KNOWLEDGE.md` Guardrail Engine**: Reads `KNOWLEDGE.md` **FIRST** to enforce strict repository rules and zero hallucinations.
- **💻 Streamlit Web Dashboard**: Pure Python web app featuring a visual **🧠 Context Engine Evidence Set** card and interactive simulation mode.

---

## 🔑 Environment Configuration (`.env`)

Create `.env` by copying `.env.example`:
```bash
cp .env.example .env
```

Populate `.env` with your API keys:
```env
# Optional GitHub OAuth Application Credentials (for Streamlit dashboard)
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret
REDIRECT_URI=http://localhost:8501

# Mistral AI Configuration
MISTRAL_API_KEY=your_mistral_api_key
MISTRAL_MODEL=mistral-small-2506
```

---

## 🚀 Integration Options

### Option 1: Zero-Server GitHub Actions (Serverless Integration)
*Contributors just paste your code files and workflow into their repository. Zero servers required!*

1. Copy the core Python files (`bot.py`, `knowledge_agent.py`, `context_engine.py`, `github_auth.py`, `config.py`, `KNOWLEDGE.md`, `requirements.txt`) into your repository.
2. Add `.github/workflows/knowledge.yml`:
   ```yaml
   name: Knowledge Bot Assistant

   on:
     issue_comment:
       types: [created]

   jobs:
     knowledge_bot:
       if: contains(github.event.comment.body, '@Knowledge') || contains(github.event.comment.body, '@knowledge')
       runs-on: ubuntu-latest

       permissions:
         issues: write
         pull-requests: read
         contents: read

       steps:
         - name: Checkout Repository
           uses: actions/checkout@v4

         - name: Setup Python
           uses: actions/setup-python@v5
           with:
             python-version: '3.11'

         - name: Install Dependencies
           run: pip install -r requirements.txt

         - name: Run @Knowledge Bot & Context Engine
           env:
             GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
             MISTRAL_API_KEY: ${{ secrets.MISTRAL_API_KEY }}
           run: |
             python bot.py \
               --owner ${{ github.repository_owner }} \
               --repo ${{ github.event.repository.name }} \
               --issue ${{ github.event.issue.number }} \
               --comment "${{ github.event.comment.body }}"
   ```
3. Add `MISTRAL_API_KEY` under Repository **Settings ➔ Secrets and variables ➔ Actions**.
4. **Test it live!** Comment `@Knowledge How should I start?` on **any** GitHub issue!

---

### Option 2: Interactive Streamlit Web Dashboard

Run the web dashboard to visually inspect context evidence, connected repositories, and handoffs:

```bash
pip install -r requirements.txt
streamlit run app.py
```

Features an **Interactive Simulation Mode** to test Context Engine V1 on any issue.


---

## 📁 Project Structure

```
Knowledge/
├── .github/workflows/
│   └── knowledge.yml       # Serverless GitHub Action workflow
├── KNOWLEDGE.md            # Mandatory repository rules & guardrails
├── context_engine.py       # Context Engine V1 (PR & Comment expansion layer)
├── knowledge_agent.py      # Mistral AI prompt engine & handoff synthesizer
├── github_auth.py          # GitHub REST API client (Issues, PRs, Comments)
├── bot.py                  # Headless GitHub Bot execution script
├── app.py                  # Streamlit Web Dashboard UI & Evidence card
├── test_context_engine.py  # Unit test suite for Context Engine V1
├── config.py               # Environment configuration loader
├── requirements.txt        # Python dependencies
├── .env.example            # Environment configuration template
└── README.md               # Documentation
```
