# Contributing to Knowledge-Agent

Thank you for your interest in contributing to Knowledge-Agent! We welcome bug fixes, documentation improvements, new LLM provider integrations, and workflow enhancements.

---

## Development Setup

1. **Clone your fork:**
   ```bash
   git clone https://github.com/<your-username>/Knowledge-Agent.git
   cd Knowledge-Agent
   ```

2. **Set up a virtual environment & install dependencies:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env and configure GITHUB_TOKEN and your LLM API keys
   ```

---

## Running Tests Hermetically

All tests in Knowledge-Agent are designed to be hermetic and execute offline without outbound network calls:

```bash
# Run all unit tests
python -m unittest discover -s . -p "test_*.py"

# Run tests in the tests/ directory
python -m unittest discover -s tests
```

Ensure all tests pass before submitting a pull request.

---

## Code Guidelines

- **Zero-SDK LLM Adapters:** When adding or updating LLM providers in `providers.py`, use standard REST calls with `httpx` to avoid heavy external SDK dependencies.
- **Security & Vulnerability Disclosure:** Never interpolate untrusted user comment bodies directly into shell commands. Pass them via environment variables. Verify HMAC signatures for all webhook endpoints. If you discover a security vulnerability, please report it privately through [GitHub Security Advisories](https://github.com/PrithvijitBose/Knowledge-Agent/security/advisories) rather than opening a public issue. Maintainers aim to acknowledge reports within 48 hours.
- **Tone & Commits:** Use conventional commit messages (`feat:`, `fix:`, `docs:`, `chore:`, `refactor:`).

---

## Submitting Pull Requests

1. Open an issue describing the bug or feature proposal first.
2. Create a topic branch from `main`:
   ```bash
   git checkout -b feat/your-feature-name
   ```
3. Commit your changes with concise messages and add unit tests.
4. Push your branch to your fork and open a Pull Request linking to the issue (`Fixes #<issue-number>`).
