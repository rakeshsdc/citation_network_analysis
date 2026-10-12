"""Citation-network construction, node capping and ranking for CiteScope."""
from __future__ import annotations

import math
from collections import Counter, defaultdict

import networkx as nx
import pandas as pd

from summarize import STOP, tokens


# ----------------------------------------------------------------- node cap
def apply_node_cap(works: list[dict], cap: int) -> tuple[list[dict], dict]:
    """Keep at most `cap` works. Ranking before the cut uses how often a work is
    cited inside the pool (60%) and its global citation count (40%)."""
    n = len(works)
    info = {
        "applied": n > cap,
        "cap": cap,
        "candidates": n,
        "retained": min(n, cap),
        "dropped": max(0, n - cap),
    }
    if n <= cap:
        return works, info
    ids = {w["id"] for w in works}
    incoming: Counter = Counter()
    for w in works:
        for r in w["refs"]:
            if r in ids and r != w["id"]:
                incoming[r] += 1
    max_in = max(incoming.values(), default=1) or 1
    max_log = max(math.log1p(w["cites"]) for w in works) or 1.0

    def key(w):
        return 0.6 * incoming[w["id"]] / max_in + 0.4 * math.log1p(w["cites"]) / max_log

    kept = sorted(works, key=key, reverse=True)[:cap]
    return kept, info


# ------------------------------------------------------------------ helpers
def build_graph(works: list[dict]) -> nx.DiGraph:
    G = nx.DiGraph()
    ids = {w["id"] for w in works}
    G.add_nodes_from(ids)
    for w in works:
        for r in w["refs"]:
            if r in ids and r != w["id"]:
                G.add_edge(w["id"], r)  # edge: citing -> cited
    return G


def _minmax(d: dict) -> dict:
    if not d:
        return {}
    lo, hi = min(d.values()), max(d.values())
    if hi - lo < 1e-12:
        return {k: 0.0 for k in d}
    return {k: (v - lo) / (hi - lo) for k, v in d.items()}


def _author_str(authors: list[str]) -> str:
    if not authors:
        return "Unknown"
    if len(authors) <= 3:
        return ", ".join(authors)
    return ", ".join(authors[:3]) + " et al."


def _cluster_label(titles: list[str], k: int = 4) -> str:
    c: Counter = Counter()
    for t in titles:
        c.update(set(tokens(t)))
    words = [w for w, _ in c.most_common(k + 6) if w not in STOP][:k]
    return ", ".join(words) if words else "mixed topics"


# ------------------------------------------------------------------ analyse
def analyze(works: list[dict], node_cap: int = 300) -> dict:
    # de-duplicate by id
    seen, uniq = set(), []
    for w in works:
        if w["id"] and w["id"] not in seen:
            seen.add(w["id"])
            uniq.append(w)

    works, cap_info = apply_node_cap(uniq, node_cap)
    G = build_graph(works)
    byid = {w["id"]: w for w in works}
    n = G.number_of_nodes()
    if n == 0:
        return {"papers": pd.DataFrame(), "authors": pd.DataFrame(), "timeline": pd.DataFrame(),
                "clusters": [], "G": G, "works": byid, "cap_info": cap_info, "n_edges": 0}

    # centralities
    if G.number_of_edges():
        pr = nx.pagerank(G, alpha=0.85)
        k = 150 if n > 150 else None
        btw = nx.betweenness_centrality(G, k=k, seed=42)
    else:
        pr = {x: 1.0 / n for x in G}
        btw = {x: 0.0 for x in G}
    indeg = dict(G.in_degree())
    outdeg = dict(G.out_degree())

    # communities (Louvain on the undirected projection)
    U = G.to_undirected()
    comms = [c for c in nx.community.louvain_communities(U, seed=42) if len(c) > 1]
    comms.sort(key=len, reverse=True)
    cluster_of = {node: 0 for node in G}  # 0 = unconnected / singleton
    for i, c in enumerate(comms, start=1):
        for node in c:
            cluster_of[node] = i

    # composite importance score (0-100)
    mm_pr, mm_in, mm_btw = _minmax(pr), _minmax(indeg), _minmax(btw)
    mm_cites = _minmax({i: math.log1p(byid[i]["cites"]) for i in G})
    score = {
        i: 100 * (0.35 * mm_pr[i] + 0.25 * mm_in[i] + 0.25 * mm_cites[i] + 0.15 * mm_btw[i])
        for i in G
    }

    rows = []
    for i in G:
        w = byid[i]
        rows.append({
            "id": i, "title": w["title"], "year": w["year"],
            "authors": _author_str(w["authors"]), "cites": w["cites"],
            "in_cites": indeg[i], "out_refs": outdeg[i],
            "pagerank": pr[i], "betweenness": btw[i], "score": round(score[i], 2),
            "cluster": cluster_of[i], "venue": w["venue"],
            "doi": w["doi"], "expanded": w["expanded"],
        })
    df = pd.DataFrame(rows).sort_values("score", ascending=False).reset_index(drop=True)
    df.insert(0, "rank", df.index + 1)

    # roles
    valid_years = df[df["year"] > 0]["year"]
    med_year = valid_years.median() if len(valid_years) else 0
    max_year = valid_years.max() if len(valid_years) else 0
    q_in = df["in_cites"].quantile(0.75)
    q_out = df["out_refs"].quantile(0.90)
    q_btw = df["betweenness"].quantile(0.90)
    q_sc = df["score"].quantile(0.75)

    def roles(r):
        out = []
        if r["year"] and r["year"] <= med_year and r["in_cites"] >= q_in and r["in_cites"] > 0:
            out.append("Foundational")
        if r["out_refs"] >= max(q_out, 10):
            out.append("Review / hub")
        if r["betweenness"] >= q_btw and r["betweenness"] > 0:
            out.append("Bridge")
        if r["year"] and r["year"] >= max_year - 3 and r["score"] >= q_sc:
            out.append("Recent influential")
        return ", ".join(out) if out else "Supporting"

    df["role"] = df.apply(roles, axis=1)
    score_of = dict(zip(df["id"], df["score"]))

    # clusters
    clusters = []
    for cid in sorted(c for c in df["cluster"].unique() if c != 0):
        sub = df[df["cluster"] == cid]
        yrs = sub[sub["year"] > 0]["year"]
        clusters.append({
            "id": int(cid), "size": len(sub),
            "label": _cluster_label(list(sub["title"])),
            "top_paper": sub.iloc[0]["title"],
            "years": f"{int(yrs.min())}-{int(yrs.max())}" if len(yrs) else "n/a",
            "avg_score": round(float(sub["score"].mean()), 2),
        })
    clusters.sort(key=lambda c: -c["size"])

    # authors
    agg = defaultdict(lambda: {"papers": 0, "score": 0.0, "cites": 0, "years": [], "best": ("", -1)})
    for i in G:
        w = byid[i]
        for a in set(w["authors"]):
            d = agg[a]
            d["papers"] += 1
            d["score"] += score_of[i]
            d["cites"] += w["cites"]
            if w["year"]:
                d["years"].append(w["year"])
            if score_of[i] > d["best"][1]:
                d["best"] = (w["title"], score_of[i])
    arows = [{
        "author": a, "papers": d["papers"], "total_score": round(d["score"], 2),
        "total_cites": d["cites"],
        "active": f"{min(d['years'])}-{max(d['years'])}" if d["years"] else "n/a",
        "top_paper": d["best"][0],
    } for a, d in agg.items()]
    adf = pd.DataFrame(arows)
    if not adf.empty:
        adf = adf.sort_values(["total_score", "papers"], ascending=False).reset_index(drop=True)
        adf.insert(0, "rank", adf.index + 1)

    # timeline (top paper per year)
    tl = []
    for y, sub in df[df["year"] > 0].groupby("year"):
        best = sub.iloc[0]
        tl.append({"year": int(y), "papers": len(sub), "total_score": round(float(sub["score"].sum()), 2),
                   "top_paper": best["title"], "top_score": best["score"]})
    tdf = pd.DataFrame(tl).sort_values("year").reset_index(drop=True) if tl else pd.DataFrame()

    return {"papers": df, "authors": adf, "timeline": tdf, "clusters": clusters,
            "G": G, "works": byid, "cap_info": cap_info, "n_edges": G.number_of_edges()}


# --------------------------------------------------------- per-paper links
def connected_works(result: dict, work_id: str, top: int = 5) -> dict:
    G, df = result["G"], result["papers"]
    lookup = df.set_index("id")

    def pack(ids):
        rows = lookup.loc[list(ids)] if ids else lookup.iloc[0:0]
        rows = rows.sort_values("score", ascending=False).head(top)
        return [{"title": r["title"], "year": int(r["year"]), "score": float(r["score"]),
                 "authors": r["authors"]} for _, r in rows.iterrows()]

    return {
        "cited_by": pack(list(G.predecessors(work_id))),   # papers that cite it
        "cites": pack(list(G.successors(work_id))),         # papers it cites
        "n_cited_by": G.in_degree(work_id),
        "n_cites": G.out_degree(work_id),
    }


def reading_order(df: pd.DataFrame, top: int = 20) -> pd.DataFrame:
    """Top-ranked works arranged oldest-first, a suggested chronological reading path."""
    sub = df.head(top)
    return sub.sort_values(["year", "score"], ascending=[True, False]).reset_index(drop=True)
