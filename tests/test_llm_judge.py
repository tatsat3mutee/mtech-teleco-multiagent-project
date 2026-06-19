"""Tests for src.evaluation.llm_judge utilities that do NOT require a live LLM."""
import pytest

from src.evaluation import llm_judge


class TestParseJson:
    def test_plain_json(self):
        out = llm_judge._parse_json('{"a": 1, "b": "x"}')
        assert out == {"a": 1, "b": "x"}

    def test_code_fenced_json(self):
        text = '```json\n{"correctness": 5, "groundedness": 4}\n```'
        out = llm_judge._parse_json(text)
        assert out == {"correctness": 5, "groundedness": 4}

    def test_malformed_returns_none(self):
        assert llm_judge._parse_json("not json at all") is None

    def test_none_input_safe(self):
        assert llm_judge._parse_json(None) is None


class TestBackendDetection:
    def test_backend_string_is_valid(self):
        # one of {openai_compat, groq, none} depending on env
        assert llm_judge._get_backend() in {"openai_compat", "groq", "none"}


class TestJudgeNoBackendGracefulNone(object):
    def test_likert_without_api_keys(self, monkeypatch):
        # Force backend to 'none' regardless of env
        monkeypatch.setattr(llm_judge, "_JUDGE_BACKEND", "none", raising=False)
        out = llm_judge.likert_judge(
            anomaly_type="zero_billing",
            candidate={"root_cause": "x"},
            reference="y",
            retrieved_context="z",
        )
        # All axes zero on failure; structure preserved
        assert set(out.keys()) >= {"correctness", "groundedness", "actionability", "completeness", "backend"}
        assert out["correctness"] == 0

    def test_faithfulness_without_backend_returns_zero(self, monkeypatch):
        monkeypatch.setattr(llm_judge, "_JUDGE_BACKEND", "none", raising=False)
        out = llm_judge.faithfulness("some rca claim here", "context claim here")
        assert out["faithfulness"] == 0.0
        assert out["n_claims"] == 0
