"""OpenRouter provider — free-tier models via OpenAI-compatible API.

Thin wrapper used by the Streamlit UI to display provider availability.
Actual routing is handled by the LiteLLM Router in src/agents/llm_utils.py.
"""
from src.agents.llm_utils import call_llm
import os

PROVIDER_NAME  = "openrouter"
DEFAULT_MODEL  = "meta-llama/llama-3.3-70b-instruct:free"


def complete(system_prompt: str, user_prompt: str, **kwargs) -> str:
    """Call through the shared LiteLLM Router. For isolated OpenRouter testing."""
    return call_llm(system_prompt, user_prompt, **kwargs)


def is_available() -> bool:
    """True if OpenRouter API key is configured."""
    return bool(os.environ.get("OPENROUTER_API_KEY", ""))
