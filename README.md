# Knowledge — Engineering Context Layer (Native GitHub Bot)

**Knowledge** is an engineering context assistant powered by **Mistral AI (`mistral-small-2506`)**. It operates **100% natively inside GitHub** (like CodeRabbit) and includes an interactive **Streamlit Web Dashboard**.

When a contributor comments `@Knowledge <question>` on any GitHub Issue or Pull Request, Knowledge automatically constructs an engineering context graph, enforces repository rules from [`KNOWLEDGE.md`](KNOWLEDGE.md), categorizes information into cognitive priority tiers, and posts a cited answer directly back to GitHub!

---

## ⚡ 1-Minute Setup Guide (Ultra-Low File Footprint)

Users only need to copy **1 Python file** (`knowledge_engine.py`) and **1 Workflow file** (`.github/workflows/knowledge.yml`) to run the bot in any consumer repository!

### 1. Copy Files to Your Repository
Copy these **3 files** into your GitHub repository:

```
Your-Repo/
├── .github/workflows/
│   └── knowledge.yml       # GitHub Action workflow
├── knowledge_engine.py     # ⚡ UNIFIED CORE ENGINE (1 single Python file!)
└── KNOWLEDGE.md            # Mandatory repository rulebook
```

### 2. Add your Mistral API Key to GitHub Secrets
1. Go to your repository on GitHub: **Settings ➔ Secrets and variables ➔ Actions**.
2. Click **New repository secret**.
3. **Name**: `MISTRAL_API_KEY`
4. **Value**: Your Mistral API Key.
5. Click **Add secret**.

### 3. Test It Live!
Open any Issue or Pull Request on your GitHub repository and post a comment:
```markdown
@Knowledge I have never worked on this repository. How should I learn this codebase?
```
Knowledge will automatically run via GitHub Actions, build the context graph, and reply directly on your GitHub issue thread!

---

## 📁 Project Structure

```
Knowledge/
├── .github/workflows/
│   └── knowledge.yml       # GitHub Action workflow (runs knowledge_engine.py)
├── knowledge_engine.py     # ⚡ UNIFIED CORE ENGINE (Config + API Client + Context Graph + LLM Synthesizer)
├── KNOWLEDGE.md            # Mandatory repository rules & guardrails
├── DECISION.md             # Architectural decision log & tradeoffs
├── FLOW.md                 # Call graph & execution reference
├── bot.py                  # CLI runner shim (delegates to knowledge_engine.py)
├── app.py                  # Streamlit Web Dashboard UI
├── webhook_server.py       # FastAPI webhook server
├── requirements.txt        # Python dependencies
└── README.md               # Documentation
```
