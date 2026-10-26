"""决策层：意图识别 + 能力路由 + 降级链 + 意图漂移处理（纯函数，便于单测）。

阶段 2 用关键词规则做意图识别（Mock），接口预留替换为 LLM structured output；
意图漂移按 PRD BR-010 顺序判定，见 decide_active_flow。
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol

from app.agent.state import Intent
from app.capabilities.workflow.slot_filling import (
    Correction,
    CorrectionAction,
    SlotDecision,
    decide,
    recognize_correction,
)

# 意图 → 触发关键词（阶段 1 的 few-shot 素材；后续替换为 LLM 分类器）
INTENT_KEYWORDS: dict[Intent, tuple[str, ...]] = {
    Intent.WORKFLOW: (
        "办理", "修改", "退货", "换货", "退款", "改地址", "地址", "查快递", "快递",
        "查物流", "物流", "单号", "售后",
    ),
    Intent.GRAPHRAG: ("关系", "品牌", "同类", "包含", "关联", "分类", "属性", "哪些", "对比"),
    Intent.RAG: ("政策", "规则", "怎么", "如何", "多久", "条件", "要求", "退换货", "运费", "流程"),
    Intent.CHITCHAT: ("你好", "您好", "hi", "hello", "在吗", "谢谢", "再见"),
}

_ADVISORY_MARKERS = ("条件", "准备什么", "准备哪些", "需要什么", "是否", "能不能")
_REASONING_MARKERS = ("对比", "分析", "为什么", "争议", "投诉", "例外", "方案", "同时", "并且")
_UNSAFE_REQUEST_MARKERS = (
    "忽略之前", "忽略所有", "系统提示", "system prompt", "越权", "其他租户",
    "别人的订单", "执行 shell", "执行命令", "运行命令",
)


def is_unsafe_request(text: str) -> bool:
    """识别明显的越权、提示注入或不可信工具执行请求。

    这不是用关键词替代完整安全系统；它是在能力路由前阻断高风险显式表达，
    防止业务关键词（如“订单”）抢先将请求送入工具工作流。
    """
    normalized = (text or "").strip().lower()
    return any(marker in normalized for marker in _UNSAFE_REQUEST_MARKERS)


def is_advisory_request(text: str) -> bool:
    """判断是否为规则/材料咨询，而非明确要求立即执行业务动作。"""
    normalized = (text or "").strip().lower()
    return any(marker in normalized for marker in _ADVISORY_MARKERS)


def response_tier(text: str, intent: Intent) -> str:
    """按风险和复杂度选择模型；默认 Flash，复杂问题才支付 Pro 的延迟。"""
    normalized = (text or "").lower()
    if intent == Intent.GRAPHRAG or any(marker in normalized for marker in _REASONING_MARKERS):
        return "reasoning"
    return "fast"

# 四级降级链：workflow → rag → graphrag →（fallback 由 route 兜底）
DEGRADATION_CHAIN: tuple[str, ...] = ("workflow", "rag", "graphrag")

# 兜底与闲聊话术（阶段 1 响应模板）
FALLBACK_REPLY = "抱歉，我暂时无法处理您的问题，请稍后再试或转人工客服。"
CHITCHAT_REPLY = "您好！我是快递企业智能客服，请问有什么可以帮您？"


def classify_intent(text: str) -> tuple[Intent, float]:
    """识别输入意图，返回 `(意图, 置信度)`。

    阶段 2：按关键词命中数评分取最高（并列时按枚举定义顺序优先）；
    后续替换为 LLM structured output。
    """
    if not text or not text.strip():
        return Intent.FALLBACK, 0.0

    normalized = text.strip().lower()
    if is_unsafe_request(normalized):
        return Intent.FALLBACK, 0.95
    # “我要办理”与“我想了解是否能办理”不是一回事。后者由客服模型解释规则，
    # 不应抢先启动表单式工作流。
    if is_advisory_request(normalized):
        return Intent.FALLBACK, 0.85
    best_intent = Intent.FALLBACK
    best_hits = 0

    for intent, keywords in INTENT_KEYWORDS.items():
        hits = [kw for kw in keywords if kw.lower() in normalized]
        if len(hits) > best_hits:
            best_intent, best_hits = intent, len(hits)

    if best_hits == 0:
        return Intent.FALLBACK, 0.3

    # 命中越多，置信度越高（上限 0.95）
    confidence = min(0.6 + 0.1 * best_hits, 0.95)
    return best_intent, confidence


# —— 意图漂移处理（PRD BR-010）——


class TurnAction(StrEnum):
    """活跃流程下，单轮输入的处理动作。"""

    FILL = "fill"            # 正常填槽
    REPROMPT = "reprompt"    # 值非法，重填
    CORRECT = "correct"      # 槽位纠错（含重新/跳过）
    INSERT = "insert"        # 轻量问题：插入处理，不改变流程栈
    INTERRUPT = "interrupt"  # 新业务流程：压栈中断
    CANCEL = "cancel"        # 明确取消：结束当前流程


@dataclass
class TurnDecision:
    """活跃流程下对单轮输入的判定结果。"""

    action: TurnAction
    correction: Correction | None = None  # CORRECT 时的纠错对象
    new_flow_id: str | None = None        # INTERRUPT 时的目标流程


# 问题式输入标记（用于判断"非槽位合法值"的漂移）
_QUESTION_MARKERS = ("什么", "怎么", "如何", "为什么", "哪", "多少", "能不能", "可以吗", "有没有")


def looks_like_question(text: str) -> bool:
    """输入是否看起来像问题（而非槽位值）。"""
    t = (text or "").strip()
    if not t:
        return False
    if t.endswith(("？", "?", "吗")):
        return True
    return any(marker in t for marker in _QUESTION_MARKERS)


def decide_active_flow(
    user_input: str,
    validate_rule: str | None,
    new_flow_id: str | None,
) -> TurnDecision:
    """PRD BR-010：活跃流程下，判定本轮输入的处理动作。

    顺序：1) 纠正/否定信号 → 纠错；2) 当前槽位合法值 → 填槽；
    3) 否则识别为新意图：新业务流程 → 中断；其余 → 轻量问题插入。
    """
    # 1) 纠正/否定信号（"不对/改成/重新/跳过/取消"等）
    correction = recognize_correction(user_input)
    if correction is not None:
        if correction.action == CorrectionAction.CANCEL:
            return TurnDecision(TurnAction.CANCEL, correction=correction)
        return TurnDecision(TurnAction.CORRECT, correction=correction)

    # 2) 当前槽位的合法值（非新流程触发、非问题式输入）
    if new_flow_id is None and not looks_like_question(user_input):
        slot = decide(user_input, validate_rule)
        if slot == SlotDecision.ACCEPT:
            return TurnDecision(TurnAction.FILL)
        if slot == SlotDecision.INVALID:
            return TurnDecision(TurnAction.REPROMPT)

    # 3) 漂移：新意图分类
    if new_flow_id is not None:
        return TurnDecision(TurnAction.INTERRUPT, new_flow_id=new_flow_id)
    return TurnDecision(TurnAction.INSERT)


# —— 意图路由（LLM 输出意图类型 + 置信度）——


@dataclass
class IntentDecision:
    """意图路由结果。"""

    intent: Intent
    confidence: float


class IntentRouter(Protocol):
    """意图路由接口（可插拔：关键词 / LLM structured output）。"""

    def route(self, query: str, history: str = "") -> IntentDecision: ...


class KeywordIntentRouter:
    """关键词意图路由（阶段 2 Mock；阶段后续换 LLM structured output）。"""

    def route(self, query: str, history: str = "") -> IntentDecision:
        intent, confidence = classify_intent(query)
        return IntentDecision(intent=intent, confidence=confidence)


class LLMIntentRouter:
    """LLM 意图路由（DeepSeek，JSON 输出）。"""

    _PROMPT = (
        "你是智能客服的意图分类器，把用户输入分类为以下意图之一并给出置信度(0~1)：\n"
        "- workflow：多轮业务办理（退货/改地址/查快递等）\n"
        "- rag：知识问答（政策/规则/怎么/如何等）\n"
        "- graphrag：图谱关联问答（品牌/分类/属性/关系等）\n"
        "- chitchat：闲聊\n"
        "- fallback：兜底\n"
        '只输出 JSON，格式：{{"intent": "<类型>", "confidence": <0~1>}}\n'
        "最近对话（没有则为无）：{history}\n"
        "用户输入：{query}"
    )

    def __init__(self) -> None:
        self._model = None

    def _load(self):
        if self._model is None:
            from app.llm import get_fast_model

            self._model = get_fast_model()
        return self._model

    def route(self, query: str, history: str = "") -> IntentDecision:
        from app.llm import extract_json

        if is_advisory_request(query):
            return IntentDecision(intent=Intent.FALLBACK, confidence=0.85)
        # 高频、无歧义表达不值得先花一次远程 LLM 往返做分类。
        # 这条快速路径直接降低真实 SSE 的首 token 延迟；复杂表达才交给模型判断。
        rule_intent, rule_confidence = classify_intent(query)
        if rule_intent != Intent.FALLBACK and rule_confidence >= 0.7:
            return IntentDecision(intent=rule_intent, confidence=rule_confidence)
        try:
            content = self._load().invoke(
                self._PROMPT.format(query=query, history=history or "无")
            ).content
            data = extract_json(content)
            return IntentDecision(
                intent=Intent(data["intent"]), confidence=float(data["confidence"])
            )
        except Exception:
            # LLM 暂时不可用时，客服仍应能处理常见业务，不把异常暴露给用户。
            return KeywordIntentRouter().route(query)


# —— 降级链（FallbackChain）——


@dataclass
class CapabilityResult:
    """能力执行结果。"""

    success: bool
    text: str = ""
    score: float = 1.0  # 相似度/置信度；低于阈值视为失败
    citations: list[str] = field(default_factory=list)
    error: str | None = None
    state_updates: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChainOutcome:
    """降级链最终结果。"""

    text: str
    level: str  # 最终成功级别或 "fallback"
    degradation_path: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    actions: int = 0
    state_updates: dict[str, Any] = field(default_factory=dict)


class DegradationObserver:
    """降级可观测：记录降级原因与路径到日志与指标。"""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.logger = logger or logging.getLogger("stacklang.degradation")
        self.records: list[dict[str, str]] = []  # 内存指标（监控/测试读取）

    def record(self, level: str, reason: str, query: str) -> None:
        self.logger.warning("降级 level=%s reason=%s query=%s", level, reason, query)
        self.records.append({"level": level, "reason": reason, "query": query})

    def count(self, level: str | None = None) -> int:
        if level is None:
            return len(self.records)
        return sum(1 for r in self.records if r["level"] == level)


class FallbackChain:
    """四级降级链：workflow → rag → graphrag → fallback。

    route 决策当前级 → execute 执行该级；失败（异常/无结果/低于阈值）记录原因
    并决策下一级；guard 按动作计数上限防死循环；最终兜底保证任意输入有响应。
    """

    def __init__(
        self,
        capabilities: dict[str, Callable[[str, dict], CapabilityResult]],
        *,
        max_actions: int = 8,
        score_threshold: float = 0.0,
        observer: DegradationObserver | None = None,
    ) -> None:
        self.capabilities = capabilities
        self.max_actions = max_actions
        self.score_threshold = score_threshold
        self.observer = observer or DegradationObserver()

    def run(self, query: str, intent: Intent, context: dict | None = None) -> ChainOutcome:
        context = context or {}
        if intent == Intent.CHITCHAT:
            return ChainOutcome(text=CHITCHAT_REPLY, level="chitchat")

        path: list[str] = []
        reasons: list[str] = []
        actions = 0
        for level in self._levels_from(intent):
            if actions >= self.max_actions:
                break  # guard：防死循环
            actions += 1
            result = self._execute(level, query, context)
            if result.success and result.score >= self.score_threshold:
                return ChainOutcome(
                    text=result.text,
                    level=level,
                    degradation_path=path,
                    reasons=reasons,
                    actions=actions,
                    state_updates=result.state_updates,
                )
            reason = result.error or "无结果或低于阈值"
            path.append(level)
            reasons.append(reason)
            self.observer.record(level, reason, query)

        # 兜底：保证任意输入有响应
        self.observer.record("fallback", "降级链耗尽", query)
        return ChainOutcome(
            text=FALLBACK_REPLY,
            level="fallback",
            degradation_path=path,
            reasons=reasons,
            actions=actions,
        )

    def _levels_from(self, intent: Intent) -> list[str]:
        if intent in (Intent.CHITCHAT, Intent.FALLBACK):
            return []
        try:
            start = DEGRADATION_CHAIN.index(intent.value)
        except ValueError:
            start = 0
        return list(DEGRADATION_CHAIN[start:])

    def _execute(self, level: str, query: str, context: dict) -> CapabilityResult:
        fn = self.capabilities.get(level)
        if fn is None:
            return CapabilityResult(success=False, error=f"未知能力: {level}")
        return fn(query, context)
