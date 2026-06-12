import re
import chromadb
from chromadb.utils import embedding_functions
from sentence_transformers import CrossEncoder
from collections import defaultdict
from app.config import settings, COUNTRY_MAP

# ── load once at startup ──────────────────────────────────────
e5_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name=settings.embedding_model
)

chroma_client = chromadb.PersistentClient(path=settings.chroma_path)

collection = chroma_client.get_collection(
    name=settings.collection_name,
    embedding_function=e5_ef,
)

reranker = CrossEncoder("BAAI/bge-reranker-v2-m3")
reranker.predict([["warmup query", "warmup document"]])  # warmup at startup

print(f"Collection '{settings.collection_name}' loaded — {collection.count()} chunks")
print("Reranker loaded and warmed up")

# ── text helpers ──────────────────────────────────────────────
def normalize_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())

def strip_passage_prefix(s: str) -> str:
    s = s.strip()
    if s.lower().startswith("passage:"):
        return s[len("passage:"):].strip()
    return s

def strip_leading_title_once(text: str, title: str) -> str:
    if not title:
        return text
    t = normalize_spaces(text)
    ttl = normalize_spaces(title)
    pattern = rf"^{re.escape(ttl)}(?:\s*[:\-|]\s*|\s+)?"
    return re.sub(pattern, "", t, flags=re.IGNORECASE).strip()

def merge_text_keep_first_title_and_passage(chunks_in_order, page_title):
    merged_parts = []
    for i, chunk_text in enumerate(chunks_in_order):
        s = (chunk_text or "").strip()
        if i == 0:
            merged_parts.append(s)
        else:
            s = strip_passage_prefix(s)
            s = strip_leading_title_once(s, page_title)
            merged_parts.append(s)
    return " ".join(p for p in merged_parts if p).strip()

# ── nan fix ───────────────────────────────────────────────────
def clean(value: str) -> str:
    return "" if str(value).lower() == "nan" else str(value)

# ── country extraction ────────────────────────────────────────
def extract_country(query: str):
    q = query.lower()
    for keyword, country in COUNTRY_MAP.items():
        if keyword in q:
            return country
    return None

# ── page key ──────────────────────────────────────────────────
def get_page_key(meta: dict) -> str:
    country = clean(meta.get("country", ""))
    chunk_type = meta.get("chunk_type", "")
    if country:
        return f"{meta.get('url', '')}|{chunk_type}|{country}"
    return meta.get("content_hash") or meta.get("url", "")

# ── build page result ─────────────────────────────────────────
def build_page_result(hits: list) -> dict:
    m0, doc0, best_dist = hits[0]

    MAX_FIRST_CHUNKS = 3

    country      = clean(m0.get("country", ""))
    chunk_type   = m0.get("chunk_type", "")
    content_hash = m0.get("content_hash", "")
    url          = m0.get("url", "")

    if country:
        where = {
            "$and": [
                {"url": url},
                {"country": country},
                {"chunk_type": chunk_type},
            ]
        }
    elif content_hash:
        where = {"content_hash": content_hash}
    else:
        where = {"url": url}

    page_data = collection.get(
        where=where,
        include=["documents", "metadatas"]
    )

    first_chunks = []
    for doc, meta in zip(page_data["documents"], page_data["metadatas"]):
        idx = int(meta.get("chunk_index", 0))
        if idx < MAX_FIRST_CHUNKS:
            first_chunks.append((idx, meta, doc))

    first_chunks.sort(key=lambda x: x[0])

    if not first_chunks:
        first_chunks = [(int(m0.get("chunk_index", 0)), m0, doc0)]

    merged_text = merge_text_keep_first_title_and_passage(
        chunks_in_order=[x[2] for x in first_chunks],
        page_title=m0.get("title", "")
    )

    return {
        "url":            url,
        "title":          m0.get("title", ""),
        "section":        m0.get("section", ""),
        "language":       m0.get("language", ""),
        "chunk_type":     chunk_type,
        "country":        country,
        "zone":           clean(m0.get("zone", "")),
        "best_distance":  best_dist,
        "matched_chunks": len(first_chunks),
        "text":           merged_text,
        "rerank_score":   None,  # filled in by reranker if used
    }

# ── main search function ──────────────────────────────────────
def search_pages(
    query: str,
    n_results_chunks: int = 20,
    top_pages: int = 5,
    section: str | None = None,
    language: str | None = None,
):
    q = f"query: {query}"
    filters = []
    applied_filter = None

    country = extract_country(query)
    if country:
        filters.append({"country": country})
        applied_filter = f"country={country}"

    if section and section in ("personal", "business"):
        filters.append({"section": section.lower()})
        applied_filter = f"{applied_filter or ''} section={section}".strip()

    if language and language in ("fr", "en"):
        filters.append({"language": language.lower()})
        applied_filter = f"{applied_filter or ''} language={language}".strip()

    where = None
    if len(filters) == 1:
        where = filters[0]
    elif len(filters) > 1:
        where = {"$and": filters}

    kwargs = {
        "query_texts": [q],
        "n_results":   n_results_chunks,
        "include":     ["documents", "metadatas", "distances"],
    }
    if where:
        kwargs["where"] = where

    res = collection.query(**kwargs)
    docs  = res["documents"][0]
    metas = res["metadatas"][0]
    dists = res["distances"][0]

    grouped = defaultdict(list)
    for doc, meta, dist in zip(docs, metas, dists):
        grouped[get_page_key(meta)].append((meta, doc, dist))

    ranked_groups = sorted(
        grouped.values(),
        key=lambda hits: min(h[2] for h in hits)
    )

    page_results = [
        build_page_result(hits)
        for hits in ranked_groups[:top_pages]
    ]

    return page_results, applied_filter

# ── reranked search ───────────────────────────────────────────
def search_pages_with_rerank(
    query: str,
    n_results_chunks: int = 20,
    candidate_pages: int = 5,
    top_pages: int = 5,
    section: str | None = None,
    language: str | None = None,
):
    candidates, applied_filter = search_pages(
        query=query,
        n_results_chunks=n_results_chunks,
        top_pages=candidate_pages,
        section=section,
        language=language,
    )

    if not candidates:
        return [], applied_filter

    pairs = [
        [query, f"{r['title']}\n{r['url']}\n{r['text'][:250]}"]
        for r in candidates
    ]

    scores = reranker.predict(pairs)

    reranked = []
    for r, score in zip(candidates, scores):
        r = dict(r)
        r["rerank_score"] = round(float(score), 4)
        reranked.append(r)

    reranked.sort(key=lambda x: x["rerank_score"], reverse=True)

    return reranked[:top_pages], applied_filter