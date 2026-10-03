# Knowledge MCP Server — Engineering Context Layer for Coding Agents

Knowledge can run as a native [Model Context Protocol](https://modelcontextprotocol.io) server, so coding agents
(Cursor, Claude Desktop, Claude Code, Windsurf, Devin) can query Knowledge's **bounded evidence engine**, **AST
doc-verifier**, and **issue/PR lineage** directly instead of guessing at your architecture.

---

## 1. Installation

```bash
# From a clone of this repository
pip install -e ".[mcp]"

# Or add the SDK to an existing install
pip install "mcp>=1.9.0"
```

The MCP SDK is an **optional dependency**. The GitHub bot and every other entry point work without it; only
`knowledge-agent mcp` requires it.

Both SDK lines are supported: `mcp<2` (`FastMCP`) and `mcp>=2` (`MCPServer`).

---

## 2. Running the Server

### stdio (recommended for desktop clients)

```bash
knowledge-agent mcp --stdio
# Equivalent: python -m knowledge_agent mcp --stdio
```

Your client spawns the process and speaks JSON-RPC over stdin/stdout. Nothing is printed to stdout other than
protocol traffic.

### SSE (for long-running or shared servers)

```bash
knowledge-agent mcp --sse --host 127.0.0.1 --port 8765
```

The server then exposes an SSE endpoint at `http://127.0.0.1:8765/sse`.

| Flag | Default | Meaning |
| :--- | :--- | :--- |
| `--stdio` | on | Serve over stdio (used by Claude Desktop, Cursor, Claude Code). |
| `--sse` | off | Serve over SSE instead of stdio. |
| `--host` | `127.0.0.1` | Bind address for the SSE transport. |
| `--port` | `8765` | Port for the SSE transport. |

---

## 3. Available Tools

### `knowledge_get_architecture_context(query: str, repo_path: str = ".")`

Returns the grounded mental model and evidence chain for a subsystem.

- Ranks repository files against the query (path matches weigh more than body matches).
- Extracts **real** functions, classes, HTTP routes, and environment variables from source via the same AST
  extractor used by the bot.
- Includes `KNOWLEDGE.md` repository rules when present.
- Returns an `evidence` list with file paths and line numbers, plus explicit `unknowns`.

`repo_path` is a local directory (fully offline). When `GITHUB_TOKEN` is set, an `owner/repo` slug is resolved
through the API instead.

### `knowledge_verify_doc_drift(doc_path: str, code_dir: str)`

Runs `DocDiscrepancyDetector` and returns mismatches between documentation claims and actual code symbols:
missing implementations, signature mismatches, and environment-variable drift. `doc_path` accepts a single
document or a directory of documents.

### `knowledge_trace_issue_pr(issue_number: int)`

Returns the complete bidirectional history for an issue: maintainer directives, contributor discussion, previous
attempts (linked PRs with merge state and changed files), and the issues those PRs themselves reference.

Requires `GITHUB_TOKEN`. The repository is resolved from `KNOWLEDGE_OWNER` + `KNOWLEDGE_REPO`, or from
`GITHUB_REPOSITORY` in the form `owner/repo`.

---

## 4. Client Configuration

### Claude Desktop — `claude_desktop_config.json`

macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "knowledge": {
      "command": "knowledge-agent",
      "args": ["mcp", "--stdio"],
      "env": {
        "GITHUB_TOKEN": "ghp_your_token_here",
        "KNOWLEDGE_OWNER": "your-org",
        "KNOWLEDGE_REPO": "your-repo"
      }
    }
  }
}
```

If `knowledge-agent` is not on your `PATH`, use the interpreter directly:

```json
{
  "mcpServers": {
    "knowledge": {
      "command": "/absolute/path/to/venv/bin/knowledge-agent",
      "args": ["mcp", "--stdio"],
      "env": {
        "GITHUB_TOKEN": "ghp_your_token_here"
      }
    }
  }
}
```

### Cursor — `.cursor/mcp.json` (project) or `~/.cursor/mcp.json` (global)

```json
{
  "mcpServers": {
    "knowledge": {
      "command": "knowledge-agent",
      "args": ["mcp", "--stdio"],
      "env": {
        "GITHUB_TOKEN": "ghp_your_token_here",
        "KNOWLEDGE_OWNER": "your-org",
        "KNOWLEDGE_REPO": "your-repo"
      }
    }
  }
}
```

### Claude Code

```bash
claude mcp add knowledge -- knowledge-agent mcp --stdio
```

### Cursor over SSE

Start the server separately, then point Cursor at the endpoint:

```bash
knowledge-agent mcp --sse --port 8765
```

```json
{
  "mcpServers": {
    "knowledge": {
      "url": "http://127.0.0.1:8765/sse"
    }
  }
}
```

---

## 5. Example Tool Output

`knowledge_get_architecture_context` returns a JSON payload shaped like:

```json
{
  "ok": true,
  "tool": "knowledge_get_architecture_context",
  "query": "auth login",
  "repo_path": "/path/to/repo",
  "source": "local",
  "intent": "ARCHITECTURE_UNDERSTANDING",
  "keywords": ["auth", "login"],
  "mental_model": {
    "subsystems": [
      {
        "file": "app/auth.py",
        "relevance_score": 31,
        "function_count": 2,
        "class_count": 1,
        "key_symbols": ["AuthService", "login(user, password)"]
      }
    ],
    "functions": [{ "name": "login", "args": ["user", "password"], "file": "app/auth.py", "line": 6 }],
    "classes": [{ "name": "AuthService", "methods": ["login"], "file": "app/auth.py", "line": 4 }],
    "http_routes": [],
    "environment_variables": ["AUTH_TOKEN"]
  },
  "repository_rules": "# Rules\n\n- Never log tokens.",
  "evidence": [{ "file": "app/auth.py", "start_line": 6, "end_line": 6, "why": "...", "excerpt": "..." }],
  "unknowns": []
}
```

When the repository does **not** contain enough evidence, the payload comes back with `"ok": false` and a populated
`unknowns` list rather than a fabricated answer.

---

## 6. Programmatic Use

```python
from knowledge_agent.mcp_server import KnowledgeContextTools, build_server, run_stdio, run_sse

# Call the tool logic directly (no SDK required)
tools = KnowledgeContextTools()
context = tools.get_architecture_context("how does auth work", repo_path=".")
drift = tools.verify_doc_drift(doc_path="README.md", code_dir="knowledge_agent")
lineage = tools.trace_issue_pr(issue_number=42)

# Or drive the MCP server
server = build_server(tools)   # registers all three tools
run_stdio()                    # or run_sse(host="127.0.0.1", port=8765)
```

---

## 7. Troubleshooting

| Symptom | Cause | Fix |
| :--- | :--- | :--- |
| `The official MCP SDK is not installed.` | `mcp` extra not installed | `pip install "knowledge-agent[mcp]"` |
| Client shows no tools | Command not found or wrong path | Use the absolute interpreter path from your venv |
| `knowledge_trace_issue_pr` returns `ok: false` | Missing token or repo | Set `GITHUB_TOKEN` and `KNOWLEDGE_OWNER` / `KNOWLEDGE_REPO` |
| Claude Desktop logs are empty | Extra stdout from the process | Only the server may write to stdout; use stderr for debugging |