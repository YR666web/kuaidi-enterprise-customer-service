"""检索底座测试：RRF 融合、BM25、混合检索开关、重排、向量化前缀。"""

from app.retrieval.embeddings import SentenceTransformerEmbedder
from app.retrieval.hybrid import (
    BM25Retriever,
    Document,
    HybridRetrieval,
    SearchResult,
    VectorRetriever,
    rrf_fuse,
    tokenize,
)


def _docs() -> list[Document]:
    return [
        Document(id="d1", text="苹果手机怎么退货", metadata={"src": "a"}),
        Document(id="d2", text="退货政策说明", metadata={"src": "b"}),
        Document(id="d3", text="物流查询方法", metadata={"src": "c"}),
    ]


# —— 分词 ——
def test_tokenize():
    assert "hello" in tokenize("Hello 世界")
    assert "世" in tokenize("世界")


# —— RRF 融合 ——
def test_rrf_fuse_dedup_and_merge():
    a = SearchResult(id="x", text="x", score=1.0)
    b = SearchResult(id="y", text="y", score=0.9)
    c = SearchResult(id="x", text="x", score=0.8)  # 与 a 同 id
    fused = rrf_fuse([[a, b], [c]], k=60)
    assert len(fused) == 2  # 按 id 去重
    assert fused[0].id == "x"  # x 出现在两路，RRF 分数最高


# —— BM25 ——
def test_bm25_retrieve():
    bm25 = BM25Retriever(_docs())
    results = bm25.retrieve("退货", top_k=2)
    assert len(results) == 2
    assert all("退货" in r.text for r in results)  # 只命中含"退货"的两篇
    assert results[0].score > 0


def test_bm25_empty():
    assert BM25Retriever().retrieve("x", 5) == []


def test_bm25_incremental_index_keeps_previous_documents():
    bm25 = BM25Retriever()
    bm25.add_documents([Document(id="old", text="apple inventory")])
    bm25.add_documents([Document(id="new", text="banana inventory")])
    bm25.add_documents([Document(id="third", text="cherry inventory")])

    assert bm25.retrieve("apple", top_k=1)[0].id == "old"
    assert bm25.retrieve("banana", top_k=1)[0].id == "new"


def test_hybrid_incremental_index_keeps_previous_documents():
    hybrid = HybridRetrieval(retrievers=[BM25Retriever()])
    hybrid.index([Document(id="old", text="apple inventory")])
    hybrid.index([Document(id="new", text="banana inventory")])
    hybrid.index([Document(id="third", text="cherry inventory")])

    assert hybrid.retrieve("apple", top_k=1)[0].id == "old"
    assert hybrid.retrieve("banana", top_k=1)[0].id == "new"


def test_hybrid_metadata_filter_enforces_tenant_boundary():
    hybrid = HybridRetrieval(retrievers=[BM25Retriever()])
    hybrid.index([
        Document(id="a", text="退货政策仅供 A", metadata={"tenant_id": "tenant-a"}),
        Document(id="b", text="退货政策仅供 B", metadata={"tenant_id": "tenant-b"}),
    ])

    results = hybrid.retrieve("退货政策", top_k=5, metadata_filter={"tenant_id": "tenant-b"})
    assert [result.id for result in results] == ["b"]


# —— 向量（假 embedder + 假 collection）——
class _FakeEmbedder:
    def __init__(self):
        self.query_texts = []
        self.doc_texts = []

    def embed_query(self, text):
        self.query_texts.append(text)
        return [1.0]

    def embed_documents(self, texts):
        self.doc_texts.extend(texts)
        return [[1.0] for _ in texts]


class _FakeCollection:
    def __init__(self):
        self.ids = []
        self.documents = []

    def add(self, ids, embeddings, documents, metadatas):
        self.ids.extend(ids)
        self.documents.extend(documents)

    def query(self, query_embeddings, n_results, include):
        n = min(n_results, len(self.ids))
        return {
            "ids": [self.ids[:n]],
            "documents": [self.documents[:n]],
            "metadatas": [[{}] * n],
            "distances": [[0.1] * n],
        }


def test_vector_retriever():
    vec = VectorRetriever(_FakeEmbedder(), _FakeCollection())
    vec.index(_docs())
    results = vec.retrieve("退货", top_k=2)
    assert len(results) == 2
    assert results[0].score == 0.9  # 1 - 0.1（cosine 距离 → 相似度）


# —— 混合检索 ——
def test_hybrid_only_bm25():
    hybrid = HybridRetrieval(retrievers=[BM25Retriever(_docs())])
    assert len(hybrid.retrieve("退货", top_k=2)) == 2


def test_hybrid_rrf_merge_two_retrievers():
    vec = VectorRetriever(_FakeEmbedder(), _FakeCollection())
    vec.index(_docs())
    hybrid = HybridRetrieval(retrievers=[BM25Retriever(_docs()), vec], rrf_k=60)
    results = hybrid.retrieve("退货", top_k=3)
    assert len(results) == 3


def test_hybrid_no_retriever():
    assert HybridRetrieval().retrieve("x", 5) == []


# —— 重排 ——
class _FakeReranker:
    def rerank(self, query, candidates, top_k):
        return sorted(candidates, key=lambda c: len(c.text), reverse=True)[:top_k]


def test_rerank_delegates():
    hybrid = HybridRetrieval(retrievers=[BM25Retriever(_docs())], reranker=_FakeReranker())
    candidates = [SearchResult("a", "短", 1.0), SearchResult("b", "比较长的文本", 1.0)]
    assert hybrid.rerank("q", candidates, top_k=1)[0].id == "b"


def test_rerank_passthrough_without_reranker():
    hybrid = HybridRetrieval(retrievers=[BM25Retriever(_docs())])
    candidates = [SearchResult("a", "x", 1.0), SearchResult("b", "y", 2.0)]
    assert hybrid.rerank("q", candidates, top_k=1)[0].id == "a"


# —— 向量化前缀（bge query 前缀，文档不加前缀）——
class _FakeModel:
    def __init__(self):
        self.inputs = []

    def encode(self, texts, normalize_embeddings=True):
        self.inputs.append(list(texts))
        return [[0.1] * 4 for _ in texts]


def test_embedder_query_prefix():
    model = _FakeModel()
    emb = SentenceTransformerEmbedder("m", "cache", query_prefix="前缀：", model=model)
    emb.embed_query("退货")
    emb.embed_documents(["文档A", "文档B"])
    assert model.inputs[0] == ["前缀：退货"]  # query 加前缀
    assert model.inputs[1] == ["文档A", "文档B"]  # 文档不加前缀
