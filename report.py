"""DOCX report generation for CiteScope."""
from __future__ import annotations

import io
from datetime import datetime

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

from docx.shared import Inches
from glossary import GLOSSARY
from graph import connected_works, reading_order
from netimage import network_png
from summarize import narrative, summarize_text, topic_overview

APP_TITLE = "CiteScope: Citation Network Analysis & Literature Mapping"
COPYRIGHT = (
    "Developed by Dr. Rakesh Chandran S.B, Associate Professor of Physics & IQAC Coordinator, "
    "S.D College, Alappuzha."
)
COPYRIGHT_LINE = f"© {datetime.now().year} Dr. Rakesh Chandran S.B. All rights reserved."


def _shade(cell, hex_fill: str):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    tcPr.append(shd)


def _table(doc, headers, rows, widths=None, font=8.5):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    for i, h in enumerate(headers):
        c = t.rows[0].cells[i]
        c.text = ""
        run = c.paragraphs[0].add_run(h)
        run.bold = True
        run.font.size = Pt(font)
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        _shade(c, "1F3864")
    for r in rows:
        cells = t.add_row().cells
        for i, v in enumerate(r):
            cells[i].text = ""
            run = cells[i].paragraphs[0].add_run(str(v))
            run.font.size = Pt(font)
    if widths:
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Pt(w)
    return t


def _para(doc, text, bold=False, italic=False, size=10.5, color=None, align=None):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold, run.italic = bold, italic
    run.font.size = Pt(size)
    if color:
        run.font.color.rgb = RGBColor(*color)
    if align:
        p.alignment = align
    return p


def _footer(doc):
    for section in doc.sections:
        p = section.footer.paragraphs[0]
        p.text = ""
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(COPYRIGHT + "  " + COPYRIGHT_LINE)
        r.font.size = Pt(8)
        r.italic = True


def build_report(result: dict, meta: dict, keywords: list[str], settings: dict, top_n: int = 15) -> bytes:
    df = result["papers"]
    cap = result["cap_info"]
    works = result["works"]
    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"

    # ---- title block
    _para(doc, APP_TITLE, bold=True, size=20, color=(0x1F, 0x38, 0x64), align=WD_ALIGN_PARAGRAPH.CENTER)
    _para(doc, "Citation Network Analysis Report", size=13, align=WD_ALIGN_PARAGRAPH.CENTER)
    _para(doc, COPYRIGHT, italic=True, size=9.5, align=WD_ALIGN_PARAGRAPH.CENTER)
    _para(doc, COPYRIGHT_LINE, italic=True, size=9.5, align=WD_ALIGN_PARAGRAPH.CENTER)
    _para(doc, f"Report generated: {datetime.now():%d %B %Y, %H:%M}", size=9.5,
          align=WD_ALIGN_PARAGRAPH.CENTER)
    _footer(doc)

    # ---- 1 parameters
    doc.add_heading("1. Search parameters", level=1)
    _table(doc, ["Parameter", "Value"], [
        ["Keywords", ", ".join(keywords)],
        ["Matching mode", "Any keyword (OR)" if settings.get("mode") == "any" else "All keywords (AND)"],
        ["OpenAlex query", meta.get("query", "")],
        ["Publication years", f"{settings.get('year_from')} - {settings.get('year_to')}"],
        ["Retrieved by", ("Relevance (best keyword match)" if settings.get("sort", "relevance") == "relevance" else "Citations (most-cited first)")],
        ["Reference expansion (one hop)", ("Yes: references cited by 2+ retrieved works were added" if settings.get("expand") else "No")],
        ["Data source", "OpenAlex (https://openalex.org)"],
    ], widths=[170, 300], font=9.5)

    # ---- 2 coverage and node cap
    doc.add_heading("2. Data coverage and node cap", level=1)
    total = meta.get("total_matches", 0)
    _para(doc, (
        f"OpenAlex reports {total:,} works matching the query. {meta.get('retrieved_search', 0):,} "
        f"were retrieved by the search"
        + (f" and {meta.get('expanded_added', 0):,} highly cited referenced works were added by one-hop expansion."
           if meta.get("expanded_added") else ".")
    ))
    if cap["applied"]:
        _para(doc, (
            f"NODE CAP APPLIED: {cap['candidates']:,} candidate works were available but the network is "
            f"limited to {cap['cap']:,} nodes. {cap['dropped']:,} lower-priority works were excluded "
            f"before analysis. Works were prioritised by their citation count inside the retrieved pool "
            f"(60%) and their global citation count (40%). Rankings below describe this reduced network "
            f"only; relatively recent or niche works with few citations may be under-represented."
        ), bold=True, color=(0xC0, 0x39, 0x2B))
    else:
        _para(doc, f"The node cap ({cap['cap']:,}) was not reached: all {cap['candidates']:,} "
                   f"retrieved works are included in the network.")
    if total > meta.get("retrieved_search", 0):
        _para(doc, (
            f"Note: only the first {meta.get('retrieved_search', 0):,} of {total:,} matching works were "
            f"retrieved, so the analysis is a sample of the topic, not its full literature."
        ), italic=True)

    # ---- 3 overview
    doc.add_heading("3. Topic overview (extractive summary)", level=1)
    _para(doc, narrative(result, keywords))
    pts = topic_overview(df, works, keywords, n_papers=12, n_sent=6)
    if pts:
        _para(doc, "Key statements drawn from the abstracts of the most influential works:", bold=True)
        for p in pts:
            para = doc.add_paragraph(style="List Bullet")
            r = para.add_run(p["sentence"] + " ")
            r.font.size = Pt(10)
            s = para.add_run(f"[{p['authors']}, {p['year']}]")
            s.italic = True
            s.font.size = Pt(9)
    _para(doc, "Summaries are generated by extractive sentence ranking (no AI model); sentences are "
               "copied from abstracts, not rewritten.", italic=True, size=9)

    # ---- 4 network stats
    doc.add_heading("4. Network statistics", level=1)
    _table(doc, ["Measure", "Value"], [
        ["Works (nodes)", len(df)],
        ["Citation links (edges)", result["n_edges"]],
        ["Thematic clusters", len(result["clusters"])],
        ["Works with no link inside the network", int((df["in_cites"] + df["out_refs"] == 0).sum())],
    ], widths=[250, 150], font=9.5)

    png = network_png(result, max_nodes=80)
    if png:
        doc.add_picture(io.BytesIO(png), width=Inches(6.3))
        doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        _para(doc, f"Figure 1. Citation network of the {min(80, len(df))} highest-scoring works (connected ones). Node size = "
                   "importance score; colour = cluster (grey = unconnected); arrows point from the citing to "
                   "the cited work. Labels show first author and year for the top 8 works. Works with no citation link to another drawn work are omitted from the picture (but remain in all tables).",
              italic=True, size=9, align=WD_ALIGN_PARAGRAPH.CENTER)

    # ---- 5 ranked papers
    doc.add_heading(f"5. Most important works (top {min(top_n, len(df))})", level=1)
    _para(doc, "Importance score (0-100) = 35% PageRank + 25% in-network citations + 25% global "
               "citations (log scale) + 15% betweenness. Ordered by score.", italic=True, size=9)
    top = df.head(top_n)
    _table(doc, ["#", "Title", "Year", "Authors", "Cites", "In-net", "Score", "Role"],
           [[r["rank"], r["title"], r["year"], r["authors"], r["cites"], r["in_cites"],
             r["score"], r["role"]] for _, r in top.iterrows()],
           widths=[18, 150, 28, 90, 30, 30, 30, 70], font=8)

    _para(doc, "Column guide: # = rank by score; Cites = global citations in OpenAlex; In-net = works in this "
               "network that cite it; Score = importance score (0-100); Role = type of contribution. "
               "Full definitions are in Appendix A.", italic=True, size=9)

    # ---- 6 reading order
    doc.add_heading("6. Suggested chronological reading path", level=1)
    ro = reading_order(df, top=min(top_n, len(df)))
    _table(doc, ["Year", "Title", "Authors", "Score"],
           [[r["year"], r["title"], r["authors"], r["score"]] for _, r in ro.iterrows()],
           widths=[34, 240, 130, 34], font=8.5)

    # ---- 7 authors
    doc.add_heading("7. Most influential authors", level=1)
    adf = result["authors"]
    if not adf.empty:
        _para(doc, "Author score = sum of the importance scores of that author's works in the network.",
              italic=True, size=9)
        _table(doc, ["#", "Author", "Works", "Total score", "Citations", "Active", "Top work"],
               [[r["rank"], r["author"], r["papers"], r["total_score"], r["total_cites"],
                 r["active"], r["top_paper"]] for _, r in adf.head(15).iterrows()],
               widths=[18, 90, 32, 40, 42, 50, 200], font=8)

    # ---- 8 timeline
    doc.add_heading("8. Timeline of the field", level=1)
    tdf = result["timeline"]
    if not tdf.empty:
        # years with the strongest contributions first would hide chronology; show chronological
        strong = tdf.sort_values("top_score", ascending=False).head(20).sort_values("year")
        _para(doc, "Years containing the highest-scoring work (chronological):", size=9, italic=True)
        _table(doc, ["Year", "Works that year", "Highest-ranked work", "Score"],
               [[r["year"], r["papers"], r["top_paper"], r["top_score"]] for _, r in strong.iterrows()],
               widths=[34, 50, 300, 40], font=8.5)

    # ---- 9 clusters
    doc.add_heading("9. Thematic clusters", level=1)
    if result["clusters"]:
        _table(doc, ["Cluster", "Works", "Key terms", "Years", "Avg score", "Leading work"],
               [[c["id"], c["size"], c["label"], c["years"], c["avg_score"], c["top_paper"]]
                for c in result["clusters"][:12]],
               widths=[36, 34, 120, 50, 40, 190], font=8)
    else:
        _para(doc, "No clusters of connected works were detected.")

    # ---- 10 per-paper detail
    doc.add_heading(f"10. Detail for the top {min(10, len(df))} works", level=1)
    for _, r in df.head(10).iterrows():
        w = works[r["id"]]
        doc.add_heading(f"#{r['rank']}  {r['title']}", level=2)
        meta_line = f"{r['authors']} | {r['year']} | {r['venue'] or 'venue n/a'} | {r['role']}"
        _para(doc, meta_line, italic=True, size=9)
        if r["doi"]:
            _para(doc, r["doi"], size=9, color=(0x1F, 0x4E, 0x9E))
        _para(doc, f"Importance score {r['score']} | {r['cites']} global citations | "
                   f"cited by {r['in_cites']} and cites {r['out_refs']} works in this network | "
                   f"cluster {r['cluster'] or 'unconnected'}", size=9.5)
        _para(doc, "Summary: " + summarize_text(w.get("abstract", ""), n=2, keywords=keywords), size=10)
        cw = connected_works(result, r["id"], top=3)
        if cw["cited_by"]:
            _para(doc, "Most important works citing it:", bold=True, size=9.5)
            for c in cw["cited_by"]:
                doc.add_paragraph(f"{c['title']} ({c['year']}), score {c['score']}", style="List Bullet")
        if cw["cites"]:
            _para(doc, "Most important works it builds on:", bold=True, size=9.5)
            for c in cw["cites"]:
                doc.add_paragraph(f"{c['title']} ({c['year']}), score {c['score']}", style="List Bullet")

    # ---- 11 method + limitations
    doc.add_heading("11. Method and limitations", level=1)
    for line in [
        "Citation links are taken from OpenAlex 'referenced_works'. An edge points from the citing work to the cited work, and only links between works inside the network are counted.",
        "PageRank identifies foundational works, betweenness identifies works bridging sub-topics, and Louvain community detection groups related works into clusters.",
        "Roles: Foundational (older, widely cited in the network), Review / hub (cites many network works), Bridge (high betweenness), Recent influential (last 3 years, top-quartile score).",
        "Results depend on keyword quality, the number of works retrieved and the node cap. Some works lack abstracts or reference lists, especially older ones, which reduces their connectivity.",
        "Citation counts come from OpenAlex and may differ from Scopus, Web of Science or Google Scholar.",
    ]:
        doc.add_paragraph(line, style="List Bullet")

    # ---- appendix: glossary
    doc.add_heading("Appendix A. Guide to terms, fields and settings", level=1)
    _table(doc, ["Term / field", "Meaning"], [[t, m] for t, m in GLOSSARY],
           widths=[130, 340], font=8.5)

    _para(doc, "")
    _para(doc, COPYRIGHT, italic=True, size=9.5, align=WD_ALIGN_PARAGRAPH.CENTER)
    _para(doc, COPYRIGHT_LINE, italic=True, size=9.5, align=WD_ALIGN_PARAGRAPH.CENTER)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
