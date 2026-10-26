"""Flow 声明式流程模型 + YAML 加载。

流程用 YAML 定义（见 data/flows/*.yaml），新增流程不改框架代码。
步骤类型：action / collect / set_slot / condition / link。
"""

import os
from dataclasses import dataclass, field
from typing import Any, Literal

import yaml

StepType = Literal["action", "collect", "set_slot", "condition", "link"]

_STEP_TYPES: frozenset[str] = frozenset({"action", "collect", "set_slot", "condition", "link"})


@dataclass
class FlowStep:
    """流程中的单个步骤，按 `type` 使用不同字段。"""

    id: str
    type: StepType
    # action
    action: str | None = None
    # collect
    slot: str | None = None
    prompt: str | None = None
    validate: str | None = None
    aliases: list[str] = field(default_factory=list)  # 字段别名（纠错定位）
    optional: bool = False  # 是否可选（可跳过）
    # set_slot
    value: Any = None
    # condition
    condition: str | None = None
    then: str | None = None
    else_: str | None = None
    # link
    target: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FlowStep":
        step_type = data.get("type")
        if step_type not in _STEP_TYPES:
            raise ValueError(f"未知步骤类型: {step_type}（步骤 {data.get('id')}）")
        step = cls(
            id=data["id"],
            type=step_type,
            action=data.get("action"),
            slot=data.get("slot"),
            prompt=data.get("prompt"),
            validate=data.get("validate"),
            aliases=data.get("aliases", []),
            optional=data.get("optional", False),
            value=data.get("value"),
            condition=data.get("condition"),
            then=data.get("then"),
            else_=data.get("else"),
            target=data.get("target"),
        )
        step._validate()
        return step

    def _validate(self) -> None:
        if self.type == "action" and not self.action:
            raise ValueError(f"action 步骤 {self.id} 缺少 action 字段")
        if self.type in ("collect", "set_slot") and not self.slot:
            raise ValueError(f"{self.type} 步骤 {self.id} 缺少 slot 字段")
        if self.type == "condition" and not self.condition:
            raise ValueError(f"condition 步骤 {self.id} 缺少 condition 字段")
        if self.type == "link" and not self.target:
            raise ValueError(f"link 步骤 {self.id} 缺少 target 字段")


@dataclass
class Flow:
    """声明式业务流程。"""

    id: str
    name: str
    steps: list[FlowStep]
    triggers: list[str] = field(default_factory=list)

    def step_by_id(self, step_id: str) -> FlowStep | None:
        for step in self.steps:
            if step.id == step_id:
                return step
        return None

    def first_step(self) -> FlowStep | None:
        return self.steps[0] if self.steps else None

    def collect_steps(self) -> list[FlowStep]:
        """返回所有 collect 步骤（槽位集合）。"""
        return [s for s in self.steps if s.type == "collect"]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Flow":
        steps = [FlowStep.from_dict(s) for s in data.get("steps", [])]
        if not steps:
            raise ValueError(f"流程 {data.get('id')} 未定义任何步骤")
        return cls(
            id=data["id"],
            name=data.get("name", data["id"]),
            steps=steps,
            triggers=data.get("triggers", []),
        )


def load_flow(path: str) -> Flow:
    """从单个 YAML 文件加载流程。"""
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"流程文件格式错误（应为 YAML 映射）: {path}")
    return Flow.from_dict(data)


def load_flows(directory: str) -> dict[str, Flow]:
    """加载目录下所有 *.yaml 流程，返回 {flow_id: Flow}；目录不存在返回空。"""
    flows: dict[str, Flow] = {}
    if not os.path.isdir(directory):
        return flows
    for filename in sorted(os.listdir(directory)):
        if not filename.endswith((".yaml", ".yml")):
            continue
        flow = load_flow(os.path.join(directory, filename))
        flows[flow.id] = flow
    return flows


def match_flow(text: str, flows: dict[str, Flow]) -> Flow | None:
    """按 trigger 关键词匹配流程；返回第一个命中（无则 None）。"""
    normalized = (text or "").lower()
    for flow in flows.values():
        if any(trigger.lower() in normalized for trigger in flow.triggers):
            return flow
    return None
