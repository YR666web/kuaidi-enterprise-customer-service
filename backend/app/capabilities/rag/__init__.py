"""RAG 知识问答能力：文档入库 → 混合检索 → 重排 → 生成 + 引用溯源。"""

from dataclasses import dataclass

from app.capabilities.rag.chunker import SemanticChunker
from app.capabilities.rag.loader import ParsedSection, load, load_pdf, markdown_to_text
from app.capabilities.rag.pipeline import RagPipeline
from app.capabilities.rag.qa import (
    Answer,
    AnswerGenerator,
    LLMAnswerGenerator,
    MockAnswerGenerator,
    RagQA,
    Source,
)


@dataclass
class RagService:
    """RAG 能力：文档入库 + 问答，共享同一检索实例。"""

    pipeline: RagPipeline
    qa: RagQA


def build_rag_service(*, enable_rerank: bool = False) -> RagService:
    """按配置构建 RAG 服务（供接入层复用）。

    enable_rerank 默认关闭：bge-reranker-v2-m3 体积大、本地未缓存时避免下载；
    缓存后置 True 开启重排。
    """
    from app.core.config import settings
    from app.llm import has_llm
    from app.retrieval import build_hybrid_retrieval

    hybrid = build_hybrid_retrieval(enable_rerank=enable_rerank)
    chunker = SemanticChunker(settings.rag.chunk_size, settings.rag.chunk_overlap)
    pipeline = RagPipeline(hybrid, chunker)
    generator = LLMAnswerGenerator() if has_llm() else MockAnswerGenerator()
    qa = RagQA(
        hybrid,
        generator=generator,
        top_k=settings.rag.top_k,
        # 不重排时返回的是 RRF 融合分（量级很小），阈值设 0；重排后按 cosine/logit 校准
        score_threshold=0.0 if not enable_rerank else settings.rag.score_threshold,
        no_answer_reply=settings.rag.no_answer_reply,
    )
    return RagService(pipeline=pipeline, qa=qa)


__all__ = [
    "Answer",
    "AnswerGenerator",
    "MockAnswerGenerator",
    "ParsedSection",
    "RagPipeline",
    "RagQA",
    "RagService",
    "SemanticChunker",
    "Source",
    "build_rag_service",
    "load",
    "load_pdf",
    "markdown_to_text",
]
