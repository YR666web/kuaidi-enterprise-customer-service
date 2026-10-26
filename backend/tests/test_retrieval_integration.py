"""检索底座集成冒烟测试（真实模型 + 内存 Chroma，标记 slow）。

运行：uv run pytest --run-slow
"""

import pytest

from app.core.config import settings
from app.retrieval.embeddings import SentenceTransformerEmbedder
from app.retrieval.hybrid import Document, VectorRetriever, build_chroma_collection


@pytest.fixture(scope="module")
def embedder() -> SentenceTransformerEmbedder:
    return SentenceTransformerEmbedder(
        model_name=settings.embedding.model_name,
        cache_dir=settings.embedding.cache_dir,
        device=settings.embedding.device,
        query_prefix=settings.retrieval.query_prefix,
    )


@pytest.mark.slow
def test_real_embedder_loads_locally(embedder):
    """真实 bge-base-zh-v1.5 从本地 models/ 缓存加载（不联网），768 维。"""
    q = embedder.embed_query("退货政策是什么")
    assert len(q) == 768
    docs = embedder.embed_documents(["退货政策说明", "物流查询方法"])
    assert len(docs) == 2 and len(docs[0]) == 768


@pytest.mark.slow
def test_real_vector_retrieve_roundtrip(embedder):
    """真实 embedding + 内存 Chroma：入库 → 检索 全链路。"""
    collection = build_chroma_collection("", "test_retrieval")  # 内存模式
    vec = VectorRetriever(embedder, collection)
    vec.index([
        Document(id="d1", text="苹果手机怎么退货"),
        Document(id="d2", text="退货政策说明"),
        Document(id="d3", text="物流查询方法"),
    ])
    results = vec.retrieve("退货政策", top_k=2)
    assert results[0].id == "d2"  # 与"退货政策"最相关
