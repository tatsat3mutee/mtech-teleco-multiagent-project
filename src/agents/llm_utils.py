"""
LLM utility — LiteLLM Router with 2-provider fallback (Groq + OpenRouter)
and optional Langfuse observability.

Architecture:
    call_llm() → LiteLLM.Router → group 1: groq/openai/gpt-oss-120b              (rpm=28)
                              → group 2: OpenRouter free fallback pool          (rpm=18 each)
                                      ↓
                               Langfuse trace  (if LANGFUSE_PUBLIC_KEY is set)

Why LiteLLM Router over a manual loop?
  - Tracks req/min per provider in real-time — shifts traffic before hitting 429
  - Cooldown: failed provider is excluded for 60s, then re-added automatically
  - No code changes in agents needed — routing is transparent
  - Single callback line activates structured tracing in Langfuse

External API: call_llm(system_prompt, user_prompt, ...) — signature unchanged.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import (
    GROQ_API_KEY,
    OPENROUTER_API_KEY,
    LLM_TEMPERATURE,
    LLM_PROVIDER_PRIORITY,
    LITELLM_ROUTER_CONFIG,
    LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST,
)

import litellm

litellm.drop_params = True   # silently ignore provider-unsupported params
litellm.set_verbose = False  # suppress per-call debug output


# ── Langfuse observability ───────────────────────────────────────────────────
def _setup_langfuse() -> bool:
    """
    Enable Langfuse tracing when keys are present.

    LiteLLM's success_callback fires after every successful completion and
    ships the full span (provider, model, latency, token counts, prompt,
    response) to Langfuse cloud.langfuse.com.  Requires no code changes in
    individual agents — all 4 agents are traced automatically.

    Returns True when tracing is active.
    """
    if not (LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY):
        return False
    os.environ.setdefault("LANGFUSE_PUBLIC_KEY", LANGFUSE_PUBLIC_KEY)
    os.environ.setdefault("LANGFUSE_SECRET_KEY", LANGFUSE_SECRET_KEY)
    os.environ.setdefault("LANGFUSE_HOST",       LANGFUSE_HOST)
    if "langfuse" not in litellm.success_callback:
        litellm.success_callback.append("langfuse")
    return True


_LANGFUSE_ACTIVE: bool = _setup_langfuse()


# ── Provider → LiteLLM model-string mapping (used by get_active_provider) ───
_LITELLM_MODEL: dict[str, str] = {
    "groq":        "groq/openai/gpt-oss-120b",
    "openrouter":  "openrouter/openai/gpt-oss-120b:free",
}

_PROVIDER_KEY: dict[str, str] = {
    "groq":        GROQ_API_KEY,
    "openrouter":  OPENROUTER_API_KEY,
}

# ── LiteLLM Router singleton ─────────────────────────────────────────────────
from litellm import Router as _LiteLLMRouter

_router: Optional[_LiteLLMRouter] = None


def get_router() -> _LiteLLMRouter:
    """Return (or lazily create) the shared LiteLLM Router instance."""
    global _router
    if _router is None:
        _router = _LiteLLMRouter(
            model_list=LITELLM_ROUTER_CONFIG,
            routing_strategy="least-busy",
            num_retries=3,
            retry_after=2,        # wait 2s before retry on 429
            allowed_fails=2,      # skip a provider after 2 consecutive failures
            cooldown_time=60,     # don't retry a failed provider for 60s
        )
    return _router


# ── Public API ───────────────────────────────────────────────────────────────
def call_llm(
    system_prompt: str,
    user_prompt:   str,
    temperature:   float = None,
    model:         str   = None,
    trace_name:    str   = "rca_agent",
    session_id:    str   = None,
    max_retries:   int   = 2,
) -> Optional[str]:
    """
    Call the LLM via LiteLLM Router with automatic rate-limit-aware fallback.

    Fallback order:
        Groq GPT OSS 120B → OpenRouter free-model pool
    Groq is always attempted first; OpenRouter is used only if Groq fails or rate-limits.

    Observability:
        When LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY are set, every call
        is traced to Langfuse with:
          - generation_name  = trace_name (e.g. "investigator", "reasoner")
          - session_id       = session_id (groups all calls for one RCA run)
          - tags             = [provider, "telecom-rca"]

    Parameters
    ----------
    system_prompt : str
        System-role message.
    user_prompt : str
        User-role message.
    temperature : float, optional
        Sampling temperature (default: config.LLM_TEMPERATURE = 0.1).
    model : str, optional
        Override the default model slug (provider prefix is added automatically).
    trace_name : str
        Langfuse generation name — use the calling agent's name for
        visibility in the observability dashboard.
    session_id : str, optional
        Groups all LLM calls for a single RCA run in Langfuse.
    max_retries : int
        Per-provider retry count for transient errors (rate-limit, timeout).

    Returns
    -------
    str or None
        Content string from the first successful provider, or None if all fail.
    """
    if temperature is None:
        temperature = LLM_TEMPERATURE

    # Bail early when no provider keys are configured (test / offline mode).
    if not any(_PROVIDER_KEY.values()):
        print("[LLM] No provider keys configured — returning None.")
        return None

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_prompt},
    ]

    metadata: dict = {
        "generation_name": trace_name,
        "tags": ["telecom-rca"],
    }
    if session_id:
        metadata["session_id"] = session_id

    router = get_router()
    model_groups: list[str] = []
    if GROQ_API_KEY:
        model_groups.append("groq-primary")
    if OPENROUTER_API_KEY:
        model_groups.append("openrouter-fallback")

    for model_group in model_groups:
        try:
            resp = router.completion(
                model=model_group,
                messages=messages,
                temperature=temperature,
                timeout=60,
                metadata=metadata,
            )
            content = resp.choices[0].message.content
            model_used = getattr(resp, "model", model_group)
            print(f"[LLM] model={model_used} trace={trace_name}")
            return content
        except Exception as e:
            print(f"[LLM] Router group failed ({model_group}): {e}")

    return None


def get_active_provider() -> str:
    """Return name of first provider with a configured API key. For UI display."""
    for p in LLM_PROVIDER_PRIORITY:
        if _PROVIDER_KEY.get(p):
            return p
    return "none"


def observability_active() -> bool:
    """Return True when Langfuse tracing is enabled."""
    return _LANGFUSE_ACTIVE
