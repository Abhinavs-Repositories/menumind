"""Run the MenuMind retrieval + answer-quality eval.

Measures the live pipeline (Gemini embeddings -> Qdrant -> rerank -> Groq -> judge)
against the gold set and writes a timestamped report.

Usage (from repo root):
    python -m evals.run_eval                       # all gold, retrieval+gen+judge
    python -m evals.run_eval --set curated         # curated only
    python -m evals.run_eval --no-judge            # retrieval + generation only
    python -m evals.run_eval --no-generate         # retrieval metrics only (fast/cheap)
    python -m evals.run_eval --restaurant Taj --limit 10
"""

from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime
from pathlib import Path

from evals import report as report_mod
from evals.datatypes import GoldItem
from evals.datatypes import load_gold
from evals.matching import context_has_answer, relevance_flags
from evals.metrics import hit_at_k, ndcg_at_k, reciprocal_rank
from evals.retrieval import capture
from rag import MenuRAG

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("evals.run")

KS = [1, 3, 5, 10]
RESULTS_ROOT = Path(__file__).resolve().parent / "results"


def _first_rank(flags: list[bool]):
    for i, rel in enumerate(flags, start=1):
        if rel:
            return i
    return None


def _retrieval_metrics(item: GoldItem, cap) -> dict:
    pre_flags = relevance_flags(item, cap.retrieved)
    post_flags = relevance_flags(item, cap.reranked)

    pre = {f"hit@{k}": hit_at_k(pre_flags, k) for k in KS}
    pre.update(
        mrr=reciprocal_rank(pre_flags),
        **{"ndcg@10": ndcg_at_k(pre_flags, 10)},
        n_retrieved=len(cap.retrieved),
        first_rel_rank=_first_rank(pre_flags),
    )
    post = {f"hit@{k}": hit_at_k(post_flags, k) for k in KS if k <= 5}
    post.update(
        mrr=reciprocal_rank(post_flags),
        **{"ndcg@5": ndcg_at_k(post_flags, 5)},
        n_reranked=len(cap.reranked),
        first_rel_rank=_first_rank(post_flags),
    )
    return {"pre": pre, "post": post}


def evaluate(
    items: list[GoldItem],
    do_generate: bool,
    do_judge: bool,
    judge_backend: str = "groq",
    judge_model: str | None = None,
) -> list[dict]:
    rag = MenuRAG()
    judge = None
    if do_judge:
        from evals.judge import Judge

        judge = Judge(backend=judge_backend, model=judge_model)
        print(f"Judge: {judge.name}\n")

    results: list[dict] = []
    for n, item in enumerate(items, start=1):
        absent = item.category == "absent"
        cap = capture(rag, item)
        rm = _retrieval_metrics(item, cap)
        ctx_recall = (not absent) and context_has_answer(item, cap.context)

        gen_s = None
        answer = None
        judgement = None
        error = None
        if do_generate:
            t = time.time()
            try:
                answer, _ = rag._generate(item.question, cap.context)
                gen_s = round(time.time() - t, 3)
            except Exception as e:  # noqa: BLE001 - keep going so we still get a partial report
                error = f"generate: {e}"
                logger.warning("generate failed on %s: %s", item.id, e)
            if answer is not None and judge is not None:
                try:
                    j = judge.judge(item, answer, cap.context)
                    judgement = j.model_dump()
                except Exception as e:  # noqa: BLE001
                    error = f"judge: {e}"
                    logger.warning("judge failed on %s: %s", item.id, e)

        total_s = round(cap.retrieve_s + cap.rerank_s + (gen_s or 0.0), 3)
        top = cap.reranked[0] if cap.reranked else None
        results.append(
            {
                "id": item.id,
                "set_name": item.set_name,
                "restaurant": item.restaurant,
                "category": item.category,
                "question": item.question,
                "absent": absent,
                "expected_facts": item.expected_facts,
                "pre": rm["pre"],
                "post": rm["post"],
                "context_recall": bool(ctx_recall),
                "latency": {
                    "retrieve_s": cap.retrieve_s,
                    "rerank_s": cap.rerank_s,
                    "gen_s": gen_s,
                    "total_s": total_s,
                },
                "answer": answer,
                "judge": judgement,
                "error": error,
                "top_doc": (
                    {"score": round(top["score"], 4), "page": top.get("page_number"),
                     "preview": top["text"][:160]}
                    if top else None
                ),
            }
        )

        hit = "HIT " if rm["post"]["hit@5"] else "MISS"
        extra = ""
        if judgement:
            extra = f" | faith {judgement['faithfulness']} rel {judgement['answer_relevance']}"
        elif error:
            extra = f" | ERR {error[:40]}"
        print(f"[{n:>3}/{len(items)}] {hit} {item.set_name[:3]} {item.restaurant or '-':<18} "
              f"{item.question[:48]:<48}{extra}")

    return results


def main() -> None:
    ap = argparse.ArgumentParser(description="Run MenuMind retrieval + answer eval")
    ap.add_argument("--set", default="all", choices=["curated", "synthetic", "all"])
    ap.add_argument("--restaurant", help="limit to one restaurant")
    ap.add_argument("--limit", type=int, help="cap number of questions (smoke test)")
    ap.add_argument("--no-generate", action="store_true", help="skip Groq generation (retrieval only)")
    ap.add_argument("--no-judge", action="store_true", help="skip the LLM judge")
    ap.add_argument("--judge-backend", default="groq", choices=["groq", "gemini"],
                    help="judge LLM backend (default groq; gemini free tier is ~20/day)")
    ap.add_argument("--judge-model", help="override the judge model")
    ap.add_argument("--out", help="output dir (default: evals/results/<timestamp>)")
    args = ap.parse_args()

    items = load_gold(args.set)
    if args.restaurant:
        items = [it for it in items if it.restaurant == args.restaurant]
    if args.limit:
        items = items[: args.limit]

    if not items:
        print("No gold items loaded. Did you run `python -m evals.generate_synthetic`?")
        return
    if args.set in ("all", "synthetic") and not any(it.set_name == "synthetic" for it in items):
        print("(note: no synthetic gold found - run `python -m evals.generate_synthetic` to add it)\n")

    do_generate = not args.no_generate
    do_judge = do_generate and not args.no_judge
    if args.no_generate and not args.no_judge:
        print("(note: --no-generate implies no judge)\n")

    print(f"Evaluating {len(items)} questions "
          f"(generate={do_generate}, judge={do_judge}) ...\n")
    results = evaluate(items, do_generate, do_judge, args.judge_backend, args.judge_model)

    summary = report_mod.aggregate(results, KS)
    console = report_mod.format_console(summary)
    print("\n" + console)

    out_dir = Path(args.out) if args.out else RESULTS_ROOT / datetime.now().strftime("%Y%m%d_%H%M%S")
    report_mod.write_outputs(results, summary, out_dir)
    print(f"\nSaved: {out_dir / 'report.md'}")
    print(f"       {out_dir / 'summary.json'}")
    print(f"       {out_dir / 'results.jsonl'}")


if __name__ == "__main__":
    main()
