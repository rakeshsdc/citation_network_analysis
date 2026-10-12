"""Free, key-less extractive summarisation (no LLM, no external service)."""
from __future__ import annotations

import re
from collections import Counter

STOP = set(
    """a an and are as at be been being but by can could did do does for from had has have
    having he her his how i if in into is it its may might more most no not of on or our
    out over she so some such than that the their them then there these they this those
    through to under up use used using was we were what when where which while who will
    with within would also between both each other only same very via based new results
    result study paper approach propose proposed present show shows shown however thus""".split()
)


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])", text)
    return [p.strip() for p in parts if len(p.strip()) > 25]


def tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z][a-z\-]{2,}", text.lower()) if t not in STOP]


def _score_sentences(sents: list[str], keywords: set[str]) -> list[float]:
    freq = Counter(t for s in sents for t in tokens(s))
    scores = []
    for i, s in enumerate(sents):
        toks = tokens(s)
        if not toks:
            scores.append(0.0)
            continue
        base = sum(freq[t] for t in toks) / (len(toks) ** 0.5)
        kw = sum(1 for t in toks if t in keywords)
        pos = 0.25 * base if i == 0 else (0.15 * base if i == len(sents) - 1 else 0.0)
        scores.append(base + 2.0 * kw + pos)
    return scores


def keyword_tokens(keywords) -> set[str]:
    out: set[str] = set()
    for k in keywords:
        out.update(tokens(k))
    return out


def summarize_text(text: str, n: int = 2, keywords=()) -> str:
    sents = split_sentences(text)
    if not sents:
        return "Abstract not available in OpenAlex for this work."
    if len(sents) <= n:
        return " ".join(sents)
    scores = _score_sentences(sents, keyword_tokens(keywords))
    top = sorted(sorted(range(len(sents)), key=lambda i: -scores[i])[:n])
    return " ".join(sents[i] for i in top)


def best_sentence(text: str, keywords=()) -> tuple[str, float]:
    sents = split_sentences(text)
    if not sents:
        return "", 0.0
    scores = _score_sentences(sents, keyword_tokens(keywords))
    i = max(range(len(sents)), key=lambda j: scores[j])
    norm = scores[i] / (max(scores) or 1.0)
    return sents[i], norm


def topic_overview(df, works_by_id: dict, keywords, n_papers: int = 12, n_sent: int = 6):
    """Key sentences from the most influential papers' abstracts."""
    picks = []
    top = df.head(n_papers)
    max_score = float(top["score"].max() or 1.0)
    for _, row in top.iterrows():
        w = works_by_id.get(row["id"])
        if not w:
            continue
        sent, q = best_sentence(w.get("abstract", ""), keywords)
        if sent:
            picks.append((q * (row["score"] / max_score), sent, row))
    picks.sort(key=lambda x: -x[0])
    return [
        {"sentence": s, "title": r["title"], "year": int(r["year"]), "authors": r["authors"]}
        for _, s, r in picks[:n_sent]
    ]


def narrative(result: dict, keywords) -> str:
    """Plain-language statistical overview of the analysed network."""
    df = result["papers"]
    if df.empty:
        return "No works were found for the supplied keywords."
    ys = df[df["year"] > 0]["year"]
    clusters = result["clusters"]
    top = df.iloc[0]
    parts = [
        f"The network for the keyword set ({', '.join(keywords)}) contains {len(df)} works "
        f"and {result['n_edges']} citation links between them, published between "
        f"{int(ys.min())} and {int(ys.max())}." if len(ys) else
        f"The network contains {len(df)} works and {result['n_edges']} citation links.",
        f"The highest-ranked work is \"{top['title']}\" ({int(top['year'])}), "
        f"cited {int(top['cites'])} times overall and {int(top['in_cites'])} times within this network.",
    ]
    if clusters:
        c = clusters[0]
        parts.append(
            f"The literature falls into {len(clusters)} thematic clusters; the largest "
            f"({c['size']} works) is centred on: {c['label']}."
        )
    return " ".join(parts)
