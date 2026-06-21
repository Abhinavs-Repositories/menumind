"""MenuMind retrieval + answer-quality evaluation suite.

Measures where the RAG pipeline stands on a gold question set:

    - Retrieval metrics : Hit@k, MRR, nDCG@k, context-recall, rerank lift, latency
    - Answer metrics    : LLM-as-judge faithfulness / relevance / correctness

Entry points (run from the repo root):

    python -m evals.generate_synthetic     # build evals/gold/synthetic.json
    python -m evals.run_eval               # run the suite, print + save a report
"""
