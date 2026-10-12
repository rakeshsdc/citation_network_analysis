"""OpenAlex data access for CiteScope.

Uses the free OpenAlex REST API (https://docs.openalex.org). No API key is
needed; supplying an e-mail address puts requests in the faster "polite pool".
"""
from __future__ import annotations

import time
from collections import Counter

import requests

BASE = "https://api.openalex.org/works"
SELECT = (
    "id,display_name,publication_year,cited_by_count,referenced_works,"
    "authorships,abstract_inverted_index,primary_location,doi,type"
)


def short_id(url: str) -> str:
    return url.rsplit("/", 1)[-1] if url else ""


def rebuild_abstract(inv: dict | None) -> str:
    """OpenAlex stores abstracts as an inverted index; rebuild plain text."""
    if not inv:
        return ""
    positions = []
    for word, idxs in inv.items():
        for i in idxs:
            positions.append((i, word))
    positions.sort()
    return " ".join(w for _, w in positions)


def parse_work(raw: dict, expanded: bool = False) -> dict:
    loc = raw.get("primary_location") or {}
    source = loc.get("source") or {}
    authors = []
    for a in raw.get("authorships") or []:
        name = (a.get("author") or {}).get("display_name")
        if name:
            authors.append(name)
    return {
        "id": short_id(raw.get("id", "")),
        "title": raw.get("display_name") or "(untitled)",
        "year": raw.get("publication_year") or 0,
        "cites": raw.get("cited_by_count") or 0,
        "refs": [short_id(r) for r in (raw.get("referenced_works") or [])],
        "authors": authors,
        "abstract": rebuild_abstract(raw.get("abstract_inverted_index")),
        "venue": source.get("display_name") or "",
        "doi": raw.get("doi") or "",
        "type": raw.get("type") or "",
        "expanded": expanded,
    }


def _get(params: dict, email: str, retries: int = 4) -> dict:
    params = dict(params)
    if email:
        params["mailto"] = email
    delay = 2.0
    for attempt in range(retries):
        try:
            r = requests.get(BASE, params=params, timeout=40)
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(delay)
                delay *= 2
                continue
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            if attempt == retries - 1:
                raise
            time.sleep(delay)
            delay *= 2
    raise RuntimeError("OpenAlex request failed after several retries")


def build_query(keywords: list[str], mode: str = "any") -> str:
    """Turn keyword list into an OpenAlex search string (phrases quoted)."""
    terms = [f'"{k}"' if " " in k else k for k in keywords if k.strip()]
    joiner = " OR " if mode == "any" else " AND "
    return joiner.join(terms)


def search_works(
    keywords: list[str],
    mode: str = "any",
    year_from: int | None = None,
    year_to: int | None = None,
    max_results: int = 300,
    sort: str = "relevance",
    email: str = "",
    progress=None,
) -> tuple[list[dict], int]:
    """Return (works, total_matches_in_openalex)."""
    filters = []
    if year_from:
        filters.append(f"from_publication_date:{year_from}-01-01")
    if year_to:
        filters.append(f"to_publication_date:{year_to}-12-31")
    params = {
        "search": build_query(keywords, mode),
        "per-page": min(200, max_results),
        "select": SELECT,
    }
    if filters:
        params["filter"] = ",".join(filters)
    if sort == "citations":
        params["sort"] = "cited_by_count:desc"

    works: list[dict] = []
    total = 0
    page = 1
    while len(works) < max_results:
        params["page"] = page
        data = _get(params, email)
        total = (data.get("meta") or {}).get("count", total)
        results = data.get("results") or []
        if not results:
            break
        works.extend(parse_work(r) for r in results)
        if progress:
            progress(f"Fetched {min(len(works), max_results)} of up to {max_results} works...")
        page += 1
        if len(results) < params["per-page"]:
            break
        time.sleep(0.15)
    return works[:max_results], total


def expand_references(
    works: list[dict], extra: int = 100, email: str = "", progress=None
) -> list[dict]:
    """One-hop expansion: add frequently cited references missing from the pool."""
    have = {w["id"] for w in works}
    counts: Counter = Counter()
    for w in works:
        for r in w["refs"]:
            if r and r not in have:
                counts[r] += 1
    # keep only references cited by at least 2 papers in the pool
    wanted = [rid for rid, c in counts.most_common(extra) if c >= 2]
    added: list[dict] = []
    for i in range(0, len(wanted), 50):
        batch = wanted[i : i + 50]
        params = {
            "filter": "openalex:" + "|".join(batch),
            "per-page": 50,
            "select": SELECT,
        }
        data = _get(params, email)
        added.extend(parse_work(r, expanded=True) for r in data.get("results") or [])
        if progress:
            progress(f"Expanded references: {len(added)} added...")
        time.sleep(0.15)
    return works + added


def fetch_all(
    keywords, mode, year_from, year_to, max_results, sort, expand, email, progress=None
) -> tuple[list[dict], dict]:
    works, total = search_works(
        keywords, mode, year_from, year_to, max_results, sort, email, progress
    )
    n_search = len(works)
    if expand and works:
        works = expand_references(works, extra=100, email=email, progress=progress)
    meta = {
        "query": build_query(keywords, mode),
        "total_matches": total,
        "retrieved_search": n_search,
        "retrieved_total": len(works),
        "expanded_added": len(works) - n_search,
    }
    return works, meta
