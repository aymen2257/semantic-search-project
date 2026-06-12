from pydantic import BaseModel
from typing import Optional

class SearchRequest(BaseModel):
    query: str
    top_pages: int = 5
    section: Optional[str] = None
    language: Optional[str] = None
    use_rerank: bool = False          # caller decides whether to rerank

class PageResult(BaseModel):
    url: str
    title: str
    section: str
    language: str
    chunk_type: str
    country: str
    zone: str
    best_distance: float
    matched_chunks: int
    text: str
    rerank_score: Optional[float] = None

class SearchResponse(BaseModel):
    query: str
    applied_filter: Optional[str] = None
    reranked: bool = False
    results: list[PageResult]
    total: int