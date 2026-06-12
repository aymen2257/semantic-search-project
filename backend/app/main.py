from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.models.schemas import SearchRequest, SearchResponse, PageResult
from app.routers.search import search_pages, search_pages_with_rerank
from app.config import settings

app = FastAPI(title="Ooredoo Search API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/api/search", response_model=SearchResponse)
def search(request: SearchRequest):
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    if request.use_rerank:
        results, applied_filter = search_pages_with_rerank(
            query=request.query,
            n_results_chunks=settings.n_results_chunks,
            candidate_pages=10,
            top_pages=request.top_pages,
            section=request.section,
            language=request.language,
        )
    else:
        results, applied_filter = search_pages(
            query=request.query,
            n_results_chunks=settings.n_results_chunks,
            top_pages=request.top_pages,
            section=request.section,
            language=request.language,
        )

    return SearchResponse(
        query=request.query,
        applied_filter=applied_filter,
        reranked=request.use_rerank,
        results=[PageResult(**r) for r in results],
        total=len(results),
    )