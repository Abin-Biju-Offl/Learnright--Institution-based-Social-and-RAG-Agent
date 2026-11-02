"""
How good is our search? Measure it instead of guessing.

    python -m app.evaluate

A RAG system can only answer well if the search step finds the right pages,
so this script tests exactly that (it's quick: no LLM involved). Each question
in eval/questions.json says which chapter really answers it:

  * hit rate  how often that chapter is among the top results (higher = better)
  * MRR       how high it ranks on average; 1.0 means always first

Questions with "chapter": null are off-topic on purpose. Their best match
should score BELOW min_score, so the app says "not found" instead of guessing.
The summary shows whether min_score separates the two groups.

Re-run it after changing the chunk size, the embedding model or the PDFs to
see whether things got better or worse.
"""

import json

from app.config import ROOT, settings
from app.ingest import load_index, read_index_info
from app.rag import RAG


def main() -> None:
    rag = RAG(load_index(), info=read_index_info())
    questions = json.loads((ROOT / "eval" / "questions.json").read_text(encoding="utf-8"))

    ranks = []      # where the right chapter ranked, per on-topic question (None = not found)
    on_topic = []   # best score of questions the textbook DOES answer
    off_topic = []  # best score of questions it doesn't

    print(f"{'result':8} {'score':>5}  question")
    for q in questions:
        hits = rag.retrieve(q["question"], q["grade"], q["subject"])
        best = hits[0].score if hits else 0.0
        chapters = [hit.node.metadata["chapter"] for hit in hits]

        if q["chapter"] is None:
            off_topic.append(best)
            result = "ok" if best < settings.min_score else "LEAKED"
        else:
            on_topic.append(best)
            rank = chapters.index(q["chapter"]) + 1 if q["chapter"] in chapters else None
            ranks.append(rank)
            result = "MISSED" if rank is None else ("too low" if best < settings.min_score else f"rank {rank}")
        print(f"{result:8} {best:5.2f}  [{q['subject']}] {q['question']}")

    print()
    print(f"Hit rate (right chapter in top {settings.top_k}): {sum(r is not None for r in ranks) / len(ranks):.0%}")
    print(f"MRR (1.0 = always ranked first):         {sum(1 / r for r in ranks if r) / len(ranks):.2f}")
    print(f"Best scores, on-topic questions:  {min(on_topic):.2f} to {max(on_topic):.2f}")
    if off_topic:
        print(f"Best scores, off-topic questions: {min(off_topic):.2f} to {max(off_topic):.2f}")
        print(f"min_score is {settings.min_score}. ", end="")
        if max(off_topic) < settings.min_score <= min(on_topic):
            print("It separates the two groups perfectly.")
        else:
            print(f"A value between {max(off_topic):.2f} and {min(on_topic):.2f} would separate them, if one exists.")


if __name__ == "__main__":
    main()
