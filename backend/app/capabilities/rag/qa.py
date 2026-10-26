"""RAG 检索问答：检索 → 重排 → 阈值过滤 → 生成（含引用）。"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.retrieval.hybrid import HybridRetrieval, SearchResult


@dataclass
class Source:
    """答案引用来源（可定位到文档 + 片段）。"""

    doc_id: str
    snippet: str
    page: int | None = None
    index: int = 0


@dataclass
class Answer:
    """问答结果。"""

    text: str
    sources: list[Source] = field(default_factory=list)
    no_answer: bool = False


class AnswerGenerator(Protocol):
    """回答生成接口（可插拔：Mock / LLM）。"""

    def generate(self, question: str, contexts: list[SearchResult]) -> Answer: ...


class MockAnswerGenerator:
    """占位生成器：拼接上下文 + [N] 引用标注（阶段后续接 LLM）。"""

    def generate(self, question: str, contexts: list[SearchResult]) -> Answer:
        if not contexts:
            return Answer(text="", no_answer=True)
        citations = "".join(f"[{i + 1}]" for i in range(len(contexts)))
        body = f"针对「{question}」，综合资料{citations}：{contexts[0].text[:50]}……"
        sources = [
            Source(
                doc_id=c.metadata.get("doc_id", c.id),
                snippet=c.text,
                page=c.metadata.get("page"),
                index=c.metadata.get("index", i),
            )
            for i, c in enumerate(contexts)
        ]
        return Answer(text=body, sources=sources)


class LLMAnswerGenerator:
    """LLM 回答生成（DeepSeek）：基于上下文生成带 [n] 引用的回答。"""

    _PROMPT = (
        "你是智能客服，根据给定的资料回答用户问题。\n"
        "要求：引用资料时用 [n] 标注来源编号（n 为资料序号）。\n"
        "资料：\n{passages}\n"
        "问题：{question}\n"
        "回答："
    )

    def __init__(self) -> None:
        self._model = None

    def _load(self):
        if self._model is None:
            from app.llm import get_chat_model

            self._model = get_chat_model()
        return self._model

    def generate(self, question: str, contexts: list[SearchResult]) -> Answer:
        passages = self.passages(contexts)
        prompt = self._PROMPT.format(passages=passages, question=question)
        content = self._load().invoke(prompt).content
        sources = [
            Source(
                doc_id=c.metadata.get("doc_id", c.id),
                snippet=c.text,
                page=c.metadata.get("page"),
                index=c.metadata.get("index", i),
            )
            for i, c in enumerate(contexts)
        ]
        return Answer(text=content, sources=sources)

    @staticmethod
    def passages(contexts: list[SearchResult]) -> str:
        return "\n".join(f"[{i + 1}] {context.text}" for i, context in enumerate(contexts))

    def stream_generate(
        self, question: str, passages: str, *, config: dict[str, Any] | None = None
    ) -> Iterable[str]:
        """基于已检索资料逐 token 生成；callbacks 由 LangGraph astream_events 透传。"""
        prompt = self._PROMPT.format(passages=passages, question=question)
        for chunk in self._load().stream(prompt, config=config):
            text = str(chunk.content or "")
            if text:
                yield text


class RagQA:
    """RAG 问答：混合检索 + 重排 + 阈值 + 生成。"""

    def __init__(
        self,
        hybrid: HybridRetrieval,
        generator: AnswerGenerator | None = None,
        *,
        top_k: int = 4,
        score_threshold: float = 0.3,
        no_answer_reply: str = "抱歉，未在知识库中找到与您问题相关的答案。",
    ) -> None:
        self.hybrid = hybrid
        self.generator = generator or MockAnswerGenerator()
        self.top_k = top_k
        self.score_threshold = score_threshold
        self.no_answer_reply = no_answer_reply

    def answer(self, question: str, *, tenant_id: str | None = None) -> Answer:
        contexts = self.contexts(question, tenant_id=tenant_id)
        if contexts is None:
            return Answer(text=self.no_answer_reply, no_answer=True)
        return self.generator.generate(question, contexts)

    def contexts(self, question: str, *, tenant_id: str | None = None) -> list[SearchResult] | None:
        """仅执行受租户隔离保护的召回与重排，供流式答案节点复用。"""
        metadata_filter = {"tenant_id": tenant_id} if tenant_id else None
        candidates = self.hybrid.retrieve(
            question, top_k=self.top_k * 2, metadata_filter=metadata_filter
        )
        if not candidates:
            return None
        reranked = self.hybrid.rerank(question, candidates, top_k=self.top_k)
        # 低相似度 → 无答案（供降级链兜底）
        if not reranked or reranked[0].score < self.score_threshold:
            return None
        return reranked
