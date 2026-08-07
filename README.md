# Knowledge - Native GitHub AI Assistant & Context Engine (CodeRabbit Style)

**Knowledge** is an engineering context assistant powered by **Mistral AI (`mistral-small-2506`)**. It operates **100% natively inside GitHub** (like CodeRabbit) and includes an interactive **Streamlit Web Dashboard**.

When a contributor comments `@Knowledge <question>` on any GitHub Issue, Knowledge automatically reads the repository's [`KNOWLEDGE.md`](KNOWLEDGE.md) rulebook, analyzes relevant documentation & source files, and posts a summarized answer directly back to GitHub!

---

## 🚀 Key Features

- **🤖 Native GitHub Bot (CodeRabbit Style)**: Responds directly in GitHub issue comment threads using GitHub Actions.
- **📜 `KNOWLEDGE.md` Guardrail Engine**: Reads `KNOWLEDGE.md` **FIRST** before making decisions to enforce strict rules:
  - **Source Priority**: Issue info ➔ Explicit links ➔ `README`/`CONTRIBUTING`/`KNOWLEDGE.md` ➔ Source code.
  - **No Hallucination**: Never invents APIs, architecture, or requirements.
  - **Evidence Citations**: Every claim is cited back to a source file or issue.
  - **Insufficient Info Fallback**: Defers missing or ambiguous information gracefully to maintainers.
- **🧠 Mistral AI (`mistral-small-2506`)**: High-performance LLM engine for issue summarization.
- **💻 Streamlit Web Dashboard**: Pure Python web dashboard for OAuth connection, repo browsing, and visual prompt testing.

---

## 🔄 How It Works (Native GitHub Flow)

```
Contributor posts comment on GitHub Issue:
"@Knowledge What are the prerequisites?"
                    │
                    ▼
GitHub Action Trigger (.github/workflows/knowledge.yml)
                    │
                    ▼
1. Reads KNOWLEDGE.md FIRST for repository rules & guardrails
2. Fetches issue context & referenced repo files via GitHub API
3. Calls Mistral AI (mistral-small-2506) with MISTRAL_API_KEY
4. Posts comment directly back to GitHub Issue thread
                    │
                    ▼
Answer appears live on GitHub! 🤖
```

---

## 🔑 Mandatory Configuration (`.env`)

Before running the application or starting development, configuring your `.env` file is **MANDATORY**:

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Populate `.env` with your API keys and GitHub credentials:
   ```env
   # Mandatory GitHub OAuth Application Credentials
   GITHUB_CLIENT_ID=your_github_client_id
   GITHUB_CLIENT_SECRET=your_github_client_secret
   REDIRECT_URI=http://localhost:8501

   # Mandatory Mistral AI Configuration
   MISTRAL_API_KEY=your_mistral_api_key
   MISTRAL_MODEL=mistral-small-2506
   ```

---

## ⚡ 1-Minute Setup Guide (GitHub Action)

### 1. Add Files to Your GitHub Repository
Ensure the following files are committed to your repository:
- `.github/workflows/knowledge.yml`
- `bot.py`
- `knowledge_agent.py`
- `github_auth.py`
- `config.py`
- `KNOWLEDGE.md` *(Mandatory rulebook file)*

### 2. Add your Mistral API Key to GitHub Secrets
1. Go to your repository on GitHub: **Settings ➔ Secrets and variables ➔ Actions**.
2. Click **New repository secret**.
3. **Name**: `MISTRAL_API_KEY`
4. **Value**: Your Mistral API Key.
5. Click **Add secret**.

### 3. Test It Live!
Open any Issue on your GitHub repository and post a comment:
```markdown
@Knowledge What are the prerequisites and setup steps?
```
Knowledge will automatically run via GitHub Actions, process the issue, and reply directly on your GitHub issue thread!

---

## 💻 Running the Streamlit Web Dashboard

Once `.env` is configured, start the interactive web application:

```bash
pip install -r requirements.txt
streamlit run app.py
```

---

## 📁 Project Structure

```
Knowledge/
├── .github/workflows/
│   └── knowledge.yml       # GitHub Action workflow (issues: write)
├── KNOWLEDGE.md            # Mandatory repository rules & guardrails
├── bot.py                  # Headless GitHub Bot execution engine
├── knowledge_agent.py      # Mistral AI (mistral-small-2506) engine & rule reader
├── github_auth.py          # GitHub REST API client & comment poster
├── config.py               # Environment variable configuration
├── app.py                  # Streamlit Web Dashboard UI
├── requirements.txt        # Python dependencies
├── .env.example            # Environment configuration template
└── README.md               # Documentation
```
