"""
Evaluation metrics for the Multi-Agent RAG RCA System.
Covers anomaly detection, RAG retrieval quality, and RCA output quality.
"""
import json
import numpy as np
import sys
from typing import List, Dict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import GROUND_TRUTH_DIR


def load_ground_truth() -> List[dict]:
    """Load ground truth RCA documents.

    Prefers the expanded 60-item file when present; falls back to the original
    15-item file for backward compatibility.
    """
    for name in ("ground_truth_rca_60.json", "ground_truth_rca.json"):
        gt_path = GROUND_TRUTH_DIR / name
        if gt_path.exists():
            with open(gt_path, "r", encoding="utf-8") as f:
                return json.load(f)
    raise FileNotFoundError(
        f"No ground truth file found under {GROUND_TRUTH_DIR}. "
        f"Expected ground_truth_rca_60.json or ground_truth_rca.json. "
        f"Run: python scripts/build_ground_truth.py to generate one."
    )


# ── Anomaly Detection Metrics ──

def detection_metrics(y_true: np.ndarray, y_pred: np.ndarray, y_scores: np.ndarray = None) -> dict:
    """Compute anomaly detection metrics."""
    from sklearn.metrics import (
        precision_score, recall_score, f1_score,
        roc_auc_score, average_precision_score,
        confusion_matrix, classification_report,
    )

    metrics = {
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1_score": f1_score(y_true, y_pred, zero_division=0),
        "confusion_matrix": confusion_matrix(y_true, y_pred).tolist(),
    }

    if y_scores is not None:
        try:
            metrics["roc_auc"] = roc_auc_score(y_true, y_scores)
            metrics["average_precision"] = average_precision_score(y_true, y_scores)
        except ValueError:
            metrics["roc_auc"] = 0.0
            metrics["average_precision"] = 0.0

    return metrics


# ── RAG Retrieval Metrics ──

def context_recall(retrieved_docs: List[str], relevant_docs: List[str]) -> float:
    """Compute context recall: proportion of relevant docs that were retrieved."""
    if not relevant_docs:
        return 0.0
    retrieved_set = set(retrieved_docs)
    relevant_set = set(relevant_docs)
    return len(retrieved_set & relevant_set) / len(relevant_set)


def context_precision(retrieved_docs: List[str], relevant_docs: List[str]) -> float:
    """Compute context precision: proportion of retrieved docs that are relevant."""
    if not retrieved_docs:
        return 0.0
    retrieved_set = set(retrieved_docs)
    relevant_set = set(relevant_docs)
    return len(retrieved_set & relevant_set) / len(retrieved_set)


def mrr_at_k(retrieved_docs: List[str], relevant_docs: List[str], k: int = 5) -> float:
    """Mean Reciprocal Rank at k."""
    relevant_set = set(relevant_docs)
    for i, doc in enumerate(retrieved_docs[:k]):
        if doc in relevant_set:
            return 1.0 / (i + 1)
    return 0.0


# ── RCA Quality Metrics ──

def compute_rouge_l(hypothesis: str, reference: str) -> dict:
    """Compute ROUGE-L score between hypothesis and reference."""
    try:
        from rouge_score import rouge_scorer
        scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)
        scores = scorer.score(reference, hypothesis)
        return {
            "precision": scores["rougeL"].precision,
            "recall": scores["rougeL"].recall,
            "fmeasure": scores["rougeL"].fmeasure,
        }
    except ImportError:
        # Fallback: simple token overlap
        hyp_tokens = set(hypothesis.lower().split())
        ref_tokens = set(reference.lower().split())
        if not ref_tokens:
            return {"precision": 0.0, "recall": 0.0, "fmeasure": 0.0}
        overlap = len(hyp_tokens & ref_tokens)
        precision = overlap / len(hyp_tokens) if hyp_tokens else 0.0
        recall = overlap / len(ref_tokens) if ref_tokens else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        return {"precision": precision, "recall": recall, "fmeasure": f1}


def compute_bert_score(hypotheses: List[str], references: List[str]) -> dict:
    """Compute BERTScore for a batch of hypothesis-reference pairs."""
    try:
        from bert_score import score as bert_score_fn
        P, R, F1 = bert_score_fn(hypotheses, references, lang="en", verbose=False)
        return {
            "precision": P.mean().item(),
            "recall": R.mean().item(),
            "f1": F1.mean().item(),
            "individual_f1": F1.tolist(),
        }
    except ImportError:
        # Fallback: use ROUGE-L as proxy
        f1_scores = []
        for hyp, ref in zip(hypotheses, references):
            rouge = compute_rouge_l(hyp, ref)
            f1_scores.append(rouge["fmeasure"])
        return {
            "precision": np.mean(f1_scores),
            "recall": np.mean(f1_scores),
            "f1": np.mean(f1_scores),
            "individual_f1": f1_scores,
            "note": "Using ROUGE-L as fallback (BERTScore not installed)"
        }


def anomaly_type_match(predicted_type: str, ground_truth_type: str) -> bool:
    """Check if predicted anomaly type matches ground truth."""
    return predicted_type.lower().strip() == ground_truth_type.lower().strip()


# ── Comprehensive Evaluation ──

def evaluate_pipeline_results(
    results: List[dict],
    ground_truths: List[dict] = None,
    run_judge: bool = False,
    judge_kwargs: dict = None,
) -> dict:
    """
    Evaluate a batch of pipeline results against ground truth.

    Args:
        results: List of pipeline outputs from run_pipeline()
        ground_truths: Optional list of ground truth RCA documents
        run_judge: If True, call LLM-as-Judge + faithfulness + answer-relevancy
            (requires GROQ_API_KEY or KIMI_API_KEY). Adds latency + cost.
        judge_kwargs: Passed through to llm_judge.judge_batch (e.g.,
            {"run_likert": True, "run_faithfulness": True, "run_relevancy": False}).
    """
    if ground_truths is None:
        try:
            ground_truths = load_ground_truth()
        except FileNotFoundError:
            ground_truths = []

    # Build ground truth lookups. Do NOT flatten by type (would drop 55/60);
    # keep a type -> list and an id -> record map.
    gt_by_type: Dict[str, List[dict]] = {}
    gt_by_id: Dict[str, dict] = {}
    for gt in ground_truths:
        gt_by_type.setdefault(gt["anomaly_type"], []).append(gt)
        if "anomaly_id" in gt:
            gt_by_id[gt["anomaly_id"]] = gt
    # Back-compat alias used by the judge (type -> any one record for that type).
    gt_lookup = {t: rows[0] for t, rows in gt_by_type.items()}

    metrics = {
        "total_processed": len(results),
        "successful": sum(1 for r in results if r.get("pipeline_status") == "completed"),
        "avg_latency_ms": np.mean([r.get("latency_ms", 0) for r in results]),
        "avg_retrieval_count": np.mean([r.get("retrieval_count", 0) for r in results]),
    }

    # Type matching
    type_matches = 0
    total_with_type = 0
    for r in results:
        rca = r.get("rca_report", {})
        pred_type = rca.get("anomaly_type", "")
        true_type = r.get("anomaly_data", {}).get("anomaly_type", "")
        if true_type:
            total_with_type += 1
            if anomaly_type_match(pred_type, true_type):
                type_matches += 1

    metrics["anomaly_type_accuracy"] = type_matches / max(total_with_type, 1)

    # RCA quality against ground truth. For each prediction:
    #   1. If the prediction carries a ground-truth id, compare against that row.
    #   2. Else compare against every GT row of the same anomaly_type and take
    #      the MAX score (charitable match). This is standard for open-ended
    #      multi-reference evaluation (cf. multi-reference BLEU/ROUGE).
    if ground_truths:
        hypotheses: List[str] = []
        references_per_hyp: List[List[str]] = []
        for r in results:
            rca = r.get("rca_report", {})
            anomaly_type = r.get("anomaly_data", {}).get("anomaly_type", "")
            gt_id = r.get("anomaly_data", {}).get("ground_truth_id") or rca.get("ground_truth_id")
            if gt_id and gt_id in gt_by_id:
                refs = [gt_by_id[gt_id].get("root_cause", "")]
            else:
                refs = [g.get("root_cause", "") for g in gt_by_type.get(anomaly_type, [])]
            if not refs:
                continue
            hypotheses.append(rca.get("root_cause", ""))
            references_per_hyp.append([ref for ref in refs if ref])

        if hypotheses:
            # ROUGE-L: per hypothesis, take max F over its reference set
            rouge_f_per_item = []
            for hyp, refs in zip(hypotheses, references_per_hyp):
                best = 0.0
                for ref in refs:
                    best = max(best, compute_rouge_l(hyp, ref)["fmeasure"])
                rouge_f_per_item.append(best)
            metrics["rouge_l_f1"] = float(np.mean(rouge_f_per_item))
            metrics["rouge_l_f1_per_item"] = rouge_f_per_item

            # BERTScore: compute per ref set and keep max per hypothesis
            bert_f_per_item: List[float] = []
            for hyp, refs in zip(hypotheses, references_per_hyp):
                if not refs:
                    bert_f_per_item.append(0.0)
                    continue
                bs = compute_bert_score([hyp] * len(refs), refs)
                bert_f_per_item.append(float(np.max(bs.get("individual_f1", [bs["f1"]]))))
            metrics["bert_score_f1"] = float(np.mean(bert_f_per_item)) if bert_f_per_item else 0.0
            metrics["bert_score_f1_per_item"] = bert_f_per_item

    # LLM-as-Judge + RAGAS-style metrics (opt-in; costs API calls)
    if run_judge and gt_lookup:
        try:
            from src.evaluation.llm_judge import judge_batch, aggregate_judge_scores
            judge_batch(results, gt_lookup, **(judge_kwargs or {}))
            metrics.update(aggregate_judge_scores(results))
        except Exception as e:
            print(f"[evaluate] judge pass failed: {e}")

    return metrics


def print_evaluation_report(metrics: dict):
    """Print a formatted evaluation report."""
    print("\n" + "=" * 60)
    print("  EVALUATION REPORT")
    print("=" * 60)

    print(f"\n  Pipeline Performance:")
    print(f"    Total Processed:      {metrics.get('total_processed', 0)}")
    print(f"    Successful:           {metrics.get('successful', 0)}")
    print(f"    Avg Latency:          {metrics.get('avg_latency_ms', 0):.0f}ms")
    print(f"    Avg Retrieval Count:  {metrics.get('avg_retrieval_count', 0):.1f}")

    print(f"\n  RCA Quality:")
    print(f"    Anomaly Type Accuracy: {metrics.get('anomaly_type_accuracy', 0):.2%}")

    if "rouge_l_f1" in metrics:
        print(f"    ROUGE-L F1:           {metrics.get('rouge_l_f1', 0):.4f}")
    if "bert_score_f1" in metrics:
        print(f"    BERTScore F1:         {metrics.get('bert_score_f1', 0):.4f}")
    if "faithfulness_mean" in metrics:
        print(f"\n  RAGAS-style (judge={metrics.get('judge_backend','?')}):")
        print(f"    Faithfulness:         {metrics.get('faithfulness_mean', 0):.4f}")
        print(f"    Answer Relevancy:     {metrics.get('answer_relevancy_mean', 0):.4f}")
    if "judge_correctness_mean" in metrics:
        print(f"\n  LLM-as-Judge (1-5 Likert):")
        print(f"    Correctness:          {metrics.get('judge_correctness_mean', 0):.2f}")
        print(f"    Groundedness:         {metrics.get('judge_groundedness_mean', 0):.2f}")
        print(f"    Actionability:        {metrics.get('judge_actionability_mean', 0):.2f}")
        print(f"    Completeness:         {metrics.get('judge_completeness_mean', 0):.2f}")

    print("\n" + "=" * 60)
