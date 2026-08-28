import os
from typing import Optional
from dotenv import load_dotenv
import providers

load_dotenv()

GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")
REDIRECT_URI = os.getenv("REDIRECT_URI", "http://localhost:8501")

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-small-2506")
MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"
GITHUB_API_BASE = "https://api.github.com"
GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"


def is_github_configured() -> bool:
    """Check if GitHub OAuth credentials are configured."""
    return bool(
        GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET and
        GITHUB_CLIENT_ID != "your_github_client_id" and
        GITHUB_CLIENT_SECRET != "your_github_client_secret"
    )


def is_mistral_configured() -> bool:
    """Check if Mistral API key is configured."""
    return bool(MISTRAL_API_KEY and MISTRAL_API_KEY != "your_mistral_api_key")


def is_llm_configured(provider_name: Optional[str] = None) -> bool:
    """Check if the active or specified LLM provider is configured."""
    return providers.get_provider(provider_name).is_configured()


def get_max_file_chars() -> int:
    try:
        return int(os.getenv("KNOWLEDGE_MAX_FILE_CHARS", "3000"))
    except ValueError:
        return 3000


def get_max_comment_chars() -> int:
    try:
        return int(os.getenv("KNOWLEDGE_MAX_COMMENT_CHARS", "2500"))
    except ValueError:
        return 2500


def get_max_diff_chars() -> int:
    try:
        return int(os.getenv("KNOWLEDGE_MAX_DIFF_CHARS", "1500"))
    except ValueError:
        return 1500


def get_max_diff_budget() -> int:
    try:
        val = os.getenv("KNOWLEDGE_MAX_DIFF_BUDGET")
        if val is not None:
            return int(val)
        val2 = os.getenv("KNOWLEDGE_MAX_DIFF_CHARS")
        if val2 is not None:
            return int(val2)
        return 14000
    except ValueError:
        return 14000
