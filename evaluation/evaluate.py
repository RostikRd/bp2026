#!/usr/bin/env python3
"""
RAG Agent Evaluation Pipeline

Evaluates the agent across 5 metrics using LLM-as-a-Judge (Claude Haiku):
  1. Faithfulness      – Is the answer grounded in source documents?
  2. Answer Relevance   – Does the answer address the question?
  3. Context Relevance   – Are the retrieved documents relevant?
  4. Correctness        – Is the answer factually correct vs reference?
  5. Completeness       – Does the answer cover all expected key points?

Usage:
    python evaluation/evaluate.py                  # run full evaluation
    python evaluation/evaluate.py --ids 4 5 6      # run only selected question IDs
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.rag.ask_cli import (
    get_vectorstore,
    load_api_keys,
    resolve_url,
    compact,
    level_ok,
    ask,
    MAX_L2_DISTANCE,
    TOP_DOCS_MAX,
    FAISS_MIN_CHUNKS,
    FAISS_MAX_BEST_L2,
)

load_api_keys()

JUDGE_MODEL_CANDIDATES = [
    os.environ.get("ANTHROPIC_MODEL", ""),
    "claude-3-5-sonnet-20241022",
    "claude-3-5-sonnet",
    "claude-3-5-haiku-20241022",
    "claude-3-5-haiku",
    "claude-sonnet-4-20250514",
    "claude-sonnet-4",
]
JUDGE_MODEL_CANDIDATES = [m for m in JUDGE_MODEL_CANDIDATES if m]

DELAY_BETWEEN_JUDGE_CALLS = 0.5
DELAY_BETWEEN_QUESTIONS = 1.5


# ---------------------------------------------------------------------------
# Retrieval helper – mirrors the retrieval logic from ask() but returns
# structured data instead of building a prompt string.
# ---------------------------------------------------------------------------

def get_retrieval_results(query: str) -> list[dict]:
    vs = get_vectorstore()
    docs_with_scores = vs.similarity_search_with_score(query, k=25)

    doc_to_score: dict[str, tuple[float, object]] = {}
    for doc, score in docs_with_scores:
        doc_id = doc.metadata.get("source_file", "") + str(doc.page_content[:100])
        if doc_id not in doc_to_score or score < doc_to_score[doc_id][0]:
            doc_to_score[doc_id] = (score, doc)

    unique_scored = sorted(doc_to_score.values(), key=lambda x: x[0])
    filtered = [
        (s, d) for s, d in unique_scored
        if level_ok(d.metadata) and s <= MAX_L2_DISTANCE
    ]
    if not filtered:
        filtered = [(s, d) for s, d in unique_scored if level_ok(d.metadata)]

    results = []
    for score, doc in filtered[:TOP_DOCS_MAX]:
        results.append({
            "content": compact(doc.page_content)[:1500],
            "url": resolve_url(doc.metadata),
            "title": doc.metadata.get("title", ""),
            "l2_score": round(float(score), 4),
        })
    return results


# ---------------------------------------------------------------------------
# LLM-as-a-Judge – sends an evaluation prompt to Claude Haiku and parses
# the JSON response {"score": 1-5, "explanation": "..."}.
# ---------------------------------------------------------------------------

def _call_judge(prompt: str, api_key: str) -> dict:
    import anthropic

    full_prompt = (
        f"{prompt}\n\n"
        "Respond ONLY with valid JSON in this exact format, nothing else:\n"
        '{"score": <integer 1-5>, "explanation": "<1-2 sentences in Slovak>"}'
    )
    client = anthropic.Anthropic(api_key=api_key, timeout=60.0)
    last_error = None
    for model in JUDGE_MODEL_CANDIDATES:
        try:
            resp = client.messages.create(
                model=model,
                max_tokens=300,
                temperature=0,
                messages=[{"role": "user", "content": full_prompt}],
            )
            text = resp.content[0].text.strip()
            match = re.search(r"\{[^}]+\}", text)
            if match:
                parsed = json.loads(match.group())
                if "score" in parsed:
                    return parsed
            return {"score": 0, "explanation": f"Failed to parse judge response: {text[:200]}"}
        except Exception as e:
            last_error = e
            err_str = str(e).lower()
            if "404" in err_str or "not_found" in err_str:
                continue
            return {"score": 0, "explanation": f"Judge error: {e}"}
    return {"score": 0, "explanation": f"All judge models unavailable. Last error: {last_error}"}


# ---------------------------------------------------------------------------
# Individual metric evaluators
# ---------------------------------------------------------------------------

def eval_faithfulness(question: str, contexts: list[dict], answer: str, api_key: str) -> dict:
    ctx_text = "\n\n".join(
        f"[{i+1}] {c['title']}\n{c['content']}"
        for i, c in enumerate(contexts[:6])
    )
    prompt = f"""Evaluate FAITHFULNESS of the answer.

Scoring guide (1-5):
  5 = Every claim in the answer is directly supported by the provided context documents
  4 = Almost all claims are supported; minor unsupported details only
  3 = Most claims are supported but some significant claims lack support
  2 = Many claims are not supported by the context
  1 = The answer contains mostly fabricated information

Question: {question}

Retrieved context documents:
{ctx_text}

Agent answer:
{answer[:8000]}"""
    return _call_judge(prompt, api_key)


def eval_relevance(question: str, answer: str, api_key: str) -> dict:
    prompt = f"""Evaluate ANSWER RELEVANCE.

Scoring guide (1-5):
  5 = The answer directly and fully addresses the question
  4 = The answer mostly addresses the question with minor tangents
  3 = The answer partially addresses the question
  2 = The answer barely addresses the question
  1 = The answer is completely off-topic or irrelevant

Question: {question}

Agent answer:
{answer[:8000]}"""
    return _call_judge(prompt, api_key)


def eval_context_relevance(question: str, contexts: list[dict], api_key: str) -> dict:
    ctx_text = "\n\n".join(
        f"[{i+1}] {c['title']} (L2 distance={c['l2_score']})\n{c['content'][:1000]}"
        for i, c in enumerate(contexts[:6])
    )
    prompt = f"""Evaluate CONTEXT RELEVANCE (retrieval quality).

Scoring guide (1-5):
  5 = All retrieved documents are highly relevant to the question
  4 = Most documents are relevant; 1-2 are tangential
  3 = About half the documents are relevant
  2 = Few documents are relevant to the question
  1 = Retrieved documents are mostly irrelevant

Question: {question}

Retrieved documents:
{ctx_text}"""
    return _call_judge(prompt, api_key)


def eval_correctness(question: str, answer: str, reference_points: list[str], api_key: str) -> dict:
    ref_text = "\n".join(f"- {p}" for p in reference_points)
    prompt = f"""Evaluate CORRECTNESS of the answer against reference key points.

Scoring guide (1-5):
  5 = All key points are correctly represented in the answer
  4 = Most key points are correct; minor inaccuracies
  3 = Some key points are correct but there are notable errors
  2 = Few key points are correctly addressed
  1 = The answer contradicts most reference points

Question: {question}

Reference key points (ground truth):
{ref_text}

Agent answer:
{answer[:8000]}"""
    return _call_judge(prompt, api_key)


def eval_completeness(question: str, answer: str, reference_points: list[str], api_key: str) -> dict:
    ref_text = "\n".join(f"- {p}" for p in reference_points)
    prompt = f"""Evaluate COMPLETENESS of the answer.

Scoring guide (1-5):
  5 = The answer covers ALL key points from the reference
  4 = The answer covers most key points (80%+)
  3 = The answer covers about half the key points
  2 = The answer covers few key points
  1 = The answer misses almost all key points

Question: {question}

Reference key points that should be covered:
{ref_text}

Agent answer:
{answer[:8000]}"""
    return _call_judge(prompt, api_key)


# ---------------------------------------------------------------------------
# Main evaluation loop
# ---------------------------------------------------------------------------

def run_evaluation(selected_ids: list[int] | None = None):
    dataset_path = PROJECT_ROOT / "evaluation" / "dataset.json"
    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set. Add it to api_keys.env.")
        sys.exit(1)

    questions = dataset["questions"]
    if selected_ids:
        questions = [q for q in questions if q["id"] in selected_ids]

    print(f"\n{'=' * 70}")
    print(f"  RAG Agent Evaluation  —  {len(questions)} questions")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 70}\n")

    all_results: list[dict] = []
    totals: dict[str, list[float]] = {
        "faithfulness": [],
        "relevance": [],
        "context_relevance": [],
        "correctness": [],
        "completeness": [],
    }
    off_topic_correct = 0
    off_topic_total = 0

    for idx, item in enumerate(questions):
        qid = item["id"]
        question = item["question"]
        category = item.get("category", "faiss")
        ref_points = item.get("reference_points", [])

        print(f"[{idx + 1}/{len(questions)}]  id={qid}  ({category})")
        print(f"  Q: {question[:90]}{'…' if len(question) > 90 else ''}")

        # --- Off-topic: check whether the agent correctly rejects it -------
        if category == "off_topic":
            off_topic_total += 1
            try:
                answer = ask(question)
            except Exception as e:
                answer = str(e)
            detected = (
                "nesúvisí" in answer.lower()
                or "odpovedám výhradne" in answer.lower()
            )
            if detected:
                off_topic_correct += 1
            score = 5.0 if detected else 1.0
            all_results.append({
                "id": qid,
                "question": question,
                "category": category,
                "off_topic_detected": detected,
                "scores": {"topic_filter": score},
            })
            symbol = "PASS" if detected else "FAIL"
            print(f"  → Off-topic detection: {symbol}")
            time.sleep(DELAY_BETWEEN_QUESTIONS)
            continue

        # --- On-topic: retrieve contexts + generate answer -----------------
        print("  → Retrieving FAISS contexts …")
        try:
            contexts = get_retrieval_results(question)
        except Exception as e:
            print(f"  ✗ Retrieval failed: {e}")
            contexts = []

        best_l2 = contexts[0]["l2_score"] if contexts else None
        faiss_has_answer = (
            len(contexts) >= FAISS_MIN_CHUNKS
            and best_l2 is not None
            and best_l2 <= FAISS_MAX_BEST_L2
        )

        print("  → Generating agent answer …")
        try:
            answer = ask(question)
        except Exception as e:
            answer = f"ERROR: {e}"
            print(f"  ✗ Agent failed: {e}")

        scores: dict[str, dict] = {}
        is_faiss = category == "faiss"

        # 1. Faithfulness (only for FAISS-based answers)
        if is_faiss and contexts:
            print("  → Judging faithfulness …")
            scores["faithfulness"] = eval_faithfulness(question, contexts, answer, api_key)
            totals["faithfulness"].append(scores["faithfulness"]["score"])
            time.sleep(DELAY_BETWEEN_JUDGE_CALLS)

        # 2. Answer Relevance (always)
        print("  → Judging relevance …")
        scores["relevance"] = eval_relevance(question, answer, api_key)
        totals["relevance"].append(scores["relevance"]["score"])
        time.sleep(DELAY_BETWEEN_JUDGE_CALLS)

        # 3. Context Relevance (only for FAISS-based answers)
        if is_faiss and contexts:
            print("  → Judging context relevance …")
            scores["context_relevance"] = eval_context_relevance(question, contexts, api_key)
            totals["context_relevance"].append(scores["context_relevance"]["score"])
            time.sleep(DELAY_BETWEEN_JUDGE_CALLS)

        # 4. Correctness (requires reference_points)
        if ref_points:
            print("  → Judging correctness …")
            scores["correctness"] = eval_correctness(question, answer, ref_points, api_key)
            totals["correctness"].append(scores["correctness"]["score"])
            time.sleep(DELAY_BETWEEN_JUDGE_CALLS)

        # 5. Completeness (requires reference_points)
        if ref_points:
            print("  → Judging completeness …")
            scores["completeness"] = eval_completeness(question, answer, ref_points, api_key)
            totals["completeness"].append(scores["completeness"]["score"])
            time.sleep(DELAY_BETWEEN_JUDGE_CALLS)

        score_strs = "  ".join(
            f"{k}={v['score']}" for k, v in scores.items()
        )
        print(f"  → {score_strs}")

        all_results.append({
            "id": qid,
            "question": question,
            "category": category,
            "answer_preview": answer[:3000] + ("…" if len(answer) > 3000 else ""),
            "contexts_count": len(contexts),
            "best_l2": best_l2,
            "faiss_has_answer": faiss_has_answer,
            "scores": {k: v["score"] for k, v in scores.items()},
            "explanations": {k: v.get("explanation", "") for k, v in scores.items()},
        })

        time.sleep(DELAY_BETWEEN_QUESTIONS)

    # -----------------------------------------------------------------------
    # Summary table
    # -----------------------------------------------------------------------
    print(f"\n{'=' * 70}")
    print("  EVALUATION RESULTS")
    print(f"{'=' * 70}\n")

    if off_topic_total > 0:
        print(f"  Off-topic detection:  {off_topic_correct}/{off_topic_total} correct\n")

    header = f"  {'Metric':<25} {'Avg':>7} {'Min':>6} {'Max':>6} {'N':>4}"
    print(header)
    print(f"  {'-' * 25} {'-' * 7} {'-' * 6} {'-' * 6} {'-' * 4}")

    for metric, scores_list in totals.items():
        if not scores_list:
            continue
        avg = sum(scores_list) / len(scores_list)
        lo = min(scores_list)
        hi = max(scores_list)
        n = len(scores_list)
        print(f"  {metric:<25} {avg:>7.2f} {lo:>6.1f} {hi:>6.1f} {n:>4}")

    # -----------------------------------------------------------------------
    # Per-question detail table
    # -----------------------------------------------------------------------
    print(f"\n{'=' * 70}")
    print("  PER-QUESTION SCORES")
    print(f"{'=' * 70}\n")

    metric_keys = ["faithfulness", "relevance", "context_relevance", "correctness", "completeness"]
    short_names = ["Faith", "Relev", "CtxRel", "Corr", "Compl"]
    header2 = f"  {'ID':>3} {'Cat':<10} " + " ".join(f"{s:>6}" for s in short_names)
    print(header2)
    print(f"  {'-' * 3} {'-' * 10} " + " ".join("-" * 6 for _ in short_names))

    for r in all_results:
        if r["category"] == "off_topic":
            tf = r["scores"].get("topic_filter", 0)
            vals = [f"{'PASS' if tf == 5 else 'FAIL':>6}"] + ["    —"] * (len(short_names) - 1)
            print(f"  {r['id']:>3} {'off_topic':<10} " + " ".join(vals))
        else:
            vals = []
            for mk in metric_keys:
                s = r["scores"].get(mk)
                vals.append(f"{s:>6}" if s is not None else "     —")
            print(f"  {r['id']:>3} {r['category']:<10} " + " ".join(vals))

    # -----------------------------------------------------------------------
    # Save detailed results to JSON
    # -----------------------------------------------------------------------
    results_dir = PROJECT_ROOT / "evaluation" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = results_dir / f"eval_{timestamp}.json"

    summary = {
        "timestamp": timestamp,
        "judge_model_candidates": JUDGE_MODEL_CANDIDATES,
        "num_questions": len(questions),
        "off_topic_accuracy": (
            f"{off_topic_correct}/{off_topic_total}"
            if off_topic_total > 0 else None
        ),
        "averages": {
            k: round(sum(v) / len(v), 2) if v else None
            for k, v in totals.items()
        },
        "detailed_results": all_results,
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n  Results saved to: {output_file.relative_to(PROJECT_ROOT)}")
    print(f"{'=' * 70}\n")
    return summary


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RAG Agent Evaluation")
    parser.add_argument(
        "--ids", nargs="*", type=int, default=None,
        help="Run evaluation only for these question IDs (e.g. --ids 4 5 6)",
    )
    args = parser.parse_args()
    run_evaluation(selected_ids=args.ids)
