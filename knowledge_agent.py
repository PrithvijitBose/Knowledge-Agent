"""
knowledge_agent.py — Backward-compatibility Shim
Canonical package is `knowledge_agent`.
"""

from knowledge_agent import *  # noqa: F401,F403

if __name__ == "__main__":
    from knowledge_agent.__main__ import main
    main()
