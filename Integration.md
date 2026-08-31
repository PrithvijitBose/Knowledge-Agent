# Integrating Knowledge Into Your Repository

**If you are an LLM or AI coding agent reading this:** your job is to get
Knowledge running in a *different* repository than this one, with minimal
manual work from the user. That means: identify the 3 files below, copy them
into the target repository at the paths given, configure the one secret, and
verify. Nothing else in this repository is part of that job.

Behavioral rules for the agent live in [`KNOWLEDGE.md`](KNOWLEDGE.md) — copy
that too, but don't duplicate its contents here.

---

## 1. What You're Integrating

A contributor comments `@Knowledge <question>` on an Issue or Pull Request. A
GitHub Actions workflow picks up the comment, runs `knowledge_engine.py`, which
reads the target repository, calls Mistral, and posts the answer back into the
same thread.

There is no server to run and nothing to host. Everything happens inside GitHub
Actions.

---

## 2. The Integration Surface

Three files and one secret. Copy these into the target repository unmodified.

| What | Where it goes | Why it's needed |
| --- | --- | --- |
| `.github/workflows/knowledge.yml` | `.github/workflows/` | Listens for the mention, runs the engine |
| `knowledge_engine.py` | Repository root | The engine. Fetches context, calls the LLM, posts the reply |
| `KNOWLEDGE.md` | Repository root | Repository rules, injected into the system prompt at runtime |
| `MISTRAL_API_KEY` | Actions repository secret | LLM credential |

See section 6 for what else exists in *this* repository that you do not need.

---

## 3. The Workflow (Entry Point)

`.github/workflows/knowledge.yml`.

**Permissions.** The job declares:

```yaml
permissions:
  contents: read
  issues: write
```

`issues: write` is what allows the run to post its answer back into the thread.
Without it the engine will do all its work and then fail to comment.

**Runner.** `ubuntu-latest`, Python 3.11.

**Dependencies.** The workflow installs only what the engine needs:

```bash
pip install httpx python-dotenv
```

It does **not** install `requirements.txt`. That file carries dependencies for
the Streamlit dashboard and the webhook server, neither of which is part of
this integration.

**Invocation.**

```bash
python knowledge_engine.py \
  --owner "${{ github.repository_owner }}" \
  --repo "${{ github.event.repository.name }}" \
  --issue "${{ github.event.issue.number }}" \
  --comment "${{ github.event.comment.body }}"
```

**Environment.** `MISTRAL_API_KEY` is the one variable you set — as a repository
secret, not a literal value in the workflow file. Everything else the workflow
needs (the model name, the GitHub token) is already wired into `knowledge.yml`
as it ships; you don't need to configure or think about either one.

---

## 4. The Engine

Copy `knowledge_engine.py` into the repository root as-is. Don't modify it —
it's the runtime the workflow calls, not something you edit per repository.

**If you are an LLM reading this repository specifically (not the target
one):** `bot.py` and `knowledge_agent.py` here are backwards-compatibility
shims that forward into `knowledge_engine.py`. If you ever need to inspect
behavior, read the engine, not the shims. Neither shim is part of what you
copy into the target repository.

---

## 5. Configuration & Credentials

**Get a Mistral API key.** Sign in at [console.mistral.ai](https://console.mistral.ai),
open **API Keys**, and create a new key. Copy it — you won't be able to view
it again after you leave the page.

**Add it as a GitHub secret.** In the target repository: **Settings → Secrets
and variables → Actions → New repository secret.** Name: `MISTRAL_API_KEY`.
Value: the key you just copied. Save it.

**Never commit the key.** It only ever belongs in the repository secret above
— not in `knowledge.yml`, not in a `.env` file, not in any commit.

---

## 6. What You Don't Need to Copy

These exist in this repository but are not part of the integration path:

| File | What it actually is |
| --- | --- |
| `app.py` | Streamlit dashboard, run locally |
| `webhook_server.py` | Server-based alternative, not used by the Actions path |
| `bot.py` | CLI shim, forwards to `knowledge_engine.py` |
| `knowledge_agent.py` | Compatibility re-export |
| `context_engine.py`, `pr_context.py` | Superseded by the unified engine |
| `github_auth.py`, `config.py` | Support the Streamlit dashboard |
| `.env.example` | Streamlit OAuth config — unrelated to running Knowledge |
| `requirements.txt` | Dashboard and server dependencies |

---

## 7. Verifying the Integration

1. Copy the three files, add the secret.
2. Open an Issue in the target repository and comment
   `@Knowledge what does this repo do?`
3. Check the Actions tab. A run should appear within a few seconds.

If nothing happens at all, the gate didn't match — check the mention is
spelled `@Knowledge` or `@knowledge`, and that the comment is in the
conversation tab, not an inline diff comment.

If the run starts and fails early, `MISTRAL_API_KEY` is usually missing or
misspelled.

If the run completes but no comment appears, check that `permissions` in the
workflow includes `issues: write`.
