"""真实 Neo4j + LLM Text2Cypher 端到端验证。

该脚本会在 Neo4j 中写入带 ``verification_fixture=true`` 的隔离测试数据，
查询后只删除这批数据。不要将其运行在未授权的数据库上。
"""

from dataclasses import dataclass

from app.capabilities.graphrag.executor import CypherExecutor, Neo4jDriver
from app.capabilities.graphrag.qa import GraphRagQA
from app.capabilities.graphrag.router import MockLabelRouter
from app.capabilities.graphrag.text2cypher import LLMCypherGenerator
from app.capabilities.graphrag.validator import CypherValidator
from app.core.config import settings
from app.llm import has_llm

QUESTION = "白色 256G 手机有哪些"
EXPECTED_PRODUCT = "StackPhone Pro"
FIXTURE_SKU = "StackPhone Pro 白色 256G"

SEED_CYPHER = """
MERGE (c:Category {category_id: 'verify-phone'})
SET c.name = '手机', c.verification_fixture = true
MERGE (p:SPU {spu_id: 'verify-stackphone'})
SET p.name = 'StackPhone Pro', p.verification_fixture = true
MERGE (s:SKU {sku_id: 'verify-white-256'})
SET s.name = $expected, s.price = 3999, s.verification_fixture = true
MERGE (color:Attr {name: '颜色', value: '白色', verification_fixture: true})
MERGE (storage:Attr {name: '容量', value: '256G', verification_fixture: true})
MERGE (c)-[:CONTAINS]->(p)
MERGE (p)-[:HAS_SKU]->(s)
MERGE (s)-[:HAS_ATTR]->(color)
MERGE (s)-[:HAS_ATTR]->(storage)
"""

CLEANUP_CYPHER = "MATCH (n {verification_fixture: true}) DETACH DELETE n"


@dataclass
class _NoopEntryRetriever:
    def retrieve(self, entity_text: str, top_k: int) -> list:
        return []


def verify() -> dict:
    if not has_llm():
        raise RuntimeError("请先配置 LLM__API_KEY，否则无法验证真实 Text2Cypher")
    driver = Neo4jDriver(settings.neo4j.uri, settings.neo4j.user, settings.neo4j.password)
    driver.query(CLEANUP_CYPHER)
    try:
        driver.query(SEED_CYPHER, {"expected": FIXTURE_SKU})
        qa = GraphRagQA(
            router=MockLabelRouter(),
            entry_retriever=_NoopEntryRetriever(),
            generator=LLMCypherGenerator(),
            validator=CypherValidator(driver),
            executor=CypherExecutor(driver),
            max_retries=settings.graphrag.max_retries,
        )
        answer = qa.ask(QUESTION)
        serialized = str(answer.records)
        if answer.no_answer or EXPECTED_PRODUCT not in serialized:
            raise AssertionError(
                f"未命中预期产品。cypher={answer.cypher!r}, "
                f"records={answer.records!r}, errors={answer.errors!r}"
            )
        return {
            "question": QUESTION,
            "cypher": answer.cypher,
            "records": answer.records,
            "passed": True,
        }
    finally:
        driver.query(CLEANUP_CYPHER)


if __name__ == "__main__":
    print(verify())
