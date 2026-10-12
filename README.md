# CiteScope: Citation Network Analysis & Literature Mapping

Enter topic keywords and CiteScope will:

- retrieve works from [OpenAlex](https://openalex.org) (free, no API key)
- build a citation network and rank works by PageRank, in-network citations, global citations and betweenness
- list the most important works, authors and years, with each work's connected papers
- group works into thematic clusters (Louvain)
- write free, extractive summaries (sentences picked from abstracts, no AI model)
- cap the number of nodes and state the cap in the on-screen notice and in the report
- export everything as a Word (.docx) report

Developed by Dr. Rakesh Chandran S.B, Associate Professor of Physics & IQAC Coordinator, S.D College, Alappuzha.
(c) Dr. Rakesh Chandran S.B. All rights reserved.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Host free from GitHub (Streamlit Community Cloud)

1. Push this folder to a GitHub repository (`app.py` at the repo root).
2. Go to https://share.streamlit.io, sign in with GitHub and choose **New app**.
3. Select the repository, branch `main` and main file `app.py`, then **Deploy**.

Every push to the repository redeploys the app. (GitHub Pages cannot run Streamlit, so Streamlit
Community Cloud, Hugging Face Spaces or Render is used for hosting.)

## Files

| File | Purpose |
|------|---------|
| `app.py` | Streamlit interface |
| `openalex.py` | Search and fetch from OpenAlex |
| `graph.py` | Node cap, network, metrics, clusters, authors, timeline |
| `summarize.py` | Extractive summaries |
| `report.py` | DOCX report |

## Notes

- Large graphs are slow to draw; the node cap (default 300, max 1000) keeps the app responsive.
- Adding your e-mail in the sidebar uses OpenAlex's faster "polite pool".
- Results depend on keyword quality. Some older works lack abstracts or reference lists.
