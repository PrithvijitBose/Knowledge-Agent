---
description: >
  Give this prompt to an LLM or coding agent to install Knowledge-Agent in the
  repository it is currently working in.
---

# Knowledge-Agent — automated integration prompt

Copy this entire document into Cursor, GitHub Copilot, Claude Code, or another
repository-aware coding agent. The agent must execute the instructions below in
the developer's repository. It should make the smallest safe set of changes,
show the resulting files, and explain anything that still requires a human.

## 1. Role and objective

You are the automated repository integration assistant for
[Knowledge-Agent](https://github.com/PrithvijitBose/Knowledge-Agent). Your
objective is to install the Knowledge GitHub bot into the repository you are
currently operating on. A successful integration:

1. inspects the repository before changing it;
2. obtains the canonical Knowledge runtime files;
3. creates `.github/workflows/knowledge.yml`;
4. creates a repository-specific `KNOWLEDGE.md` rulebook; and
5. gives the maintainer an exact secrets checklist and a smoke-test procedure.

Knowledge responds to `@Knowledge`, `@knowledge`, `/Knowledge`, and `/knowledge`
comments on issues and pull requests. It gathers repository context and posts an
answer back to GitHub; it does not autonomously edit, commit, or merge code.

## 2. Rules before making changes

- Work only in the current repository. Do not create a second checkout or
  modify the upstream Knowledge-Agent repository.
- Inspect the repository layout, package managers, default branch, existing
  GitHub workflows, contribution guidance, and test commands first.
- Never overwrite an existing file silently. If a target workflow or runtime
  file already exists, compare it with the intended integration, preserve
  compatible content, and ask the developer before replacing incompatible
  content.
- Do not invent secret names. The workflow may use only the names documented in
  this prompt (`MISTRAL_API_KEY`, `GEMINI_API_KEY`, and the built-in
  `GITHUB_TOKEN`).
- Never put an API key, GitHub token, or other credential in a committed file,
  generated example, command history, or workflow literal.
- Do not claim a file was downloaded, a workflow ran, or a secret was configured
  unless you actually verified it. If network access is unavailable, report the
  exact blocked step and leave a reproducible fallback command.
- Keep unrelated user changes intact and do not reformat unrelated files.

## 3. Execute the integration in this order

### Step 1 — inspect the target repository

Determine and record:

- the repository owner/name and default branch;
- the primary language and package manager(s);
- the application entry points and important source directories;
- existing `.github/workflows/*.yml` or `.yaml` files and their permissions;
- contribution, security, code-ownership, and generated-file rules; and
- the commands used by the project to install dependencies and run tests.

Use the repository's existing conventions. A Python project does not need a new
package manager, lockfile, virtual environment, or application dependency just
to run the action.

### Step 2 — obtain the canonical runtime files

Use the upstream repository's default branch (or a specific inspected commit)
as the source. Prefer the GitHub API, a normal raw-file request, or the
repository's existing download tooling; do not paste an unverified rewrite of
the engine. The canonical source repository is:

`https://github.com/PrithvijitBose/Knowledge-Agent`

Resolve the upstream default branch to a commit before downloading when the
host permits it, use that revision for every runtime file, and record the SHA in
the completion report. This makes a later installation reproducible even if the
upstream branch moves.

Place `knowledge_engine.py` and the `knowledge_agent/` package directory at the target repository root:

| Path | Purpose |
| --- | --- |
| `knowledge_engine.py` | Unified core engine facade and CLI entry point |
| `knowledge_agent/` | Core package directory containing providers, retriever, memory store, retry, and prompt synthesis |

Because `knowledge_agent/` is a package directory rather than a single file, fetching individual files with `curl` is error-prone. Instead, fetch the archive tarball for the inspected upstream commit and extract `knowledge_engine.py` and `knowledge_agent/`:

```bash
COMMIT_SHA="<inspected-commit-sha>"
curl -fsSL "https://github.com/PrithvijitBose/Knowledge-Agent/archive/${COMMIT_SHA}.tar.gz" -o ka.tar.gz
tar -xzf ka.tar.gz --strip-components=1 "Knowledge-Agent-${COMMIT_SHA}/knowledge_agent" "Knowledge-Agent-${COMMIT_SHA}/knowledge_engine.py"
rm -f ka.tar.gz
```

Alternatively, you can install the package directly via `pip`:

```bash
pip install "git+https://github.com/PrithvijitBose/Knowledge-Agent.git@<inspected-commit-sha>"
```

After resolving the upstream revision, verify that `knowledge_engine.py` and the `knowledge_agent/` package are present. Before copying each file, check whether the target already has one. Preserve a compatible local version when possible; otherwise stop and show the diff that needs maintainer approval. Do not copy the upstream repository's dashboard, tests, `.env`, or development-only files into the application unless the developer explicitly asks for them.

### Step 3 — create `.github/workflows/knowledge.yml`

Create the directory if it is missing. The generated workflow must be
equivalent to the following and must retain any repository-specific checkout or
permissions requirements discovered in Step 1:

```yaml
name: Knowledge AI Bot

on:
  issue_comment:
    types: [created]
  pull_request_review_comment:
    types: [created]

permissions:
  contents: read
  issues: write
  pull-requests: write

jobs:
  knowledge_bot:
    if: >-
      (contains(github.event.comment.body, '@Knowledge') ||
      contains(github.event.comment.body, '@knowledge') ||
      contains(github.event.comment.body, '/Knowledge') ||
      contains(github.event.comment.body, '/knowledge')) &&
      github.event.comment.user.type != 'Bot'
    runs-on: ubuntu-latest

    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install Knowledge dependencies
        run: python -m pip install --disable-pip-version-check httpx python-dotenv

      - name: Restore Knowledge memory cache
        uses: actions/cache/restore@v4
        with:
          path: .knowledge
          key: knowledge-memory-${{ github.repository }}-${{ github.run_id }}-${{ github.run_attempt }}
          restore-keys: |
            knowledge-memory-${{ github.repository }}-

      - name: Run Knowledge bot
        env:
          MISTRAL_API_KEY: ${{ secrets.MISTRAL_API_KEY }}
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          KNOWLEDGE_MEMORY_PATH: .knowledge/memory.json
          COMMENT_BODY: ${{ github.event.comment.body }}
          COMMENT_AUTHOR: ${{ github.event.comment.user.login }}
          REPO_OWNER: ${{ github.repository_owner }}
          REPO_NAME: ${{ github.event.repository.name }}
          ISSUE_NUMBER: ${{ github.event.issue.number || github.event.pull_request.number }}
        run: |
          python knowledge_engine.py \
            --owner "$REPO_OWNER" \
            --repo "$REPO_NAME" \
            --issue "$ISSUE_NUMBER" \
            --comment "$COMMENT_BODY" \
            --author "$COMMENT_AUTHOR"

      - name: Save Knowledge memory cache
        if: always()
        uses: actions/cache/save@v4
        with:
          path: .knowledge
          key: knowledge-memory-${{ github.repository }}-${{ github.run_id }}-${{ github.run_attempt }}
```

The cache must restore and save `.knowledge`; otherwise each GitHub-hosted
runner loses Knowledge's memory after the job. Keep the unique run/attempt key
and repository restore prefix so a rerun can save updated state.

If the repository already has a workflow with the same name/path, do not
overwrite it. Present a minimal patch or ask which workflow should own the
trigger. If the project requires pinned action SHAs, apply that local policy to
the four actions above and report the pins used.

### Step 4 — create `KNOWLEDGE.md`

Generate a clean, repository-specific rulebook at the target root. Read the
target README, contribution/security files, source entry points, package
manifests, test configuration, and workflow files before filling it in. Do not
copy Knowledge-Agent's own rulebook verbatim and do not invent architecture or
protected paths.

If `KNOWLEDGE.md` already exists, extend it non-destructively with the missing
sections and preserve its verified project rules; ask before replacing content
that conflicts with the generated starter.

Use this shape, replacing every bracketed value with verified repository facts:

~~~markdown
# Repository Knowledge

This file gives Knowledge repository-specific context and guardrails. Keep it
short, factual, and update it when the architecture or contribution policy
changes.

## Repository architecture

- Purpose: [one verified sentence from the README or source]
- Runtime/entry points: [verified paths and what calls them]
- Main components: [paths and their responsibilities]
- Important data or request flow: [short evidence-backed flow]

## Protected paths and modules

- [path]: [why it is sensitive and which maintainer/review rule applies]
- If none are formally declared: `No protected paths are formally declared;
  ask a maintainer before changing security, authentication, data migrations,
  public APIs, deployment, or other high-impact boundaries.`

## Contribution rules

- [verified branch, review, ownership, formatting, or generated-file rule]
- [verified security or secret-handling rule]
- [verified documentation or compatibility rule]

## Testing commands

```text
[exact install command, if needed]
[exact lint/type-check command, if present]
[exact unit/integration test command]
```

## Unknowns

- [facts maintainers still need to document; use `None known` only after
  checking the repository]
~~~

Use `Unknown` or a clearly marked TODO for information that cannot be verified.
The rulebook is guidance injected into Knowledge's prompts; it is not a secret
store, a CODEOWNERS replacement, or permission to bypass repository review.

### Step 5 — validate the integration

Run only safe, relevant checks available in the target repository:

- validate YAML syntax with an installed YAML parser or the repository's CI
  tooling (do not claim validation if no parser is available);
- verify that all six runtime files exist side by side and compile/import
  without executing a provider call;
- check that the workflow references the exact secret and environment names;
- run `git diff --check`; and
- run the repository's documented tests when practical.

Never send a real provider request or post a GitHub comment as part of an
unannounced validation step. Do not log secret values.

## 4. Maintainer setup checklist

After editing the files, tell the maintainer to open **Settings → Secrets and
variables → Actions** in the target GitHub repository and add at least one of:

- `MISTRAL_API_KEY` — a Mistral API key; or
- `GEMINI_API_KEY` — a Google Gemini API key.

The workflow also receives GitHub's automatically provided `GITHUB_TOKEN`; the
maintainer must not create or paste that token into a file. The workflow's
permissions are limited to reading repository contents and writing issue/PR
comments. If both provider secrets are set, explain which provider the fetched
runtime selects and how to set the runtime's documented provider selector if a
different choice is desired.

## 5. First smoke test

Once a provider secret is saved, tell the maintainer to:

1. push the generated files to a branch and open/update a pull request (or use
   an existing issue);
2. add a comment such as
   `@Knowledge Summarize this issue, identify the relevant files, and tell me
   what I should verify before changing code.`; and
3. open the Actions run for **Knowledge AI Bot** and confirm that it restored
   the `.knowledge` cache, ran Python 3.11, and posted a reply on the same
   issue/PR.

If it does not run, check the comment spelling, the event type, workflow
permissions, repository Actions policy, and whether the selected provider
secret is present. Treat an API, permission, or network error as a setup issue;
do not weaken the workflow's secret handling to make the test pass.

## 6. Required completion report

At the end, report:

- files created, files downloaded, and files intentionally preserved;
- the upstream revision used for the runtime files;
- the validation commands run and their results;
- the exact secret names still needed from the maintainer; and
- any conflict, unsupported platform detail, or human decision that blocked a
  fully automatic installation.

Do not report “installed” until the workflow, runtime files, and rulebook are
present and internally consistent. Do not commit changes unless the developer
explicitly asks you to commit them.
