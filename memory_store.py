"""Compatibility shim. Canonical home is knowledge_agent.memory_store."""
import sys
import knowledge_agent.memory_store
from knowledge_agent.memory_store import *  # noqa: F401,F403

sys.modules[__name__] = knowledge_agent.memory_store
