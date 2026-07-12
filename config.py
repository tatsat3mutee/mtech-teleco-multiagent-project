"""
Central configuration for the Multi-Agent RAG Telecom Billing RCA System.
Repository: tatsat3mutee/mtech-teleco-multiagent-project
"""
import os
from pathlib import Path

# ── Project Root ──
PROJECT_ROOT = Path(__file__).parent.resolve()

# ── Data Paths ──
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
CORPUS_DIR = DATA_DIR / "corpus"
RCA_PLAYBOOKS_DIR = CORPUS_DIR / "rca_playbooks"
EVAL_DIR = DATA_DIR / "eval"
GROUND_TRUTH_DIR = EVAL_DIR / "ground_truth_rca"

# ── Model Paths ──
MODELS_DIR = PROJECT_ROOT / "models"

# ── ChromaDB ──
CHROMA_PERSIST_DIR = PROJECT_ROOT / "chroma_db"
CHROMA_COLLECTION_NAME = "telecom_billing_kb"

# ── Embedding Model ──
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIMENSIONS = 384

# ── Chunking ──
CHUNK_SIZE = 512
CHUNK_OVERLAP = 64

# ── Retrieval ──
TOP_K = 5

# ── LLM (Groq primary, OpenRouter fallback — 2 keys total) ──
#
# Priority order:
#   1. Groq  (free tier, fast inference; GPT OSS 120B replaces deprecated Llama 3.3 70B)
#   2. OpenRouter  (free-tier models: GPT OSS 120B, Qwen, Llama 3.3 70B)
#
# call_llm() tries the Groq router group first, then the OpenRouter fallback
# group if Groq fails or rate-limits.

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

GROQ_API_KEY       = os.environ.get("GROQ_API_KEY", "")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

# Provider priority — used by llm_utils.get_active_provider() for UI display
LLM_PROVIDER_PRIORITY = ["groq", "openrouter"]

# ── API Security ──
RCA_API_KEY = os.environ.get("RCA_API_KEY", "")  # empty = auth disabled (dev mode)
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:8501,http://localhost:3000").split(",")

# ── Single-provider fallback for legacy code paths ──
_explicit_key   = os.environ.get("LLM_API_KEY", "")
_explicit_base  = os.environ.get("LLM_BASE_URL", "")
_explicit_model = os.environ.get("LLM_MODEL", "")

if _explicit_key:
    LLM_API_KEY  = _explicit_key
    LLM_BASE_URL = _explicit_base
    LLM_MODEL    = _explicit_model or "openai/gpt-oss-120b"
    LLM_PROVIDER = "custom"
elif GROQ_API_KEY:
    LLM_API_KEY  = GROQ_API_KEY
    LLM_BASE_URL = "https://api.groq.com/openai/v1"
    LLM_MODEL    = _explicit_model or "openai/gpt-oss-120b"
    LLM_PROVIDER = "groq"
elif OPENROUTER_API_KEY:
    LLM_API_KEY  = OPENROUTER_API_KEY
    LLM_BASE_URL = "https://openrouter.ai/api/v1"
    LLM_MODEL    = _explicit_model or "meta-llama/llama-3.3-70b-instruct:free"
    LLM_PROVIDER = "openrouter"
else:
    LLM_API_KEY  = ""
    LLM_BASE_URL = ""
    LLM_MODEL    = _explicit_model or "openai/gpt-oss-120b"
    LLM_PROVIDER = "none"

LLM_TEMPERATURE = 0.1

# ── LiteLLM Router Config — rate-limit-aware multi-model fallback ──────────
# Groq is attempted first by call_llm(); OpenRouter slots are used only as the
# fallback group if Groq fails or rate-limits.
LITELLM_ROUTER_CONFIG = [
    {
        "model_name": "groq-primary",
        "litellm_params": {
            "model":   "groq/openai/gpt-oss-120b",
            "api_key": GROQ_API_KEY,
        },
        "rpm": 28,   # stay under Groq's 30 req/min hard cap
        "tpm": 7500, # observed live: gpt-oss-120b on-demand tier caps at 8,000 TPM
                     # (429 on EC2, 2026-07-12) — throttle below it proactively
    },
    {
        "model_name": "openrouter-fallback",
        "litellm_params": {
            "model":    "openrouter/openai/gpt-oss-120b:free",
            "api_key":  OPENROUTER_API_KEY,
            "api_base": "https://openrouter.ai/api/v1",
        },
        "rpm": 18,
    },
    {
        "model_name": "openrouter-fallback",
        "litellm_params": {
            "model":    "openrouter/meta-llama/llama-3.3-70b-instruct:free",
            "api_key":  OPENROUTER_API_KEY,
            "api_base": "https://openrouter.ai/api/v1",
        },
        "rpm": 18,
    },
    {
        "model_name": "openrouter-fallback",
        "litellm_params": {
            "model":    "openrouter/qwen/qwen3-coder:free",
            "api_key":  OPENROUTER_API_KEY,
            "api_base": "https://openrouter.ai/api/v1",
        },
        "rpm": 18,
    },
]

# ── Observability (Langfuse) ────────────────────────────────────────────────
# Free at cloud.langfuse.com — 50K observations/month, sufficient for thesis.
# When both keys are set, every LiteLLM call is traced to Langfuse automatically
# with agent name, provider, latency, token count, and full prompt/response.
LANGFUSE_PUBLIC_KEY = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.environ.get("LANGFUSE_SECRET_KEY", "")
LANGFUSE_HOST       = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")

# ── Judge LLM (evaluation) ──
# Judge independence: the generator uses Groq GPT-OSS-120B, so the judge
# defaults to a DIFFERENT model family (Llama 3.3 70B via OpenRouter) to avoid
# self-affinity bias in LLM-as-Judge scoring. Falls back to Groq only when no
# OpenRouter key is configured. Override JUDGE_* env vars for a fully separate
# provider (e.g., GPT-4o / Claude) on the final evaluation run.
if os.environ.get("JUDGE_API_KEY"):
    JUDGE_API_KEY  = os.environ["JUDGE_API_KEY"]
    JUDGE_BASE_URL = os.environ.get("JUDGE_BASE_URL", "https://api.groq.com/openai/v1")
    JUDGE_MODEL    = os.environ.get("JUDGE_MODEL", "openai/gpt-oss-120b")
elif OPENROUTER_API_KEY:
    JUDGE_API_KEY  = OPENROUTER_API_KEY
    JUDGE_BASE_URL = os.environ.get("JUDGE_BASE_URL", "https://openrouter.ai/api/v1")
    JUDGE_MODEL    = os.environ.get("JUDGE_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
else:
    JUDGE_API_KEY  = GROQ_API_KEY
    JUDGE_BASE_URL = os.environ.get("JUDGE_BASE_URL", "https://api.groq.com/openai/v1")
    JUDGE_MODEL    = os.environ.get("JUDGE_MODEL", "openai/gpt-oss-120b")
JUDGE_TEMPERATURE  = 0.0  # deterministic scoring
JUDGE_FALLBACK_MODEL = LLM_MODEL

# ── Ablation Study Configurations ──
ABLATION_CONFIGS = {
    "no_rag": {
        "use_rag": False,
        "use_agents": False,
        "description": "Config A: Direct LLM — no RAG, no agents",
    },
    "cot_baseline": {
        "use_rag": False,
        "use_agents": False,
        "description": "Config A2: Few-shot Chain-of-Thought baseline — no retrieval",
    },
    "react_baseline": {
        "use_rag": True,
        "use_agents": False,
        "description": "Config A3: ReAct baseline — reason/act/observe loop with retrieval",
    },
    "rag_only": {
        "use_rag": True,
        "use_agents": False,
        "description": "Config B: RAG + LLM — no agent decomposition",
    },
    "single_agent_rag": {
        "use_rag": True,
        "use_agents": True,
        "single_agent": True,
        "description": "Config C: Single Agent + RAG",
    },
    "multi_agent_rag": {
        "use_rag": True,
        "use_agents": True,
        "single_agent": False,
        "description": "Config D: Multi-Agent + RAG (proposed system)",
    },
    "graph_rag": {
        "use_rag": True,
        "use_agents": True,
        "single_agent": False,
        "use_graph_rag": True,
        "description": "Config E: Multi-Agent + GraphRAG (headline novelty)",
    },
}

# ── Anomaly Detection ──
RANDOM_SEED = 42
AUGMENTED_TARGET_SIZE = 35_000  # Augmented dataset size (ROSE-style oversampling)
ANOMALY_RATIOS = {
    "zero_billing": 0.03,
    "duplicate_charge": 0.02,
    "usage_spike": 0.03,
    "cdr_failure": 0.015,
    "sla_breach": 0.02,
}
ISOLATION_FOREST_PARAMS = {
    "n_estimators": 200,
    "contamination": 0.1,
    "max_features": 0.8,
    "random_state": RANDOM_SEED,
}

# ── Anomaly Type Classification Thresholds ──
# Used by detector._estimate_anomaly_type() — configurable per dataset
ANOMALY_TYPE_THRESHOLDS = {
    "duplicate_charge_min": 200,   # MonthlyCharges > this → duplicate_charge
    "sla_breach_min": 150,         # MonthlyCharges > this → sla_breach
    "usage_spike_ratio": 0.5,      # MonthlyCharges > TotalCharges * ratio → usage_spike
}

# ── MLflow ──
# Env-first: docker-compose points at the MLflow server (http://mlflow:5000);
# bare-metal/dev falls back to the local ./mlruns file store.
MLFLOW_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "mlruns")
MLFLOW_EXPERIMENT_NAME = "telecom_billing_rca"
