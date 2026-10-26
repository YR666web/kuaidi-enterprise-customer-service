"""文档处理流水线：解析 → 语义切分 → 向量化入库。"""

from pathlib import Path

from app.capabilities.rag.chunker import SemanticChunker
from app.capabilities.rag.loader import load
from app.retrieval.hybrid import Document, HybridRetrieval


class RagPipeline:
    """解析 + 切分 + 入库（BM25 + 向量，经 HybridRetrieval 统一入库）。"""

    def __init__(self, hybrid: HybridRetrieval, chunker: SemanticChunker | None = None) -> None:
        self.hybrid = hybrid
        self.chunker = chunker or SemanticChunker()

    def ingest(
        self, path: str, doc_id: str | None = None, tenant_id: str = "default"
    ) -> list[Document]:
        """解析文档并切分入库；返回 chunk（带 doc_id/页码/片段 metadata）。"""
        doc_id = doc_id or Path(path).stem
        chunks: list[Document] = []
        index = 0
        for section in load(path):
            for text in self.chunker.split(section.text):
                chunks.append(Document(
                    id=f"{doc_id}#{index}",
                    text=text,
                    metadata={
                        "doc_id": doc_id,
                        "tenant_id": tenant_id,
                        "page": section.page,
                        "index": index,
                    },
                ))
                index += 1
        self.hybrid.index(chunks)
        return chunks
