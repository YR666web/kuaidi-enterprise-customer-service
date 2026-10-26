"""Text2Cypher：基于 schema 生成 Cypher + 自校正闭环。"""

from typing import Protocol

from app.capabilities.graphrag.router import EntityRef, RouteResult
from app.capabilities.graphrag.schema import SCHEMA_DESCRIPTION, NodeType
from app.retrieval.hybrid import SearchResult


class CypherGenerator(Protocol):
    """Cypher 生成接口（可插拔：Mock / LLM）。"""

    def generate(
        self,
        query: str,
        node_types: list[NodeType],
        entities: list[EntityRef],
        entry_nodes: list[SearchResult],
        error: str | None = None,
    ) -> str: ...


class MockCypherGenerator:
    """占位：按主节点类型生成固定 Cypher（阶段后续接 LLM）。"""

    def generate(self, query, node_types, entities, entry_nodes, error=None):
        if NodeType.USER in node_types:
            return "MATCH (u:User {user_id: $user_id})-[:PURCHASED]->(s:SKU) RETURN s"
        if NodeType.TRADEMARK in node_types:
            return "MATCH (t:Trademark)-[:PRODUCES]->(spu:SPU) RETURN spu"
        if NodeType.CATEGORY in node_types:
            return "MATCH (c:Category)-[:CONTAINS]->(spu:SPU) RETURN spu"
        if NodeType.SPU in node_types:
            return "MATCH (spu:SPU) RETURN spu"
        return "MATCH (n) RETURN n LIMIT 10"


class LLMCypherGenerator:
    """LLM Cypher 生成（DeepSeek）：基于 schema 生成只读 Cypher。"""

    def __init__(self) -> None:
        self._model = None

    def _load(self):
        if self._model is None:
            from app.llm import get_chat_model

            self._model = get_chat_model()
        return self._model

    def generate(self, query, node_types, entities, entry_nodes, error=None):
        entities_text = "、".join(f"{e.node_type}:{e.value}" for e in entities) or "无"
        prompt = (
            "你是 Neo4j 专家，根据 schema 生成只读 Cypher"
            "（只用 MATCH/RETURN，不写数据）。"
            "颜色、容量、品类等领域过滤值必须直接写成经转义的 Cypher "
            "字符串字面量，不得创造未绑定参数。"
            "只有用户隔离可使用 $user_id。\n"
            f"Schema：\n{SCHEMA_DESCRIPTION}\n"
            f"涉及的节点类型：{node_types}\n"
            f"识别到的实体：{entities_text}\n"
            f"用户问题：{query}\n"
        )
        if error:
            prompt += f"上次生成的 Cypher 有误：{error}\n请修正后重新生成。\n"
        prompt += "只输出 Cypher 语句。"
        from app.llm import strip_code_fence

        return strip_code_fence(self._load().invoke(prompt).content)


def generate_with_self_correction(
    generator,
    validator,
    query: str,
    route: RouteResult,
    entry_nodes,
    max_retries: int = 3,
) -> tuple[str, list[str]]:
    """生成 Cypher 并自校正：出错带错误信息重写，重试上限 max_retries。

    返回 `(cypher, errors)`；cypher 为空表示重试耗尽仍未通过校验。
    """
    errors: list[str] = []
    error: str | None = None
    for _ in range(max_retries):
        cypher = generator.generate(
            query, route.node_types, route.entities, entry_nodes, error=error
        )
        ok, msg = validator.validate(cypher)
        if ok:
            return cypher, errors
        errors.append(msg or "校验失败")
        error = msg
    return "", errors
