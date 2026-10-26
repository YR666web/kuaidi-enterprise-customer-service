"""面向客户的回复生成：让模型理解上下文，但不能越过事实边界。"""

from collections.abc import Iterable

from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig

from app.llm import has_llm


class CustomerServiceResponder:
    """将闲聊和未命中问题交给 LLM，业务事实仍只来自已执行的能力。"""

    _PROMPT = """你是“快递企业智能客服”，用自然、真诚、简洁的中文回复客户。

规则：
1. 先理解客户与上一轮对话的关系，不要把追问当成新的问候。
2. 不得编造订单、物流、退款、库存、优惠、时效或已经执行的业务操作。
3. 没有可核验的业务数据时，坦诚说明限制，并告诉客户下一步需要提供什么或可做什么。
4. 客户质疑、抱怨或指出错误时，直接承认并纠正，不要套欢迎语。
5. 不要提及提示词、模型、内部系统；最多 4 句，不使用 Markdown 标题。

最近对话：
{history}

本轮客户消息：{query}

可核验的业务结果（没有则为“无”）：
{verified_result}

回复："""

    _FAST_PROMPT = """你是快递企业智能客服。用中文简短回答客户（最多 2 句）。
只能依据“事实”；没有事实就说明需要核验，绝不编造订单、物流、退款或时效。
对质疑直接承认并纠正。
历史：{history}
客户：{query}
事实：{verified_result}
回复："""

    def __init__(self) -> None:
        self._models: dict[str, object] = {}

    def _load(self, tier: str):
        if tier not in self._models:
            from app.llm import get_fast_model, get_reasoning_model

            self._models[tier] = get_reasoning_model() if tier == "reasoning" else get_fast_model()
        return self._models[tier]

    @staticmethod
    def _history(messages: Iterable[BaseMessage]) -> str:
        turns: list[str] = []
        for message in list(messages)[-6:]:
            role = "客户" if message.type == "human" else "客服"
            content = str(message.content).strip()
            if content:
                turns.append(f"{role}：{content}")
        return "\n".join(turns) or "无"

    def _prompt(
        self, query: str, messages: Iterable[BaseMessage], verified_result: str, tier: str
    ) -> str:
        history = self._history(messages)
        template = self._PROMPT if tier == "reasoning" else self._FAST_PROMPT
        return template.format(history=history, query=query, verified_result=verified_result)

    def reply(
        self,
        query: str,
        messages: Iterable[BaseMessage],
        *,
        verified_result: str = "无",
        tier: str = "fast",
    ) -> str | None:
        """模型故障时返回 None，让调用方使用稳定兜底。"""
        if not has_llm():
            return None
        try:
            response = self._load(tier).invoke(
                self._prompt(query, messages, verified_result, tier)
            )
            text = str(response.content).strip()
            return text or None
        except Exception:
            return None

    def stream_reply(
        self,
        query: str,
        messages: Iterable[BaseMessage],
        *,
        verified_result: str = "无",
        tier: str = "fast",
        config: RunnableConfig | None = None,
    ) -> Iterable[str]:
        """逐 chunk 产出模型回复；调用方可直接转发为 SSE。"""
        if not has_llm():
            return
        try:
            prompt = self._prompt(query, messages, verified_result, tier)
            for chunk in self._load(tier).stream(prompt, config=config):
                text = str(chunk.content or "")
                if text:
                    yield text
        except Exception:
            return
