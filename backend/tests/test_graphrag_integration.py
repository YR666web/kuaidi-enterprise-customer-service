"""真实依赖集成测试；与 FakeDriver 单测明确分离。"""

import os

import pytest

from scripts.verify_graphrag import verify


@pytest.mark.integration
def test_real_neo4j_llm_text2cypher_end_to_end():
    if os.getenv("RUN_NEO4J_INTEGRATION") != "1":
        pytest.skip("设置 RUN_NEO4J_INTEGRATION=1 后才运行真实 Neo4j/LLM 测试")
    report = verify()
    assert report["passed"] is True
    assert report["records"]
