"""
Tests for the 2-provider LLM Router in llm_utils.py.
All LLM calls are mocked — no real API keys required.
"""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_provider_registry_fallback():
    """With all API keys empty, call_llm returns None gracefully."""
    with patch.dict("os.environ", {
        "GROQ_API_KEY":       "",
        "OPENROUTER_API_KEY": "",
        "LLM_API_KEY":        "",
    }):
        # Re-import with cleared keys via a fresh import of the module
        import importlib
        import config as cfg
        importlib.reload(cfg)
        import src.agents.llm_utils as lu
        importlib.reload(lu)

        # With no keys, Router bails early → None
        result = lu.call_llm("system", "user")
        assert result is None


def test_get_active_provider_no_keys():
    """get_active_provider returns 'none' when no API keys are configured."""
    import importlib
    import src.agents.llm_utils as lu

    with patch.dict("os.environ", {
        "GROQ_API_KEY":       "",
        "OPENROUTER_API_KEY": "",
    }):
        import config as cfg
        with patch.object(cfg, "GROQ_API_KEY", ""), \
             patch.object(cfg, "OPENROUTER_API_KEY", ""):
            importlib.reload(lu)
            provider = lu.get_active_provider()
            assert provider == "none"

    # Restore module state
    importlib.reload(lu)


def test_get_active_provider_openrouter_fallback():
    """get_active_provider returns 'openrouter' when only OpenRouter key is set."""
    import importlib
    import src.agents.llm_utils as lu

    with patch.dict("os.environ", {
        "GROQ_API_KEY":       "",
        "OPENROUTER_API_KEY": "sk-or-test",
    }):
        import config as cfg
        with patch.object(cfg, "GROQ_API_KEY", ""), \
             patch.object(cfg, "OPENROUTER_API_KEY", "sk-or-test"):
            importlib.reload(lu)
            provider = lu.get_active_provider()
            assert provider == "openrouter"

    importlib.reload(lu)


def test_call_llm_signature_unchanged():
    """call_llm accepts the same signature as the original single-provider version."""
    from src.agents.llm_utils import call_llm
    import inspect
    sig = inspect.signature(call_llm)
    params = list(sig.parameters.keys())
    assert "system_prompt" in params
    assert "user_prompt" in params
    assert "temperature" in params
    assert "model" in params


def test_provider_priority_order():
    """LLM_PROVIDER_PRIORITY contains exactly 2 providers with Groq first."""
    from config import LLM_PROVIDER_PRIORITY
    assert set(LLM_PROVIDER_PRIORITY) == {"groq", "openrouter"}
    assert LLM_PROVIDER_PRIORITY[0] == "groq"  # Groq is always primary


def test_litellm_model_string_format():
    """Every provider model string must follow the LiteLLM 'provider/model' format."""
    from src.agents.llm_utils import _LITELLM_MODEL
    for provider, model_str in _LITELLM_MODEL.items():
        assert "/" in model_str, (
            f"{provider} model string missing provider prefix: {model_str!r}"
        )
        prefix, name = model_str.split("/", 1)
        assert prefix and name, f"{provider} model string malformed: {model_str!r}"


def test_router_config_has_primary_slots():
    """LITELLM_ROUTER_CONFIG must define both routing groups with valid slots."""
    from config import LITELLM_ROUTER_CONFIG
    assert len(LITELLM_ROUTER_CONFIG) == 4
    groups = {slot["model_name"] for slot in LITELLM_ROUTER_CONFIG}
    assert groups == {"groq-primary", "openrouter-fallback"}, (
        f"unexpected router groups: {groups}"
    )
    for slot in LITELLM_ROUTER_CONFIG:
        assert "model" in slot["litellm_params"]
        assert "/" in slot["litellm_params"]["model"]
