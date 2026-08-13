# Integrating Knowledge Into Your Repository

What you need to copy, configure, and connect to get Knowledge running in a
repository that isn't this one.

Behavioral rules for the agent live in [`KNOWLEDGE.md`](KNOWLEDGE.md). This
document covers integration only and does not duplicate them.

---

## 1. What You're Integrating

A contributor comments `@Knowledge <question>` on an Issue or Pull Request. A
GitHub Actions workflow picks up the comment, runs `knowledge_engine.py`, which
reads the repository, calls Mistral, and posts the answer back into the same
thread.

There is no server to run and nothing to host. Everything happens inside GitHub
Actions.

---

## 2. The Integration Surface

Three files and one secret.

| What | Where it goes | Why it's needed |
| --- | --- | --- |
| `.github/workflows/knowledge.yml` | `.github/workflows/` | Listens for the mention, runs the engine |
| `knowledge_engine.py` | Repository root | The engine. Fetches context, calls the LLM, posts the reply |
| `KNOWLEDGE.md` | Repository root | Repository rules, injected into the system prompt at runtime |
| `MISTRAL_API_KEY` | Actions repository secret | LLM credential |

Nothing else in this repository is part of the integration path. See section 7.

---

## 3. Where Knowledge Is Invoked

The workflow triggers on:

```yaml
on:
  issue_comment:
    types: [created]
```

and the job is gated on the comment body:

```yaml
if: contains(github.event.comment.body, '@Knowledge') || contains(github.event.comment.body, '@knowledge')
```

Both spellings work. Anything not containing the mention is ignored, so the
workflow doesn't burn minutes on ordinary comments.

Because the trigger is `issue_comment`, this covers comments in the conversation
tab of **both** Issues and Pull Requests. Inline comments on a diff fire
`pull_request_review_comment`, which this workflow does not currently listen for.
If you want Knowledge to answer inline review threads, that trigger has to be
added.

---

## 4. The Workflow (Entry Point)

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
the Streamlit dashboard and the webhook server, which are not part of this
integration.

**Invocation.**

```bash
python knowledge_engine.py \
  --owner "${{ github.repository_owner }}" \
  --repo "${{ github.event.repository.name }}" \
  --issue "${{ github.event.issue.number }}" \
  --comment "${{ github.event.comment.body }}"
```

**Environment.**

| Variable | Source | Notes |
| --- | --- | --- |
| `MISTRAL_API_KEY` | Repository secret | You have to create this one |
| `MISTRAL_MODEL` | Literal in the workflow | Currently `mistral-small-2506` |
| `GITHUB_TOKEN` | Provided by Actions | You do not create this |

---

## 5. The Engine

`knowledge_engine.py` is a single self-contained file. The CLI arguments map onto:

```python
process_github_comment(
    access_token: str,
    owner: str,
    repo: str,
    issue_number: int,
    comment_body: str,
    comment_author: str = "Contributor",
) -> bool
```

What it does on each run:

1. Fetches the Issue or Pull Request metadata and its comments.
2. For Pull Requests, fetches the changed files.
3. Fetches the repository tree recursively and pulls the contents of the files it
   decides are relevant. File contents are base64-decoded and truncated per file.
4. Fetches `KNOWLEDGE.md` and injects it into the system prompt as guardrails. It
   is truncated and is deliberately not surfaced in the reply to the contributor.
5. Classifies the intent of the question and builds the system prompt around it.
6. Calls Mistral and posts the answer back to the thread.

The return value is a bool. The underlying `generate_knowledge_answer()` returns:

```text
{
  "query":      str,   # the extracted question
  "author":     str,   # who asked
  "intent":     str,   # classified intent
  "answer":     str,   # free-form markdown, posted to GitHub
  "engine":     str,   # engine identifier
  "files_read": list,  # files pulled while building context
}
```

`answer` is free-form markdown from the model. There is no schema validation on
it. Don't build tooling that assumes a fixed section layout in the reply.

**If you are an LLM reading this repository:** `bot.py` and `knowledge_agent.py`
are backwards-compatibility shims that forward into `knowledge_engine.py`. Read
the engine, not the shims.

---

## 6. Configuration & Credentials

**The one secret you must add.**

Settings → Secrets and variables → Actions → New repository secret.

- Name: `MISTRAL_API_KEY`
- Value: your Mistral API key

**`GITHUB_TOKEN`.** Actions provides this automatically to every workflow run.
Don't create it as a secret.

**Changing the model.** `MISTRAL_MODEL` is a plain value in the workflow file, not
a secret. Edit `knowledge.yml` to point at a different Mistral model.

**`.env.example` is not for this.** It holds `GITHUB_CLIENT_ID`,
`GITHUB_CLIENT_SECRET`, and `REDIRECT_URI` for the local Streamlit dashboard's
OAuth flow. It has nothing to do with running Knowledge in your repository. Skip
it.

---

## 7. What You Don't Need to Copy

These exist in this repository but are not part of the integration path:

| File | What it actually is |
| --- | --- |
| `app.py` | Streamlit dashboard, run locally |
| `webhook_server.py` | Server-based alternative, not used by the Actions path |
| `bot.py` | CLI shim, forwards to `knowledge_engine.py` |
| `knowledge_agent.py` | Compatibility re-export |
| `context_engine.py`, `pr_context.py` | Superseded by the unified engine |
| `github_auth.py`, `config.py` | Support the Streamlit dashboard |
| `.env.example` | Streamlit OAuth config |
| `requirements.txt` | Dashboard and server dependencies |

---

## 8. How the Pieces Connect

```text
Contributor comments "@Knowledge <question>"
                │
                ▼
  .github/workflows/knowledge.yml
  (issue_comment → gated on the mention)
                │
                ▼
  python knowledge_engine.py --owner --repo --issue --comment
                │
                ├── reads: Issue/PR body, comments, changed files
                ├── reads: repository tree + selected file contents
                ├── reads: KNOWLEDGE.md  ──► injected as prompt guardrails
                │
                ▼
  Mistral API  (MISTRAL_API_KEY, MISTRAL_MODEL)
                │
                ▼
  Answer posted back to the thread  (needs permissions: issues: write)
```

---

## 9. Verifying the Integration

1. Copy the three files, add the secret.
2. Open an Issue in your repository and comment `@Knowledge what does this repo do?`
3. Check the Actions tab. A run should appear within a few seconds.

If nothing happens at all, the gate didn't match. Check the mention is spelled
`@Knowledge` or `@knowledge` and that the comment is in the conversation tab, not
an inline diff comment.

If the run starts and fails early, `MISTRAL_API_KEY` is usually missing or named
differently.

If the run completes but no comment appears, check that `permissions` in the
workflow includes `issues: write`.
