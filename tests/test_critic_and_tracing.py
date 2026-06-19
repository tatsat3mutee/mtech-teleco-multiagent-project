"""Tests for src.agents.critic and src.utils.tracing — all offline."""
import json
from pathlib import Path

import pytest

from src.agents.critic import critic_node, should_revise, _parse_json
from src.utils.tracing import Tracer, trace_span, summarize_trace


class TestCriticParseJson:
    def test_plain_json(self):
        assert _parse_json('{"verdict":"accept","confidence":0.9}')["verdict"] == "accept"

    def test_fenced_json(self):
        out = _parse_json('```json\n{"verdict":"revise"}\n```')
        assert out["verdict"] == "revise"

    def test_garbage(self):
        assert _parse_json("not json") is None
        assert _parse_json(None) is None


class TestCriticNodeFallback:
    def test_accept_when_no_hypothesis(self):
        state = {"anomaly_data": {"anomaly_type": "x"}}
        out = critic_node(state)
        assert out["critic_verdict"] == "accept"
        assert out["critic_attempts"] == 1

    def test_llm_unavailable_defaults_to_accept(self, monkeypatch):
        # Force call_llm to return None (simulates missing API key)
        from src.agents import critic as critic_mod
        monkeypatch.setattr(critic_mod, "call_llm", lambda *a, **kw: None)
        state = {
            "anomaly_data": {"anomaly_type": "zero_billing"},
            "hypothesis": "CDR job failed",
            "retrieved_docs": [{"source": "x.md", "text": "info"}],
            "rca_report": {"root_cause": "x"},
        }
        out = critic_node(state)
        assert out["critic_verdict"] == "accept"
        assert "critic-llm-unavailable" in out["critic_reasons"]

    def test_revise_branch_runs_at_most_once(self):
        state = {"critic_verdict": "revise", "critic_attempts": 1}
        assert should_revise(state) == "revise"
        state["critic_attempts"] = 2
        assert should_revise(state) == "proceed"


class TestCriticRevisionLoopE2E:
    """End-to-end test: critic requests revision, hypothesis agent re-runs, then critic accepts."""

    def test_revision_then_accept(self, monkeypatch):
        from src.agents import critic as critic_mod

        call_count = {"n": 0}

        def fake_call_llm(system, user, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                # First call: critic requests revision
                return json.dumps({
                    "verdict": "revise",
                    "confidence": 0.4,
                    "reasoning": "Hypothesis lacks root cause evidence",
                    "suggestions": ["Check CDR pipeline logs"],
                })
            else:
                # Second call: critic accepts
                return json.dumps({
                    "verdict": "accept",
                    "confidence": 0.9,
                    "reasoning": "Hypothesis aligns with retrieved evidence",
                    "suggestions": [],
                })

        monkeypatch.setattr(critic_mod, "call_llm", fake_call_llm)

        state = {
            "anomaly_data": {"anomaly_type": "zero_billing"},
            "hypothesis": "CDR job failed due to network timeout",
            "retrieved_docs": [{"source": "playbook.md", "text": "CDR failures often due to timeout"}],
            "rca_report": {"root_cause": "CDR ingestion timeout"},
            "critic_attempts": 0,
        }

        # First pass: critic says revise
        out1 = critic_node(state)
        assert out1["critic_verdict"] == "revise"
        assert out1["critic_attempts"] == 1
        assert should_revise(out1) == "revise"

        # Simulate hypothesis agent re-running (updates hypothesis)
        state.update(out1)
        state["hypothesis"] = "CDR pipeline timeout at ingestion layer"

        # Second pass: critic accepts
        out2 = critic_node(state)
        assert out2["critic_verdict"] == "accept"
        assert out2["critic_attempts"] == 2
        assert should_revise(out2) == "proceed"


class TestTracer:
    def test_disabled_no_file(self, tmp_path):
        Tracer.set_enabled(False)
        Tracer.log_event("llm_call", model="x")  # no-op
        assert Tracer.current_path() is None or not Tracer.current_path().exists()

    def test_span_writes_start_and_end(self, tmp_path):
        p = tmp_path / "t.jsonl"
        Tracer.set_enabled(True, path=p)
        try:
            with trace_span("retrieval", q="duplicate charge"):
                pass
            Tracer.log_event("llm_call", model="gpt-4o-mini", latency_ms=100)
        finally:
            Tracer.set_enabled(False)
        lines = p.read_text(encoding="utf-8").strip().splitlines()
        kinds = [json.loads(l)["kind"] for l in lines]
        assert "span_start" in kinds and "span_end" in kinds and "llm_call" in kinds

    def test_summarize(self, tmp_path):
        p = tmp_path / "t.jsonl"
        Tracer.set_enabled(True, path=p)
        try:
            with trace_span("a"):
                pass
            with trace_span("a"):
                pass
            with trace_span("b"):
                pass
        finally:
            Tracer.set_enabled(False)
        s = summarize_trace(p)
        assert s["spans"]["a"]["n"] == 2
        assert s["spans"]["b"]["n"] == 1
        assert s["event_counts"]["span_end"] == 3
