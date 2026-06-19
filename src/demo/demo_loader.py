"""
Demo mode loader — serves pre-computed RCA results when no API keys are configured.

is_demo_mode() returns True if all 4 API keys are absent from the environment.
load_demo_results() returns the pre-computed results from data/demo/.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

_DEMO_DIR = Path(__file__).resolve().parents[2] / "data" / "demo"
_DEMO_RESULTS_PATH = _DEMO_DIR / "sample_rca_results.json"

_API_KEY_ENV_VARS = [
    "GROQ_API_KEY",
    "OPENROUTER_API_KEY",
]


def is_demo_mode() -> bool:
    """True when neither LLM provider API key is configured."""
    return all(not os.environ.get(k, "").strip() for k in _API_KEY_ENV_VARS)


def load_demo_results() -> List[Dict[str, Any]]:
    """Load pre-computed RCA results from data/demo/sample_rca_results.json."""
    if not _DEMO_RESULTS_PATH.exists():
        return []
    try:
        with open(_DEMO_RESULTS_PATH) as f:
            data = json.load(f)
        return data if isinstance(data, list) else data.get("results", [])
    except Exception:
        return []


def get_demo_result_for_type(anomaly_type: str) -> Optional[Dict[str, Any]]:
    """Return the first demo result matching the given anomaly type, or None."""
    for result in load_demo_results():
        rca = result.get("rca_report", {})
        if rca.get("anomaly_type") == anomaly_type or result.get("anomaly_type") == anomaly_type:
            return result
    return None
