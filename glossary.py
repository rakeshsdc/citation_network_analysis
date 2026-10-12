"""Plain-language definitions of every term used in the app and report."""

# (term, meaning)
GLOSSARY = [
    ("Retrieve by: relevance",
     "OpenAlex returns the works that match your keywords best (keyword match in title, abstract and "
     "related text). Good for a balanced, on-topic sample, including newer papers."),
    ("Retrieve by: citations",
     "OpenAlex returns the most-cited works among those matching your keywords. Good for finding the "
     "landmark papers, but it favours older works and under-represents recent ones."),
    ("Add highly cited references (one hop)",
     "After the keyword search, the app looks at the reference lists of the retrieved works. Papers that "
     "are cited by at least 2 of them but did not match the keywords (often classic or foundational "
     "papers) are fetched and added, up to 100. 'One hop' means going exactly one step along the "
     "citation links (from a paper to the papers it cites), and no further. Such works are marked "
     "'added by expansion'."),
    ("Node",
     "One paper (work) in the network."),
    ("Edge / citation link",
     "An arrow from a citing paper to the paper it cites. Only links where both papers are inside the "
     "network are counted."),
    ("Node cap",
     "The maximum number of papers allowed in the network. If more were retrieved, the lowest-priority "
     "ones are dropped before analysis (priority = 60% how often cited inside the retrieved pool + "
     "40% global citations)."),
    ("Score (importance score)",
     "A single number from 0 to 100 that ranks papers by importance in this network. It combines: "
     "35% PageRank, 25% in-network citations (in_cites), 25% global citations (log scale) and 15% "
     "betweenness. 100 = the highest-ranked paper in the set. The same score is shown in every table "
     "(ranked works, reading path, authors, timeline, clusters, connected works) so that results can "
     "be compared. Scores are relative to this search only and cannot be compared between different "
     "searches."),
    ("Rank (#)",
     "Position of the paper when sorted by score; 1 = most important."),
    ("Cites (global citations)",
     "Total number of times OpenAlex records the paper as cited by any work in the world."),
    ("In-net / in_cites",
     "How many papers inside this network cite this paper (incoming links). High values mean the paper "
     "is a key reference for this topic."),
    ("out_refs",
     "How many papers inside this network this paper cites (outgoing links). High values usually "
     "indicate a review article or a paper that builds on much of the topic."),
    ("PageRank",
     "A measure of influence: a paper scores high if it is cited by many papers, especially by papers "
     "that are themselves influential. The same idea Google uses to rank web pages."),
    ("Betweenness",
     "How often a paper lies on the shortest citation path between other papers. High values mark "
     "'bridge' papers that connect different sub-topics."),
    ("Role: Foundational",
     "Published in the older half of the set and cited by many network papers (top 25% of in_cites)."),
    ("Role: Review / hub",
     "Cites many other network papers (top 10% of out_refs and at least 10); typically a review."),
    ("Role: Bridge",
     "Top 10% for betweenness; links different sub-topics."),
    ("Role: Recent influential",
     "Published within the last 3 years of the set and in the top 25% by score."),
    ("Role: Supporting",
     "None of the above; a regular contributing paper. A paper can have several roles."),
    ("Cluster",
     "A group of papers that cite each other more than they cite the rest, found with the Louvain "
     "community-detection method. Each cluster is roughly one sub-topic. Cluster 0 / 'unconnected' "
     "means the paper has no citation link to others in the network. Key terms are the most "
     "frequent title words in the cluster."),
    ("Author total score",
     "Sum of the importance scores of all of an author's papers in the network (counts both "
     "productivity and impact). 'Works' = number of the author's papers in the network."),
    ("Timeline",
     "Total score of papers per publication year, showing when the field's important work appeared."),
    ("Reading path",
     "The top-ranked papers re-ordered oldest to newest, a suggested order for reading the field."),
    ("Node size (network picture)",
     "Larger circle = higher importance score."),
    ("Node colour (network picture)",
     "Colour = cluster. Grey = unconnected papers."),
    ("Arrow direction (network picture)",
     "Arrows point from the citing paper to the cited paper."),
    ("Extractive summary",
     "Sentences selected from the paper's abstract by ranking sentences on keyword and word "
     "frequency. Nothing is rewritten by AI."),
]
