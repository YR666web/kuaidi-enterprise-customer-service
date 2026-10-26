"""GraphRAG 图谱问答能力：标签路由 → 入口检索 → Text2Cypher → 校验自校正 → 执行。"""

from app.capabilities.graphrag.entry import EntryRetriever
from app.capabilities.graphrag.executor import (
    CypherExecutor,
    GraphDriver,
    Neo4jDriver,
    enforce_user_filter,
)
from app.capabilities.graphrag.qa import GraphAnswer, GraphRagQA
from app.capabilities.graphrag.router import EntityRef, LabelRouter, MockLabelRouter, RouteResult
from app.capabilities.graphrag.schema import SCHEMA_DESCRIPTION, NodeType
from app.capabilities.graphrag.text2cypher import (
    CypherGenerator,
    LLMCypherGenerator,
    MockCypherGenerator,
    generate_with_self_correction,
)
from app.capabilities.graphrag.validator import CypherValidator, LogicChecker


def build_graphrag_service() -> GraphRagQA:
    """按配置构建 GraphRAG 服务（本机 Neo4j bolt://localhost:7687）。"""
    from app.core.config import settings
    from app.llm import has_llm
    from app.retrieval import build_hybrid_retrieval

    hybrid = build_hybrid_retrieval()
    driver = Neo4jDriver(settings.neo4j.uri, settings.neo4j.user, settings.neo4j.password)
    generator = LLMCypherGenerator() if has_llm() else MockCypherGenerator()
    return GraphRagQA(
        router=MockLabelRouter(),
        entry_retriever=EntryRetriever(hybrid),
        generator=generator,
        validator=CypherValidator(driver),
        executor=CypherExecutor(driver),
        max_retries=settings.graphrag.max_retries,
        entry_top_k=settings.graphrag.entry_top_k,
    )


__all__ = [
    "CypherExecutor",
    "CypherGenerator",
    "CypherValidator",
    "EntityRef",
    "EntryRetriever",
    "GraphAnswer",
    "GraphDriver",
    "GraphRagQA",
    "LabelRouter",
    "LogicChecker",
    "MockCypherGenerator",
    "MockLabelRouter",
    "Neo4jDriver",
    "NodeType",
    "RouteResult",
    "SCHEMA_DESCRIPTION",
    "build_graphrag_service",
    "enforce_user_filter",
    "generate_with_self_correction",
]
