"""Pytest suite for the RAGML project.

Covers the fast, deterministic critical paths:
- evaluation metrics (ROUGE, type match, retrieval precision/recall, MRR)
- statistics utilities (bootstrap CI, paired bootstrap, compare_configs)
- ground-truth loader (60-item preferred, 15-item fallback, count invariants)
- GT-derived anomalies (shape, GT-id pairing, determinism under seed)
- anomaly injector ratios (deterministic, expected count per type)
- rate-limit token bucket semantics
- llm_judge _parse_json robustness + graceful no-backend path

Tests that touch Groq, OpenAI, ChromaDB, or GPU embeddings are skipped so the
suite stays offline-safe and < 15s. Integration smokes for those live in
`test_pipeline.py` / `test_llm.py`.
"""
