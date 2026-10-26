"""DialogueStack 对话栈（LIFO）：流程嵌套、中断、恢复。

栈帧 FlowFrame 携带每个流程独立的执行位置（current_step）与槽位（slots）。
栈整体可序列化为 list[dict]，经 LangGraph checkpoint 持久化。
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FlowFrame:
    """单个流程的执行帧。"""

    flow_id: str
    current_step: str | None = None  # None 表示尚未开始
    slots: dict[str, Any] = field(default_factory=dict)
    last_slot: str | None = None  # 最近一次填充/纠正的槽位（纠错默认定位目标）

    def to_dict(self) -> dict[str, Any]:
        return {
            "flow_id": self.flow_id,
            "current_step": self.current_step,
            "slots": self.slots,
            "last_slot": self.last_slot,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FlowFrame":
        return cls(
            flow_id=data["flow_id"],
            current_step=data.get("current_step"),
            slots=dict(data.get("slots", {})),
            last_slot=data.get("last_slot"),
        )


class DialogueStack:
    """LIFO 对话栈，管理流程嵌套/中断/恢复。"""

    def __init__(self, frames: list[FlowFrame] | None = None) -> None:
        self._frames = frames or []

    def push_flow(self, flow_id: str) -> FlowFrame:
        """压入新流程（中断当前流程），返回新帧。"""
        frame = FlowFrame(flow_id=flow_id)
        self._frames.append(frame)
        return frame

    def pop_flow(self) -> FlowFrame | None:
        """弹出栈顶流程（结束当前流程，恢复上一层）。"""
        return self._frames.pop() if self._frames else None

    def pop_to_flow(self, flow_id: str) -> bool:
        """弹回指定流程：弹出直到栈顶为 flow_id；找不到返回 False。"""
        for i in range(len(self._frames) - 1, -1, -1):
            if self._frames[i].flow_id == flow_id:
                del self._frames[i + 1:]
                return True
        return False

    def top(self) -> FlowFrame | None:
        return self._frames[-1] if self._frames else None

    def is_empty(self) -> bool:
        return not self._frames

    def __len__(self) -> int:
        return len(self._frames)

    def to_list(self) -> list[dict[str, Any]]:
        """序列化为 list[dict]（用于写入 LangGraph state 持久化）。"""
        return [frame.to_dict() for frame in self._frames]

    @classmethod
    def from_list(cls, data: list[dict[str, Any]] | None) -> "DialogueStack":
        """从序列化数据恢复。"""
        return cls([FlowFrame.from_dict(item) for item in (data or [])])
