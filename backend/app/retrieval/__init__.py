"""检索底座：统一检索接口（retrieve + rerank），RAG 与 GraphRAG 复用。"""

from app.retrieval.embeddings import Embedder, SentenceTransformerEmbedder
from app.retrieval.hybrid import (
    BM25Retriever,
    Document,
    HybridRetrieval,
    Retriever,
    SearchResult,
    VectorRetriever,
    build_chroma_collection,
    rrf_fuse,
    tokenize,
)
from app.retrieval.reranker import BgeReranker, Reranker


def build_hybrid_retrieval(
    *,
    enable_bm25: bool = True,
    enable_vector: bool = True,
    enable_rerank: bool = True,
) -> HybridRetrieval:
    """按配置构建统一检索服务（供 RAG / GraphRAG 复用）。"""
    from app.core.config import settings

    retrievers: list[Retriever] = []
    if enable_bm25:
        retrievers.append(BM25Retriever())
    if enable_vector:
        embedder = SentenceTransformerEmbedder(
            model_name=settings.embedding.model_name,
            cache_dir=settings.embedding.cache_dir,
            device=settings.embedding.device,
            query_prefix=settings.retrieval.query_prefix,
        )
        collection = build_chroma_collection(
            settings.chroma.persist_dir, settings.chroma.collection
        )
        retrievers.append(VectorRetriever(embedder, collection))

    reranker = BgeReranker(settings.retrieval.rerank_model) if enable_rerank else None
    return HybridRetrieval(
        retrievers=retrievers, reranker=reranker, rrf_k=settings.retrieval.rrf_k
    )


__all__ = [
    "BM25Retriever",
    "BgeReranker",
    "Document",
    "Embedder",
    "HybridRetrieval",
    "Retriever",
    "Reranker",
    "SearchResult",
    "SentenceTransformerEmbedder",
    "VectorRetriever",
    "build_chroma_collection",
    "build_hybrid_retrieval",
    "rrf_fuse",
    "tokenize",
]
