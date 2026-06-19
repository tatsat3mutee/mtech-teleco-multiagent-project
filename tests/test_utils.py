"""Tests for src.utils.*"""
import time
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.utils.rate_limit import TokenBucket, get_limiter
from src.utils.test_data import anomalies_from_ground_truth


class TestTokenBucket:
    def test_full_bucket_allows_immediate_first_acquire(self):
        b = TokenBucket(rate_per_minute=60, capacity=3)
        waited = b.acquire()
        assert waited == 0.0

    def test_depleted_bucket_waits_at_least_expected_interval(self):
        # 120 rpm = 2 rps → interval ~0.5s
        b = TokenBucket(rate_per_minute=120, capacity=1)
        b.acquire()  # deplete
        start = time.monotonic()
        b.acquire()
        elapsed = time.monotonic() - start
        assert elapsed >= 0.3  # generous lower bound for CI jitter

    def test_singleton_shared(self):
        a = get_limiter()
        b = get_limiter()
        assert a is b


class TestGTDerivedAnomalies:
    def test_default_shape(self):
        xs = anomalies_from_ground_truth(limit_per_type=3)
        assert len(xs) == 15

    def test_has_ground_truth_id(self):
        xs = anomalies_from_ground_truth(limit_per_type=2)
        assert all("ground_truth_id" in a for a in xs)

    def test_deterministic_under_seed(self):
        xs = anomalies_from_ground_truth(limit_per_type=3, seed=123)
        ys = anomalies_from_ground_truth(limit_per_type=3, seed=123)
        assert xs == ys

    def test_types_present(self):
        xs = anomalies_from_ground_truth(limit_per_type=3)
        types = {a["anomaly_type"] for a in xs}
        assert len(types) == 5

    def test_ground_truth_id_is_unique_per_anomaly(self):
        xs = anomalies_from_ground_truth(limit_per_type=12)
        gt_ids = [a["ground_truth_id"] for a in xs]
        assert len(gt_ids) == len(set(gt_ids))


class TestCacheKeyDeterministic:
    def test_same_input_same_key(self):
        from src.utils.cache import _cache_key
        anomaly = {"account_id": "ACC001", "anomaly_type": "zero_billing", "confidence": 0.9}
        assert _cache_key(anomaly) == _cache_key(anomaly)

    def test_key_order_independent(self):
        from src.utils.cache import _cache_key
        a = {"account_id": "ACC001", "anomaly_type": "zero_billing"}
        b = {"anomaly_type": "zero_billing", "account_id": "ACC001"}
        assert _cache_key(a) == _cache_key(b)

    def test_different_input_different_key(self):
        from src.utils.cache import _cache_key
        a = {"account_id": "ACC001", "anomaly_type": "zero_billing"}
        b = {"account_id": "ACC002", "anomaly_type": "zero_billing"}
        assert _cache_key(a) != _cache_key(b)

    def test_key_has_rca_prefix(self):
        from src.utils.cache import _cache_key
        key = _cache_key({"x": 1})
        assert key.startswith("rca:")


class TestInferenceLogRoundTrip:
    def test_log_and_fetch(self, tmp_path):
        """log_inference then fetch_recent returns the written row."""
        import src.utils.inference_log as ilog
        orig_path = ilog._DB_PATH
        ilog._DB_PATH = tmp_path / "test_inferences.db"
        ilog._DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            ilog.log_inference(
                anomaly_id="TEST-001",
                anomaly_type="zero_billing",
                severity="HIGH",
                root_cause="Test root cause",
                confidence=0.92,
                latency_ms=250.0,
                source="test",
                provider="groq",
                model="test-model",
            )
            rows = ilog.fetch_recent(limit=5)
            assert len(rows) >= 1
            row = rows[0]
            assert row["anomaly_id"] == "TEST-001"
            assert row["anomaly_type"] == "zero_billing"
            assert row["confidence"] == pytest.approx(0.92, abs=1e-6)
        finally:
            ilog._DB_PATH = orig_path


class TestDemoLoaderEmptyFile:
    def test_returns_empty_list_when_file_missing(self):
        """load_demo_results() returns [] gracefully when the JSON file does not exist."""
        import src.demo.demo_loader as dl
        orig_path = dl._DEMO_RESULTS_PATH
        dl._DEMO_RESULTS_PATH = Path("/nonexistent/path/sample_rca_results.json")
        try:
            result = dl.load_demo_results()
            assert result == []
        finally:
            dl._DEMO_RESULTS_PATH = orig_path
