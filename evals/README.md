# MenuMind evals

An evaluation suite for the RAG **retrieval** (and the answer quality built on top
of it). It runs the *live* pipeline — Gemini embeddings → Qdrant
(`mocha_menu_embeddings`) → embedding rerank → Groq generation → LLM judge — so
the numbers reflect what the app actually serves.

## What it measures

**Retrieval** (the focus), per query, both *pre-rerank* (Qdrant top-10) and
*post-rerank* (the 5 chunks the LLM actually sees):

| metric | meaning |
|---|---|
| **Hit@k** | did an answer-bearing chunk land in the top-k? |
| **MRR** | how high was the first relevant chunk (1/rank)? |
| **nDCG@k** | ranking quality (binary relevance) |
| **context-recall** | did the answer fact survive rerank + truncation into the LLM context? |
| **rerank lift** | Hit@5 / MRR gained (or lost) by the rerank step |
| **latency** | retrieve + rerank + generate, mean / p50 / p95 |

**Answer quality** (LLM-as-judge, Gemini, 1–5): `faithfulness` (grounded, no
hallucination), `answer_relevance`, `correctness` (vs the gold answer). `absent`
questions check the model correctly says *"not on the menu"* instead of inventing.

### How "relevant" is decided
A retrieved chunk is relevant to a question when it **carries the answer facts**
(normalized substring match on `expected_facts`) or, for synthetic items, when its
Qdrant point id matches the chunk the question was generated from. This is robust
to re-ingestion / chunk-id drift. See [matching.py](matching.py).

## Gold sets
- **curated** — [gold/curated.yaml](gold/curated.yaml): ~33 hand-written questions
  whose facts were verified against the parsed menus. Trustworthy smoke set.
- **synthetic** — `gold/synthetic.json`: generated from live chunks (each question
  tagged with its source chunk). Scales coverage to all menus. Not committed by
  default — regenerate it.

## Usage (run from the repo root, with the venv active)

```bash
# 1. (once / when menus change) build the synthetic gold set from Qdrant
python -m evals.generate_synthetic --per-restaurant 5

# 2. run the full suite (retrieval + generation + judge)
python -m evals.run_eval

# faster / cheaper variants
python -m evals.run_eval --set curated          # curated only
python -m evals.run_eval --no-judge             # retrieval + generation, no judge
python -m evals.run_eval --no-generate          # retrieval metrics only (no Groq/Gemini-judge)
python -m evals.run_eval --restaurant Taj --limit 10
```

Each run prints a summary and writes `evals/results/<timestamp>/`:
`report.md` (tables), `summary.json` (aggregates), `results.jsonl` (per-query detail
for debugging misses — includes the top retrieved chunk and the judge's reasoning).

## Cost & notes
- Uses the same free-tier keys from `.env` (Gemini, Qdrant, Groq).
- `--no-generate` is the cheapest pass: only the retrieval embeddings hit an API.
- The judge defaults to **Groq** (`openai/gpt-oss-120b`), deliberately a *different
  family* than the llama generator so a model isn't grading itself. Gemini's free
  tier caps `generate_content` at ~20/day (shared with menu parsing), too small for
  a full judged run — use `--judge-backend gemini` only for tiny spot checks.
- Switch judge/generator models with `--judge-backend {groq,gemini} --judge-model X`
  (run_eval) and `--backend/--model` (generate_synthetic).
- Tune knobs live in `config.py` (`rag_top_k`, `rag_top_k_rerank`, `rag_min_score`);
  re-run to see the effect on Hit@k / context-recall.
