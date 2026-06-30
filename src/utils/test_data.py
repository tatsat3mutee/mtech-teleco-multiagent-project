"""Derive ablation test anomalies from the 60-item ground-truth set.

Each GT row becomes one synthetic anomaly record with plausible numeric
features so detection-downstream code keeps working. The `ground_truth_id`
tag is preserved so evaluation can pick the exact reference RCA rather than
falling back to anomaly-type matching.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path
from typing import List, Dict

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import GROUND_TRUTH_DIR, RANDOM_SEED
from src.evaluation.metrics import load_ground_truth


_FEATURE_PROFILES = {
    "zero_billing": {
        "monthly_charges_fn": lambda r: 0.0,
        "total_charges_fn": lambda r: r.random() * 5500 + 400,
        "internet": ["Fiber optic", "DSL", "Fiber optic"],
        "contract": ["Two year", "Month-to-month", "One year"],
    },
    "duplicate_charge": {
        "monthly_charges_fn": lambda r: r.choice([89.5, 159.9, 210.4, 145.0, 265.0]) * 2,
        "total_charges_fn": lambda r: r.random() * 9000 + 900,
        "internet": ["Fiber optic", "Fiber optic", "DSL"],
        "contract": ["One year", "Two year", "Month-to-month"],
    },
    "usage_spike": {
        "monthly_charges_fn": lambda r: r.choice([620, 850, 1100, 950, 720]),
        "total_charges_fn": lambda r: r.random() * 7500 + 1000,
        "internet": ["Fiber optic", "Fiber optic", "DSL"],
        "contract": ["Month-to-month", "Month-to-month", "One year"],
    },
    "cdr_failure": {
        "monthly_charges_fn": lambda r: 0.0,
        "total_charges_fn": lambda r: 0.0,
        "internet": ["DSL", "Fiber optic", "DSL"],
        "contract": ["Month-to-month", "One year", "Month-to-month"],
    },
    "sla_breach": {
        "monthly_charges_fn": lambda r: r.choice([180, 250, 320, 275, 410]),
        "total_charges_fn": lambda r: r.random() * 10000 + 3000,
        "internet": ["Fiber optic", "Fiber optic", "Fiber optic"],
        "contract": ["Two year", "One year", "Two year"],
    },
}


def anomalies_from_ground_truth(limit_per_type: int = 12, seed: int = RANDOM_SEED) -> List[Dict]:
    """Build test anomalies from the GT set. Deterministic for a given seed.

    Args:
        limit_per_type: Max rows per anomaly_type (GT has 12). Use 3 for fast runs.
        seed: RNG seed so features are reproducible across runs.
    """
    gt = load_ground_truth()
    rng = random.Random(seed)
    buckets: Dict[str, List[dict]] = {}
    for row in gt:
        buckets.setdefault(row["anomaly_type"], []).append(row)

    anomalies: List[dict] = []
    for atype, rows in buckets.items():
        profile = _FEATURE_PROFILES.get(atype, _FEATURE_PROFILES["zero_billing"])
        for i, row in enumerate(rows[:limit_per_type]):
            tenure = rng.randint(3, 72)
            anomalies.append({
                "account_id": f"ABL-{row['anomaly_id']}",
                "ground_truth_id": row["anomaly_id"],
                "anomaly_type": atype,
                "confidence": round(0.80 + rng.random() * 0.18, 2),
                "monthly_charges": float(profile["monthly_charges_fn"](rng)),
                "total_charges": float(profile["total_charges_fn"](rng)),
                "tenure": tenure,
                "features": {
                    "InternetService": profile["internet"][i % len(profile["internet"])],
                    "Contract": profile["contract"][i % len(profile["contract"])],
                },
            })
    return anomalies
