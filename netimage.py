"""Static PNG of the citation network (for the Word report and download)."""
from __future__ import annotations

import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx

PALETTE = ["#4C78A8", "#F58518", "#54A24B", "#E45756", "#72B7B2", "#B279A2",
           "#FF9DA6", "#9D755D", "#BAB0AC", "#EECA3B", "#2F4B7C", "#A05195"]


def network_png(result: dict, max_nodes: int = 80, label_top: int = 8) -> bytes:
    df = result["papers"].head(max_nodes)
    if df.empty:
        return b""
    keep = set(df["id"])
    H = result["G"].subgraph(keep).copy()
    # papers with no link to another drawn paper would only distort the layout
    isolated = [n for n in H if H.degree(n) == 0]
    H.remove_nodes_from(isolated)
    if len(H) == 0:
        return b""
    U = H.to_undirected()
    pos = nx.spring_layout(U, seed=7, k=3.0 / max(len(U), 1) ** 0.5, iterations=300, scale=1.0)
    info = df.set_index("id")
    smax = float(df["score"].max() or 1.0)
    sizes = [40 + 420 * info.loc[n, "score"] / smax for n in H]
    colors = [PALETTE[(info.loc[n, "cluster"] - 1) % len(PALETTE)] if info.loc[n, "cluster"] else "#BBBBBB"
              for n in H]

    fig, ax = plt.subplots(figsize=(10, 7.5), dpi=150)
    nx.draw_networkx_edges(H, pos, ax=ax, edge_color="#B8B8B8", width=0.5, arrows=True,
                           arrowsize=5, alpha=0.55)
    nx.draw_networkx_nodes(H, pos, ax=ax, node_size=sizes, node_color=colors,
                           edgecolors="white", linewidths=0.7, alpha=0.95)
    labels = {r["id"]: f"{r['authors'].split(',')[0].split(' et al')[0]} {r['year']}"
              for _, r in df.head(label_top).iterrows() if r["id"] in H}
    nx.draw_networkx_labels(H, pos, labels=labels, ax=ax, font_size=7, font_weight="bold",
                            bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.8))
    note = f"; {len(isolated)} unconnected not drawn" if isolated else ""
    ax.set_title(f"Citation network of {len(H)} connected works among the top {len(df)}{note}\n"
                 "size = importance score, colour = cluster, arrows: citing -> cited", fontsize=9)
    ax.margins(0.08)
    ax.axis("off")
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return buf.getvalue()
