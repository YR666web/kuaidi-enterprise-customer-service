"""LLM 客户端：DeepSeek（OpenAI 兼容，经 langchain-openai）。"""

import json
import re

from langchain_openai import ChatOpenAI

from app.core.config import settings


def has_llm() -> bool:
    """是否已配置 LLM API key。"""
    return bool(settings.llm.api_key)


def _build_model(
    model: str,
    *,
    thinking: str,
    max_tokens: int,
    reasoning_effort: str | None = None,
) -> ChatOpenAI:
    if not settings.llm.api_key:
        raise RuntimeError("未配置 LLM__API_KEY，无法初始化 LLM")
    kwargs = {
        "model": model,
        "api_key": settings.llm.api_key,
        "base_url": settings.llm.base_url,
        "temperature": settings.llm.temperature,
        "max_tokens": max_tokens,
        # DeepSeek 的 thinking 是提供方扩展字段，须通过 OpenAI SDK 的 extra_body 透传。
        "extra_body": {"thinking": {"type": thinking}},
    }
    if reasoning_effort:
        kwargs["reasoning_effort"] = reasoning_effort
    return ChatOpenAI(**kwargs)


def get_fast_model() -> ChatOpenAI:
    """低延迟客服流：Flash + 禁用思考，适合闲聊、明确规则与工具结果解释。"""
    return _build_model(
        settings.llm.fast_model,
        thinking="disabled",
        max_tokens=settings.llm.fast_max_tokens,
    )


def get_reasoning_model() -> ChatOpenAI:
    """高质量推理流：V4 Pro，仅用于复杂推理、GraphRAG 与高风险判断。"""
    return _build_model(
        settings.llm.reasoning_model or settings.llm.model,
        thinking="enabled",
        max_tokens=settings.llm.reasoning_max_tokens,
        reasoning_effort=settings.llm.reasoning_effort,
    )


def get_chat_model() -> ChatOpenAI:
    """兼容旧调用：默认保持高质量推理模型。"""
    return get_reasoning_model()


def extract_json(text: str) -> dict:
    """从 LLM 输出中提取首个 JSON 对象（容错）。"""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"LLM 未输出有效 JSON: {text}")
    return json.loads(match.group(0))


def strip_code_fence(text: str) -> str:
    """去掉 LLM 输出中的 markdown 代码块围栏（```lang ... ```）。"""
    cleaned = text.strip()
    match = re.match(r"^```[^\n]*\n(.*?)\n?```\s*$", cleaned, re.DOTALL)
    if match:
        return match.group(1).strip()
    return cleaned
