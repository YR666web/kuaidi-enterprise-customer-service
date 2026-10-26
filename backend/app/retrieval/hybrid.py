"""检索底座：BM25 + 向量双路召回，RRF 融合。

- BM25 用 rank_bm25 进程内实现，Retriever 接口预留 Elasticsearch 切换位；
- 向量路经 Embedder + Chroma collection（cosine）；
- 两路可开关；向量库 / BM25 / rerank 均可插拔。
"""

import re
from dataclasses import dataclass, field, replace
from typing import Any, Protocol

from rank_bm25 import BM25Okapi

# —— 数据模型 ——


@dataclass
class Document:
    """待索引文档。"""

    id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResult:
    """召回结果。"""

    id: str
    text: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


class Retriever(Protocol):
    """统一召回接口（可插拔）。"""

    def retrieve(
        self, query: str, top_k: int, metadata_filter: dict[str, Any] | None = None
    ) -> list[SearchResult]: ...


# —— 分词 ——
_CJK_RE = re.compile(r"[一-鿿]")
_WORD_RE = re.compile(r"[a-zA-Z0-9]+")


def tokenize(text: str) -> list[str]:
    """简单分词：英文按词、中文按字（可替换为 jieba 等）。"""
    tokens = [m.group().lower() for m in _WORD_RE.finditer(text)]
    tokens.extend(_CJK_RE.findall(text))
    return tokens


# —— BM25 ——
class BM25Retriever:
    """rank_bm25 进程内 BM25 召回；生产切换 Elasticsearch 见 build_hybrid_retrieval。"""

    def __init__(self, documents: list[Document] | None = None, tokenizer=tokenize) -> None:
        self.tokenizer = tokenizer
        self._documents: list[Document] = []
        self._bm25: BM25Okapi | None = None
        if documents:
            self.index(documents)

    def index(self, documents: list[Document]) -> None:
        """Replace the in-memory index with ``documents``.

        This remains the explicit rebuild operation used when restoring the
        index from Chroma or after deleting documents.
        """
        self._documents = list(documents)
        self._rebuild()

    def add_documents(self, documents: list[Document]) -> None:
        """Append documents and rebuild BM25.

        ``HybridRetrieval.index`` is used by incremental ingestion.  Calling
        ``index`` there used to discard all previously uploaded documents.
        IDs are treated as upserts so retrying an ingestion does not create
        duplicate BM25 entries.
        """
        if not documents:
            return
        by_id = {document.id: document for document in self._documents}
        for document in documents:
            by_id[document.id] = document
        self._documents = list(by_id.values())
        self._rebuild()

    def _rebuild(self) -> None:
        corpus = [self.tokenizer(d.text) for d in self._documents]
        self._bm25 = BM25Okapi(corpus) if corpus else None

    def retrieve(
        self, query: str, top_k: int, metadata_filter: dict[str, Any] | None = None
    ) -> list[SearchResult]:
        if not self._bm25 or top_k <= 0:
            return []
        scores = self._bm25.get_scores(self.tokenizer(query))
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        if metadata_filter:
            ranked = [
                (index, score)
                for index, score in ranked
                if all(self._documents[index].metadata.get(key) == value
                       for key, value in metadata_filter.items())
            ]
        ranked = ranked[:top_k]
        return [
            SearchResult(
                id=self._documents[i].id,
                text=self._documents[i].text,
                score=float(score),
                metadata=self._documents[i].metadata,
            )
            for i, score in ranked
        ]


# —— 向量（Chroma）——
def _clean_metadata(meta: dict[str, Any] | None) -> dict[str, Any] | None:
    """Chroma 不接受空 dict 与 None 值，过滤后返回。"""
    if not meta:
        return None
    cleaned = {k: v for k, v in meta.items() if v is not None}
    return cleaned or None


class VectorRetriever:
    """向量召回：Embedder + Chroma collection（collection 由工厂创建，便于插拔）。"""

    def __init__(self, embedder, collection) -> None:
        self.embedder = embedder
        self.collection = collection

    def index(self, documents: list[Document]) -> None:
        if not documents:
            return
        self.collection.add(
            ids=[d.id for d in documents],
            embeddings=self.embedder.embed_documents([d.text for d in documents]),
            documents=[d.text for d in documents],
            metadatas=[_clean_metadata(d.metadata) for d in documents],
        )

    def retrieve(
        self, query: str, top_k: int, metadata_filter: dict[str, Any] | None = None
    ) -> list[SearchResult]:
        if top_k <= 0:
            return []
        result = self.collection.query(
            query_embeddings=[self.embedder.embed_query(query)],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
            **({"where": metadata_filter} if metadata_filter else {}),
        )
        ids = result.get("ids") or [[]]
        docs = result.get("documents") or [[]]
        metas = result.get("metadatas") or [[]]
        distances = result.get("distances") or [[]]
        return [
            SearchResult(
                id=ids[0][i],
                text=docs[0][i],
                score=1.0 - float(distances[0][i]),  # cosine 距离 → 相似度
                metadata=metas[0][i] or {},
            )
            for i in range(len(ids[0]))
        ]


def build_chroma_collection(persist_dir: str, name: str):
    """创建/获取 Chroma collection（cosine 度量）。persist_dir 为空则用内存模式。"""
    import chromadb

    client = chromadb.PersistentClient(path=persist_dir) if persist_dir else chromadb.Client()
    return client.get_or_create_collection(name=name, metadata={"hnsw:space": "cosine"})


# —— RRF 融合 ——
def rrf_fuse(result_sets: list[list[SearchResult]], k: int = 60) -> list[SearchResult]:
    """Reciprocal Rank Fusion：多路召回按 id 去重、分数累加，降序返回。"""
    fused_scores: dict[str, float] = {}
    fused_by_id: dict[str, SearchResult] = {}
    for results in result_sets:
        for rank, result in enumerate(results):
            fused_scores[result.id] = fused_scores.get(result.id, 0.0) + 1.0 / (k + rank + 1)
            fused_by_id[result.id] = result
    merged = [replace(result, score=fused_scores[result.id]) for result in fused_by_id.values()]
    merged.sort(key=lambda r: r.score, reverse=True)
    return merged


class HybridRetrieval:
    """统一检索：多路召回 + RRF 融合 + 重排（供 RAG / GraphRAG 复用）。"""

    def __init__(
        self, retrievers: list[Retriever] | None = None, reranker=None, rrf_k: int = 60
    ) -> None:
        self.retrievers = retrievers or []
        self.reranker = reranker
        self.rrf_k = rrf_k

    def index(self, documents: list[Document]) -> None:
        """入库：委托给支持 index 的召回器（BM25 + 向量）。"""
        for retriever in self.retrievers:
            if isinstance(retriever, BM25Retriever):
                retriever.add_documents(documents)
            elif hasattr(retriever, "index"):
                retriever.index(documents)

    def retrieve(
        self, query: str, top_k: int, metadata_filter: dict[str, Any] | None = None
    ) -> list[SearchResult]:
        """多路召回并 RRF 融合。"""
        if not self.retrievers:
            return []
        per_retriever = []
        for retriever in self.retrievers:
            # 保持第三方/测试 Retriever 的旧两参数接口可用；即使底层不支持 where，
            # 仍在融合前二次过滤，租户边界不能依赖某一个实现。
            if metadata_filter:
                try:
                    results = retriever.retrieve(query, top_k, metadata_filter=metadata_filter)
                except TypeError:
                    results = retriever.retrieve(query, top_k)
                results = [
                    result
                    for result in results
                    if all(
                        result.metadata.get(key) == value
                        for key, value in metadata_filter.items()
                    )
                ]
            else:
                results = retriever.retrieve(query, top_k)
            per_retriever.append(results)
        return rrf_fuse(per_retriever, k=self.rrf_k)[:top_k]

    def rerank(
        self, query: str, candidates: list[SearchResult], top_k: int
    ) -> list[SearchResult]:
        """重排候选；无 reranker 时原样截断。"""
        if self.reranker is None:
            return candidates[:top_k]
        return self.reranker.rerank(query, candidates, top_k)
