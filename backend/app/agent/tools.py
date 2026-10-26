"""AI 工具层：显式 schema、白名单注册、参数校验与统一错误边界。"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Any] = field(repr=False, compare=False)


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    output: Any = None
    error: str | None = None


class ToolRegistry:
    """只能执行显式注册的函数，不使用 eval/动态导入。"""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if not spec.name or spec.name in self._tools:
            raise ValueError(f"工具名为空或重复: {spec.name}")
        if spec.parameters.get("type") != "object":
            raise ValueError("工具 parameters 顶层必须是 object")
        self._tools[spec.name] = spec

    def schemas(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": spec.parameters,
                },
            }
            for spec in self._tools.values()
        ]

    def execute(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        spec = self._tools.get(name)
        if spec is None:
            return ToolResult(False, error=f"未授权工具: {name}")
        error = _validate(arguments, spec.parameters)
        if error:
            return ToolResult(False, error=error)
        try:
            return ToolResult(True, output=spec.handler(**arguments))
        except Exception as exc:
            return ToolResult(False, error=f"{type(exc).__name__}: {exc}")


def _validate(arguments: dict[str, Any], schema: dict[str, Any]) -> str | None:
    if not isinstance(arguments, dict):
        return "工具参数必须是 JSON object"
    properties = schema.get("properties", {})
    for key in schema.get("required", []):
        if key not in arguments:
            return f"缺少必填参数: {key}"
    if schema.get("additionalProperties") is False:
        unknown = sorted(set(arguments) - set(properties))
        if unknown:
            return f"未知参数: {', '.join(unknown)}"
    python_types = {"string": str, "integer": int, "number": (int, float), "boolean": bool}
    for key, value in arguments.items():
        property_schema = properties.get(key, {})
        expected = property_schema.get("type")
        expected_type = python_types.get(expected)
        wrong_type = expected_type and not isinstance(value, expected_type)
        bool_is_not_integer = expected == "integer" and isinstance(value, bool)
        if wrong_type or bool_is_not_integer:
            return f"参数 {key} 应为 {expected}"
        if isinstance(value, str):
            if len(value) < property_schema.get("minLength", 0):
                return f"参数 {key} 长度不足"
            if len(value) > property_schema.get("maxLength", float("inf")):
                return f"参数 {key} 过长"
    return None
