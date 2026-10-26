"""向量化：Embedder 接口 + bge-base-zh-v1.5 本地实现。

- query 侧加检索前缀（bge 指令），文档侧不加前缀；
- 输出归一化，配合 cosine 度量；
- 本地 models/ 缓存加载，不联网（local_files_only）。
"""

from typing import Protocol


class Embedder(Protocol):
    """向量化接口（可插拔）。"""

    def embed_query(self, text: str) -> list[float]: ...

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...


class SentenceTransformerEmbedder:
    """sentence-transformers 加载本地 bge-base-zh-v1.5。"""

    def __init__(
        self,
        model_name: str,
        cache_dir: str,
        device: str = "cpu",
        query_prefix: str = "",
        *,
        model=None,  # 可注入（测试用假模型）
    ) -> None:
        self.model_name = model_name
        self.cache_dir = cache_dir
        self.device = device
        self.query_prefix = query_prefix
        self._model = model

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(
                self.model_name,
                device=self.device,
                cache_folder=self.cache_dir,
                local_files_only=True,  # 本地缓存，不联网
                similarity_fn_name="cosine",
            )
        return self._model

    def embed_query(self, text: str) -> list[float]:
        model = self._load()
        vec = model.encode([self.query_prefix + text], normalize_embeddings=True)
        return [float(x) for x in vec[0]]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        model = self._load()
        vec = model.encode(list(texts), normalize_embeddings=True)
        return [[float(x) for x in v] for v in vec]
