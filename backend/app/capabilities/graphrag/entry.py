"""入口节点检索：用检索底座混合检索候选入口节点。"""

from app.retrieval.hybrid import HybridRetrieval, SearchResult


class EntryRetriever:
    """入口节点检索（向量 + 全文混合）。"""

    def __init__(self, hybrid: HybridRetrieval) -> None:
        self.hybrid = hybrid

    def retrieve(self, entity_text: str, top_k: int) -> list[SearchResult]:
        return self.hybrid.retrieve(entity_text, top_k)
