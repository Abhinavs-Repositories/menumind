"""Aggregate per-query results into summary metrics + render reports."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Optional

from evals.metrics import safe_mean


def _pct(x: float) -> str:
    return f"{100 * x:5.1f}%"


def _agg_block(results: list[dict], ks: list[int]) -> dict:
    """Aggregate retrieval + answer metrics over a list of per-query results.

    Retrieval metrics use only scored (non-absent) items; answer metrics use all
    items that were judged (a correct refusal on an absent item still counts)."""
    scored = [r for r in results if not r["absent"]]
    block: dict = {"n": len(results), "n_scored": len(scored), "n_absent": len(results) - len(scored)}

    if scored:
        for k in ks:
            block[f"pre_hit@{k}"] = safe_mean([r["pre"][f"hit@{k}"] for r in scored])
        block["pre_mrr"] = safe_mean([r["pre"]["mrr"] for r in scored])
        block["pre_ndcg@10"] = safe_mean([r["pre"]["ndcg@10"] for r in scored])
        for k in [k for k in ks if k <= 5]:
            block[f"post_hit@{k}"] = safe_mean([r["post"][f"hit@{k}"] for r in scored])
        block["post_mrr"] = safe_mean([r["post"]["mrr"] for r in scored])
        block["post_ndcg@5"] = safe_mean([r["post"]["ndcg@5"] for r in scored])
        block["context_recall"] = safe_mean([1.0 if r["context_recall"] else 0.0 for r in scored])
        # rerank lift on the headline Hit@5 / MRR
        block["rerank_lift_hit@5"] = round(block["post_hit@5"] - block.get("pre_hit@5", 0.0), 4)
        block["rerank_lift_mrr"] = round(block["post_mrr"] - block["pre_mrr"], 4)

    # latency over all items that actually retrieved
    totals = [r["latency"]["total_s"] for r in results if r["latency"]["total_s"] is not None]
    if totals:
        s = sorted(totals)
        block["latency_mean_s"] = round(mean(s), 3)
        block["latency_p50_s"] = round(s[len(s) // 2], 3)
        block["latency_p95_s"] = round(s[min(len(s) - 1, int(0.95 * len(s)))], 3)

    judged = [r for r in results if r.get("judge")]
    if judged:
        block["judge_faithfulness"] = safe_mean([r["judge"]["faithfulness"] for r in judged])
        block["judge_relevance"] = safe_mean([r["judge"]["answer_relevance"] for r in judged])
        corr = [r["judge"]["correctness"] for r in judged if r["judge"]["correctness"] is not None]
        block["judge_correctness"] = safe_mean(corr) if corr else None
        absent_judged = [r for r in judged if r["absent"]]
        if absent_judged:
            # a faithful answer on an absent item == a correct decline
            block["absent_decline_faithfulness"] = safe_mean(
                [r["judge"]["faithfulness"] for r in absent_judged]
            )
    return block


def aggregate(results: list[dict], ks: list[int]) -> dict:
    overall = _agg_block(results, ks)

    by_set: dict[str, dict] = {}
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        groups[r["set_name"]].append(r)
    for name, rs in sorted(groups.items()):
        by_set[name] = _agg_block(rs, ks)

    by_rest: dict[str, dict] = {}
    rgroups: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        rgroups[r["restaurant"] or "(none)"].append(r)
    for name, rs in sorted(rgroups.items()):
        by_rest[name] = _agg_block(rs, ks)

    by_cat: dict[str, dict] = {}
    cgroups: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        cgroups[r["category"]].append(r)
    for name, rs in sorted(cgroups.items()):
        by_cat[name] = _agg_block(rs, ks)

    return {"overall": overall, "by_set": by_set, "by_restaurant": by_rest, "by_category": by_cat}


# ---------------------------------------------------------------- console ----

def _headline(b: dict) -> list[str]:
    lines = []
    if "post_hit@5" in b:
        lines.append(
            f"  Retrieval (post-rerank): Hit@1 {_pct(b['post_hit@1'])} | "
            f"Hit@3 {_pct(b['post_hit@3'])} | Hit@5 {_pct(b['post_hit@5'])} | "
            f"MRR {b['post_mrr']:.3f} | nDCG@5 {b['post_ndcg@5']:.3f}"
        )
        lines.append(
            f"  Retrieval (pre-rerank) : Hit@5 {_pct(b.get('pre_hit@5', 0))} | "
            f"Hit@10 {_pct(b.get('pre_hit@10', 0))} | MRR {b['pre_mrr']:.3f} | "
            f"nDCG@10 {b['pre_ndcg@10']:.3f}"
        )
        lines.append(
            f"  Rerank lift            : Hit@5 {b['rerank_lift_hit@5']:+.3f} | "
            f"MRR {b['rerank_lift_mrr']:+.3f}"
        )
        lines.append(f"  Context recall         : {_pct(b['context_recall'])} "
                     "(answer facts present in the LLM context)")
    if "latency_mean_s" in b:
        lines.append(
            f"  Latency (retrieve+rerank+gen): mean {b['latency_mean_s']}s | "
            f"p50 {b['latency_p50_s']}s | p95 {b['latency_p95_s']}s"
        )
    if "judge_faithfulness" in b:
        corr = b.get("judge_correctness")
        corr_s = f"{corr:.2f}/5" if corr is not None else "n/a"
        lines.append(
            f"  Answer judge (1-5)     : faithfulness {b['judge_faithfulness']:.2f} | "
            f"relevance {b['judge_relevance']:.2f} | correctness {corr_s}"
        )
        if "absent_decline_faithfulness" in b:
            lines.append(
                f"  Absent-question decline: {b['absent_decline_faithfulness']:.2f}/5 "
                "(higher = correctly says 'not on the menu')"
            )
    return lines


def _mini(b: dict) -> str:
    if "post_hit@5" not in b:
        parts = []
        if "judge_faithfulness" in b:
            parts.append(f"faith {b['judge_faithfulness']:.1f}")
        return f"n={b['n']} (absent)  " + " ".join(parts)
    s = (
        f"n={b['n_scored']:<3} Hit@5 {_pct(b['post_hit@5'])} MRR {b['post_mrr']:.2f} "
        f"ctx {_pct(b['context_recall'])}"
    )
    if "judge_faithfulness" in b:
        s += f"  faith {b['judge_faithfulness']:.1f} rel {b['judge_relevance']:.1f}"
        if b.get("judge_correctness") is not None:
            s += f" corr {b['judge_correctness']:.1f}"
    return s


def format_console(summary: dict) -> str:
    out: list[str] = []
    out.append("=" * 72)
    out.append("MENUMIND RETRIEVAL EVAL")
    out.append("=" * 72)
    o = summary["overall"]
    out.append(f"\nOVERALL  (n={o['n']}, scored={o['n_scored']}, absent={o['n_absent']})")
    out.extend(_headline(o))

    out.append("\nBY GOLD SET")
    for name, b in summary["by_set"].items():
        out.append(f"  {name:<10} {_mini(b)}")

    out.append("\nBY RESTAURANT")
    for name, b in summary["by_restaurant"].items():
        out.append(f"  {name:<22} {_mini(b)}")

    out.append("\nBY CATEGORY")
    for name, b in summary["by_category"].items():
        out.append(f"  {name:<14} {_mini(b)}")

    out.append("\n" + "=" * 72)
    return "\n".join(out)


# ----------------------------------------------------------------- files ----

def write_outputs(results: list[dict], summary: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "results.jsonl").open("w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (out_dir / "report.md").write_text(_markdown(summary), encoding="utf-8")


def _md_row(name: str, b: dict) -> str:
    if "post_hit@5" not in b:
        faith = f"{b.get('judge_faithfulness', float('nan')):.2f}" if "judge_faithfulness" in b else "-"
        return f"| {name} | {b['n']} | (absent) | - | - | - | {faith} | - | - |"
    corr = b.get("judge_correctness")
    faith = f"{b['judge_faithfulness']:.2f}" if "judge_faithfulness" in b else "-"
    rel = f"{b['judge_relevance']:.2f}" if "judge_relevance" in b else "-"
    corr_s = f"{corr:.2f}" if corr is not None else "-"
    return (
        f"| {name} | {b['n_scored']} | {_pct(b['post_hit@5']).strip()} | "
        f"{b['post_mrr']:.3f} | {b['post_ndcg@5']:.3f} | {_pct(b['context_recall']).strip()} | "
        f"{faith} | {rel} | {corr_s} |"
    )


def _markdown(summary: dict) -> str:
    o = summary["overall"]
    lines = ["# MenuMind retrieval eval", ""]
    lines.append(f"- queries: **{o['n']}** (scored {o['n_scored']}, absent {o['n_absent']})")
    for line in _headline(o):
        lines.append(f"- {line.strip()}")
    header = (
        "\n| group | n | Hit@5 | MRR | nDCG@5 | ctx-recall | faith | rel | corr |\n"
        "|---|---|---|---|---|---|---|---|---|"
    )
    lines.append("\n## By gold set" + header)
    for name, b in summary["by_set"].items():
        lines.append(_md_row(name, b))
    lines.append("\n## By restaurant" + header)
    for name, b in summary["by_restaurant"].items():
        lines.append(_md_row(name, b))
    lines.append("\n## By category" + header)
    for name, b in summary["by_category"].items():
        lines.append(_md_row(name, b))
    return "\n".join(lines) + "\n"
