"""Context Engineering：按优先级选择上下文，并给工具输出设置硬预算。"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ContextItem:
    source: str
    content: str
    priority: int = 0


@dataclass
class ContextWindow:
    text: str
    included: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)
    used_chars: int = 0


class ContextBuilder:
    """可确定性的字符预算器。

    生产环可将字符估算替换为供应商 tokenizer；本实现离线可运行、便于单测。
    """

    def __init__(self, max_chars: int = 4_000, max_item_chars: int = 1_200) -> None:
        if max_chars <= 0 or max_item_chars <= 0:
            raise ValueError("上下文预算必须为正数")
        self.max_chars = max_chars
        self.max_item_chars = max_item_chars

    def build(self, items: list[ContextItem]) -> ContextWindow:
        selected: list[str] = []
        included: list[str] = []
        dropped: list[str] = []
        used = 0
        ordered = sorted(enumerate(items), key=lambda pair: (-pair[1].priority, pair[0]))
        for _, item in ordered:
            content = item.content.strip()
            if len(content) > self.max_item_chars:
                content = content[: self.max_item_chars] + "…[truncated]"
            block = f"[{item.source}]\n{content}"
            separator = 2 if selected else 0
            if used + separator + len(block) > self.max_chars:
                dropped.append(item.source)
                continue
            selected.append(block)
            included.append(item.source)
            used += separator + len(block)
        return ContextWindow("\n\n".join(selected) or "无", included, dropped, used)
