"""
config.py — Backward-compatibility Shim
Re-exports configuration variables from `knowledge_engine.py` and `providers.py`.
"""

import knowledge_engine
import providers

GITHUB_CLIENT_ID = knowledge_engine.GITHUB_CLIENT_ID
GITHUB_CLIENT_SECRET = knowledge_engine.GITHUB_CLIENT_SECRET
REDIRECT_URI = knowledge_engine.REDIRECT_URI
MISTRAL_API_KEY = knowledge_engine.MISTRAL_API_KEY
MISTRAL_MODEL = knowledge_engine.MISTRAL_MODEL


def is_github_configured() -> bool:
    return knowledge_engine.is_github_configured()


def is_mistral_configured() -> bool:
    return knowledge_engine.is_mistral_configured()


def is_llm_configured(provider_name: str = None) -> bool:
    return knowledge_engine.is_llm_configured(provider_name)


def get_provider(provider_name: str = None, model: str = None):
    return providers.get_provider(provider_name, model=model)


def list_providers():
    return providers.list_providers()


def load_local_config(directory: str = ".") -> dict:
    """Load local configuration from .knowledge-agent.json or .knowledge-agent.yaml."""
    import os
    import json
    for filename in [".knowledge-agent.json", ".knowledge-agent.yaml", ".knowledge-agent.yml"]:
        target = os.path.join(directory, filename)
        if os.path.exists(target):
            try:
                with open(target, "r", encoding="utf-8") as f:
                    content = f.read()
                if filename.endswith(".json"):
                    return json.loads(content)
                res = {}
                for line in content.splitlines():
                    if ":" in line and not line.strip().startswith("#"):
                        k, v = line.split(":", 1)
                        res[k.strip()] = v.strip().strip('"').strip("'")
                return res
            except Exception:
                return {}
    return {}
