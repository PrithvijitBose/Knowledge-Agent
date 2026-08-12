"""
config.py — Backward-compatibility Shim
Re-exports configuration variables from `knowledge_engine.py`.
"""

import knowledge_engine

GITHUB_CLIENT_ID = knowledge_engine.GITHUB_CLIENT_ID
GITHUB_CLIENT_SECRET = knowledge_engine.GITHUB_CLIENT_SECRET
REDIRECT_URI = knowledge_engine.REDIRECT_URI
MISTRAL_API_KEY = knowledge_engine.MISTRAL_API_KEY
MISTRAL_MODEL = knowledge_engine.MISTRAL_MODEL

def is_github_configured() -> bool:
    return knowledge_engine.is_github_configured()

def is_mistral_configured() -> bool:
    return knowledge_engine.is_mistral_configured()
