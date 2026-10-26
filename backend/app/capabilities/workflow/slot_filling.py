"""槽位填充：强制单槽填充 + 槽位纠错。

收集期只接受当前槽位的合法值；丢弃越界（非法）槽位与漂移/新流程启动信号。
纠错：识别纠错信号（不对/改成/重新/跳过/取消），定位目标槽位，仅更新目标槽位。
"""

import re
from dataclasses import dataclass
from enum import StrEnum


class SlotDecision(StrEnum):
    ACCEPT = "accept"    # 当前槽位的合法值，接受
    INVALID = "invalid"  # 值非法（越界/格式错误），丢弃并要求重填
    DRIFT = "drift"      # 漂移/新流程启动信号，丢弃


class CorrectionAction(StrEnum):
    CORRECT = "correct"  # 纠正：用新值覆盖目标槽位
    REWIND = "rewind"    # 重新：清空目标槽位并回到该槽位重填
    SKIP = "skip"        # 跳过：跳过当前（可选）槽位
    CANCEL = "cancel"    # 取消：终止当前流程


@dataclass
class Correction:
    """纠错意图。rest 为去掉信号词后的剩余文本（供提取纠正值）。"""

    action: CorrectionAction
    rest: str = ""


# 纠错信号（"换一个/先不"等残留信号仍走漂移）
CORRECTION_KEYWORDS: dict[CorrectionAction, tuple[str, ...]] = {
    CorrectionAction.CORRECT: (
        "不对", "不是这个", "不是", "改成", "换成", "应该是", "错了", "写错了", "填错了",
    ),
    CorrectionAction.REWIND: ("重新", "重填", "重来", "再来一遍"),
    CorrectionAction.SKIP: ("跳过", "略过", "不用填", "不填"),
    CorrectionAction.CANCEL: ("取消", "不弄了", "算了", "不办了", "退出", "不做了", "不用了"),
}

_ACTION_ORDER: tuple[CorrectionAction, ...] = (
    CorrectionAction.CORRECT,
    CorrectionAction.REWIND,
    CorrectionAction.SKIP,
    CorrectionAction.CANCEL,
)

# 漂移/中断关键词（残留的"换一种说法"类信号；新流程触发由 executor 的 match_flow 处理）
DRIFT_KEYWORDS = ("先不", "换一个", "等等", "先帮我")

_EDGE_CHARS = " ，。,:：、!！?？"

# 价值引入词（"是/改成/换成/应该是/为"）
_VALUE_MARKERS = ("改成", "换成", "应该是", "应为", "是", "为")

_PHONE_RE = re.compile(r"^1[3-9]\d{9}$")

# 所有纠错关键词（长度降序，去除时避免"不是"截断"不是这个"）
_ALL_CORRECTION_KEYWORDS: tuple[str, ...] = tuple(
    sorted((kw for kws in CORRECTION_KEYWORDS.values() for kw in kws), key=len, reverse=True)
)


def is_drift(text: str) -> bool:
    """检测漂移/新流程启动信号。"""
    return any(kw in text for kw in DRIFT_KEYWORDS)


def validate_value(value: str, rule: str | None) -> bool:
    """按规则校验槽位值；rule 为空表示仅要求非空。"""
    value = (value or "").strip()
    if not value:
        return False
    if rule == "phone":
        return bool(_PHONE_RE.match(value))
    if rule == "name":
        return 2 <= len(value) <= 20 and not any(ch.isdigit() for ch in value)
    if rule == "address":
        return len(value) >= 5
    if rule and rule.startswith("regex:"):
        return bool(re.fullmatch(rule[len("regex:"):], value))
    return True


def decide(user_input: str, validate_rule: str | None = None) -> SlotDecision:
    """判定输入应如何处理（单槽填充的核心决策）。"""
    text = (user_input or "").strip()
    if not text:
        return SlotDecision.INVALID
    if is_drift(text):
        return SlotDecision.DRIFT
    if not validate_value(text, validate_rule):
        return SlotDecision.INVALID
    return SlotDecision.ACCEPT


# —— 纠错 ——
def recognize_correction(text: str) -> Correction | None:
    """识别纠错信号，返回 Correction；无信号返回 None。"""
    text = (text or "").strip()
    if not text:
        return None
    for action in _ACTION_ORDER:
        if any(kw in text for kw in CORRECTION_KEYWORDS[action]):
            rest = _remove_keywords(text)
            return Correction(action=action, rest=_strip_edges(rest))
    return None


def _remove_keywords(text: str) -> str:
    cleaned = text
    for kw in _ALL_CORRECTION_KEYWORDS:
        cleaned = cleaned.replace(kw, " ")
    return cleaned


def _strip_edges(text: str) -> str:
    return text.strip(_EDGE_CHARS)


def locate_slot(
    text: str,
    slot_aliases: dict[str, list[str]],
    fallback_slot: str | None,
) -> str | None:
    """定位纠错目标槽位：优先用户提及的字段名，否则用 fallback（最近填充/当前槽位）。"""
    for slot, aliases in slot_aliases.items():
        for alias in aliases:
            if alias and alias in text:
                return slot
    return fallback_slot


def extract_value(rest: str, aliases: list[str] | None = None) -> str | None:
    """从纠错剩余文本中提取纠正值（去掉字段别名与价值引入词）。"""
    value = _strip_edges(rest or "")
    for alias in (aliases or []):
        if alias and value.startswith(alias):
            value = _strip_edges(value[len(alias):])
            break
    for marker in _VALUE_MARKERS:
        if value.startswith(marker):
            value = _strip_edges(value[len(marker):])
            break
    return value or None
