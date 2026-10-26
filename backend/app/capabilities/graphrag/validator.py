"""Cypher 校验：EXPLAIN 语法 + 逻辑（LLM），供自校正使用。"""

import re
from typing import Protocol

from app.capabilities.graphrag.executor import GraphDriver


class LogicChecker(Protocol):
    """逻辑校验接口（可插拔：Mock / LLM）。"""

    def check(self, cypher: str) -> tuple[bool, str | None]: ...


class CypherValidator:
    """校验 Cypher：先 EXPLAIN 语法校验，再逻辑校验。"""

    def __init__(self, driver: GraphDriver, logic_checker: LogicChecker | None = None) -> None:
        self.driver = driver
        self.logic_checker = logic_checker

    def validate(self, cypher: str) -> tuple[bool, str | None]:
        parameters = set(re.findall(r"\$([A-Za-z_]\w*)", cypher))
        unsupported = sorted(parameters - {"user_id"})
        if unsupported:
            return False, (
                "存在未绑定参数: " + ", ".join(f"${name}" for name in unsupported)
                + "。领域过滤值请使用 Cypher 字符串字面量；仅 $user_id 允许作为运行时参数。"
            )
        try:
            self.driver.explain(cypher)
        except Exception as exc:
            return False, f"语法错误: {exc}"
        if self.logic_checker is not None:
            return self.logic_checker.check(cypher)
        return True, None
