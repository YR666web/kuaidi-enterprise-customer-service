"""重排：Reranker 接口 + bge-reranker-v2-m3 交叉编码实现。"""

from dataclasses import replace
from typing import Protocol

from app.retrieval.hybrid import SearchResult


class Reranker(Protocol):
    """重排接口（可插拔）。"""

    def rerank(
        self, query: str, candidates: list[SearchResult], top_k: int
    ) -> list[SearchResult]: ...


class BgeReranker:
    """bge-reranker-v2-m3 交叉编码重排（懒加载，需先缓存模型）。"""

    def __init__(self, model_name: str, device: str = "cpu", *, model=None) -> None:
        self.model_name = model_name
        self.device = device
        self._model = model  # 可注入（测试用假模型）

    def _load(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self.model_name, device=self.device)
        return self._model

    def rerank(
        self, query: str, candidates: list[SearchResult], top_k: int
    ) -> list[SearchResult]:
        if not candidates:
            return []
        model = self._load()
        pairs = [[query, c.text] for c in candidates]
        scores = model.predict(pairs)
        ranked = sorted(
            zip(candidates, scores, strict=True), key=lambda x: float(x[1]), reverse=True
        )
        return [replace(c, score=float(s)) for c, s in ranked[:top_k]]
