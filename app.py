"""CiteScope: Citation Network Analysis & Literature Mapping (Streamlit app)."""
from __future__ import annotations

import re
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

from graph import analyze, connected_works, reading_order
from openalex import fetch_all
from report import APP_TITLE, COPYRIGHT, COPYRIGHT_LINE, build_report
from summarize import narrative, summarize_text, topic_overview

st.set_page_config(page_title="CiteScope", page_icon="🕸️", layout="wide")

PALETTE = ["#4C78A8", "#F58518", "#54A24B", "#E45756", "#72B7B2", "#B279A2",
           "#FF9DA6", "#9D755D", "#BAB0AC", "#EECA3B", "#2F4B7C", "#A05195"]


def footer():
    st.divider()
    st.markdown(
        f"<div style='text-align:center;color:#666;font-size:0.85rem'>{COPYRIGHT}<br>"
        f"{COPYRIGHT_LINE}</div>",
        unsafe_allow_html=True,
    )


def parse_keywords(text: str) -> list[str]:
    parts = re.split(r"[\n,;]+", text)
    return [p.strip() for p in parts if p.strip()]


@st.cache_data(show_spinner=False, ttl=3600)
def cached_fetch(keywords, mode, y0, y1, max_fetch, sort, expand, email):
    return fetch_all(list(keywords), mode, y0, y1, max_fetch, sort, expand, email)


def network_html(result, max_display: int) -> str:
    from pyvis.network import Network

    df = result["papers"].head(max_display)
    keep = set(df["id"])
    G = result["G"]
    net = Network(height="680px", width="100%", directed=True, bgcolor="#ffffff",
                  font_color="#222222", cdn_resources="in_line")
    max_score = float(df["score"].max() or 1.0)
    for _, r in df.iterrows():
        color = PALETTE[(r["cluster"] - 1) % len(PALETTE)] if r["cluster"] else "#BBBBBB"
        tip = (f"{r['title']}\n{r['authors']} ({r['year']})\nScore {r['score']} | "
               f"cites {r['cites']} | cluster {r['cluster'] or '-'}")
        net.add_node(r["id"], label=str(r["year"]), title=tip,
                     size=8 + 32 * r["score"] / max_score, color=color)
    for u, v in G.edges():
        if u in keep and v in keep:
            net.add_edge(u, v, color="#CCCCCC", arrows="to")
    net.set_options('{"physics":{"barnesHut":{"gravitationalConstant":-6000,"springLength":120}},'
                    '"interaction":{"hover":true}}')
    return net.generate_html()


# ----------------------------------------------------------------- header
st.markdown(
    f"<h1 style='margin-bottom:0'>🕸️ {APP_TITLE}</h1>"
    "<p style='color:#555;margin-top:0.2rem'>Enter topic keywords to map the citation network, "
    "rank the key papers, authors and years, and download a Word report.</p>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("Search settings")
    kw_text = st.text_area("Topic keywords (one per line or comma-separated)",
                           placeholder="graphene supercapacitor\nelectrode materials", height=120)
    mode = st.radio("Match", ["any", "all"], horizontal=True,
                    help="any = a work may match any keyword (OR); all = must match every keyword (AND)")
    this_year = datetime.now().year
    y0, y1 = st.slider("Publication years", 1950, this_year, (2000, this_year))
    max_fetch = st.slider("Works to retrieve", 50, 1000, 300, step=50)
    node_cap = st.slider("Node cap (max works in network)", 50, 1000, 300, step=50,
                         help="If more works are available the lowest-priority ones are dropped "
                              "and this is stated in the report.")
    sort = st.selectbox("Retrieve by", ["relevance", "citations"])
    expand = st.checkbox("Add highly cited references (one hop)", value=True)
    top_n = st.slider("Works listed in report", 10, 30, 15)
    email = st.text_input("Your e-mail (optional, speeds up OpenAlex)", "")
    run = st.button("Run analysis", type="primary", width="stretch")
    st.caption(COPYRIGHT)

keywords = parse_keywords(kw_text)

if run:
    if not keywords:
        st.error("Please enter at least one keyword.")
    else:
        try:
            with st.status("Fetching works from OpenAlex...", expanded=False) as status:
                works, meta = cached_fetch(tuple(keywords), mode, y0, y1, max_fetch, sort, expand, email)
                status.update(label=f"Retrieved {len(works)} works. Building network...")
                result = analyze(works, node_cap)
                status.update(label="Analysis complete", state="complete")
            settings = {"mode": mode, "year_from": y0, "year_to": y1, "sort": sort,
                        "expand": expand}
            st.session_state["state"] = {
                "result": result, "meta": meta, "keywords": keywords,
                "settings": settings, "top_n": top_n,
                "report": build_report(result, meta, keywords, settings, top_n=top_n)
                if not result["papers"].empty else b"",
            }
        except Exception as e:  # network / API errors
            st.error(f"Could not complete the analysis: {e}")

S = st.session_state.get("state")
if not S:
    st.info("Enter keywords in the sidebar and press **Run analysis**.")
    footer()
    st.stop()

result, meta, kws = S["result"], S["meta"], S["keywords"]
df, cap = result["papers"], result["cap_info"]

if df.empty:
    st.warning("No works found. Try different keywords or a wider year range.")
    footer()
    st.stop()

# ---------------------------------------------------------------- notices
if cap["applied"]:
    st.warning(
        f"**Node cap applied:** {cap['candidates']:,} works were available; the network is limited to "
        f"{cap['cap']:,} nodes ({cap['dropped']:,} lower-priority works excluded). "
        "This is stated in the downloadable report."
    )
if meta["total_matches"] > meta["retrieved_search"]:
    st.caption(f"OpenAlex lists {meta['total_matches']:,} matching works; the first "
               f"{meta['retrieved_search']:,} were retrieved.")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Works in network", len(df))
m2.metric("Citation links", result["n_edges"])
m3.metric("Clusters", len(result["clusters"]))
ys = df[df["year"] > 0]["year"]
m4.metric("Years covered", f"{int(ys.min())}-{int(ys.max())}" if len(ys) else "n/a")

st.download_button("⬇️ Download report (DOCX)", S["report"],
                   file_name="CiteScope_report.docx",
                   mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

tabs = st.tabs(["Overview", "Ranked works", "Authors", "Timeline", "Clusters", "Network", "Work details"])

with tabs[0]:
    st.subheader("Topic overview")
    st.write(narrative(result, kws))
    for p in topic_overview(df, result["works"], kws):
        st.markdown(f"- {p['sentence']}  \n  <small>*{p['authors']}, {p['year']}*</small>",
                    unsafe_allow_html=True)
    st.caption("Extractive summary: sentences are selected from abstracts, not generated by AI.")
    st.subheader("Suggested chronological reading path")
    ro = reading_order(df, top=min(S["top_n"], len(df)))
    st.dataframe(ro[["year", "title", "authors", "score", "role"]], width="stretch", hide_index=True)

with tabs[1]:
    st.subheader("Works ranked by citation-network importance")
    st.dataframe(
        df[["rank", "title", "year", "authors", "cites", "in_cites", "out_refs", "score", "role",
            "cluster", "venue"]],
        width="stretch", hide_index=True)
    st.caption("Score (0-100) = 35% PageRank + 25% in-network citations + 25% global citations (log) "
               "+ 15% betweenness.")

with tabs[2]:
    st.subheader("Most influential authors")
    st.dataframe(result["authors"].head(50), width="stretch", hide_index=True)

with tabs[3]:
    st.subheader("Timeline")
    tdf = result["timeline"]
    if not tdf.empty:
        st.bar_chart(tdf.set_index("year")["total_score"])
        st.caption("Bar height = combined importance of works published that year.")
        st.dataframe(tdf, width="stretch", hide_index=True)

with tabs[4]:
    st.subheader("Thematic clusters")
    for c in result["clusters"][:15]:
        st.markdown(f"**Cluster {c['id']}** ({c['size']} works, {c['years']}): {c['label']}  \n"
                    f"Leading work: *{c['top_paper']}*")

with tabs[5]:
    st.subheader("Citation network")
    if len(df) > 30:
        max_display = st.slider("Nodes drawn", 20, min(400, len(df)), min(120, len(df)), step=10)
    else:
        max_display = len(df)
    st.caption("Node size = importance, colour = cluster, arrows point from citing to cited work. "
               "Only the top-scoring nodes are drawn for readability.")
    components.html(network_html(result, max_display), height=700, scrolling=True)

with tabs[6]:
    st.subheader("Work details and connections")
    options = {f"#{r['rank']} {r['title'][:90]} ({r['year']})": r["id"] for _, r in df.head(50).iterrows()}
    choice = st.selectbox("Choose a work", list(options))
    wid = options[choice]
    row = df[df["id"] == wid].iloc[0]
    w = result["works"][wid]
    st.markdown(f"**{row['title']}**  \n{row['authors']} | {row['year']} | {row['venue'] or 'venue n/a'}  \n"
                f"Role: {row['role']} | Score {row['score']} | {row['cites']} global citations")
    if row["doi"]:
        st.markdown(f"[{row['doi']}]({row['doi']})")
    st.write("**Summary:** " + summarize_text(w.get("abstract", ""), n=2, keywords=kws))
    cw = connected_works(result, wid, top=5)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**Cited by {cw['n_cited_by']} works in network (top by importance)**")
        for c in cw["cited_by"]:
            st.markdown(f"- {c['title']} ({c['year']}), score {c['score']}")
    with c2:
        st.markdown(f"**Cites {cw['n_cites']} works in network (top by importance)**")
        for c in cw["cites"]:
            st.markdown(f"- {c['title']} ({c['year']}), score {c['score']}")

footer()
