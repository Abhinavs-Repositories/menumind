"""LLM-as-judge for answer quality (Groq by default, decoupled from the generator).

Scores three axes on a 1-5 scale:
  - faithfulness     : is every claim grounded in the retrieved context (no hallucination)?
  - answer_relevance : does the answer actually address the question?
  - correctness      : does it match the gold expected_answer? (null when none provided)

For 'absent' questions (the fact isn't in the menu), the correct behaviour is to
decline / say it's not on the menu; the judge is told to reward that.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from evals.datatypes import GoldItem
from evals.llm import DEFAULT_GROQ_JUDGE, make_backend


class Judgement(BaseModel):
    faithfulness: int          # 1-5
    answer_relevance: int      # 1-5
    correctness: Optional[int] # 1-5 or null
    reasoning: str


JUDGE_SYSTEM = """You are a strict evaluator for a restaurant-menu Q&A assistant. \
You grade ONE answer against the retrieved context and (optionally) a gold answer. \
Use integer scores 1-5 (5 = best). Be critical; reserve 5 for genuinely flawless.

Definitions:
- faithfulness: Is every factual claim in the answer supported by the CONTEXT? \
Hallucinated dishes/prices/hours score low. If the context lacks the info and the \
answer correctly says it doesn't know / it's not on the menu, that is FAITHFUL (score 5).
- answer_relevance: Does the answer address the user's QUESTION (right dish, right \
field asked for)? An on-topic but evasive answer scores mid.
- correctness: Only if a GOLD answer is given. Does the answer agree with the gold \
answer's facts (price, item, hours)? A correct refusal when the gold says the item \
is absent counts as correct (5). If no gold answer is provided, return null.

Keep reasoning to one sentence."""


class Judge:
    def __init__(self, backend: str = "groq", model: str | None = None):
        self._backend = make_backend(backend, model, role="judge")
        self.name = self._backend.name

    def judge(self, item: GoldItem, answer: str, context: str) -> Judgement:
        gold = item.expected_answer or "(none provided - return null for correctness)"
        absent_note = (
            "\nNOTE: This item is marked ABSENT - the correct behaviour is to say the "
            "information is not on the menu. Reward a correct decline."
            if item.category == "absent"
            else ""
        )
        user = (
            f"QUESTION:\n{item.question}\n\n"
            f"RETRIEVED CONTEXT:\n{context or '(empty)'}\n\n"
            f"ASSISTANT ANSWER:\n{answer}\n\n"
            f"GOLD ANSWER:\n{gold}{absent_note}\n\n"
            "Grade the answer now."
        )
        return self._backend.complete(JUDGE_SYSTEM, user, Judgement, temperature=0.0)


__all__ = ["Judge", "Judgement", "DEFAULT_GROQ_JUDGE"]
