"""GraphRAG 测试：标签路由、Text2Cypher 自校正、user_id 过滤、执行格式化、编排。"""

from app.capabilities.graphrag.entry import EntryRetriever
from app.capabilities.graphrag.executor import CypherExecutor, enforce_user_filter
from app.capabilities.graphrag.qa import GraphRagQA
from app.capabilities.graphrag.router import MockLabelRouter, RouteResult
from app.capabilities.graphrag.schema import NodeType
from app.capabilities.graphrag.text2cypher import (
    MockCypherGenerator,
    generate_with_self_correction,
)
from app.capabilities.graphrag.validator import CypherValidator
from app.retrieval.hybrid import SearchResult


def _route(types=None):
    return RouteResult(node_types=types or [], entities=[])


# —— 标签路由 ——
def test_label_router_types_and_entities():
    r = MockLabelRouter().route("苹果品牌有哪些手机")
    assert NodeType.TRADEMARK in r.node_types  # 品牌
    assert NodeType.SPU in r.node_types  # 手机
    assert any(e.value == "苹果" and e.node_type == NodeType.TRADEMARK for e in r.entities)


# —— 自校正闭环 ——
class _ControllableGenerator:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def generate(self, query, node_types, entities, entry_nodes, error=None):
        self.calls.append(error)
        return self.responses.pop(0)


class _FakeValidator:
    def __init__(self, reject):
        self.reject = set(reject)

    def validate(self, cypher):
        if cypher in self.reject:
            return False, f"语法错误: {cypher}"
        return True, None


def test_self_correction_recovers():
    gen = _ControllableGenerator(["BAD", "GOOD"])
    validator = _FakeValidator(["BAD"])
    cypher, errors = generate_with_self_correction(gen, validator, "q", _route(), [], max_retries=3)
    assert cypher == "GOOD"
    assert len(gen.calls) == 2  # 失败一次后重写成功
    assert len(errors) == 1


def test_self_correction_gives_up_after_max_retries():
    gen = _ControllableGenerator(["BAD", "BAD", "BAD"])
    validator = _FakeValidator(["BAD"])
    cypher, errors = generate_with_self_correction(gen, validator, "q", _route(), [], max_retries=3)
    assert cypher == ""
    assert len(gen.calls) == 3  # 重试上限
    assert len(errors) == 3


def test_validator_rejects_unbound_domain_parameters():
    validator = CypherValidator(_FakeDriver())
    ok, error = validator.validate("MATCH (s:SKU {name: $sku_name}) RETURN s")
    assert ok is False
    assert "$sku_name" in error


def test_validator_allows_bound_user_parameter():
    validator = CypherValidator(_FakeDriver())
    ok, error = validator.validate(
        "MATCH (u:User {user_id: $user_id})-[:PURCHASED]->(s:SKU) RETURN s"
    )
    assert ok is True
    assert error is None


# —— user_id 安全过滤 ——
def test_enforce_user_filter():
    assert enforce_user_filter("MATCH (n) RETURN n", has_user=False, user_id=None)[0] is True
    ok, _ = enforce_user_filter("MATCH (u:User) RETURN u", has_user=True, user_id="u1")
    assert ok is False  # 缺少 $user_id
    ok, _ = enforce_user_filter(
        "MATCH (u:User {user_id: $user_id}) RETURN u", has_user=True, user_id=None
    )
    assert ok is False  # 缺少 user_id 值
    ok, _ = enforce_user_filter(
        "MATCH (u:User {user_id: $user_id}) RETURN u", has_user=True, user_id="u1"
    )
    assert ok is True


# —— 执行格式化 ——
class _FakeDriver:
    def __init__(self, records=None, reject=None):
        self.records = records or []
        self.reject = reject or set()
        self.queries = []

    def explain(self, cypher):
        if cypher in self.reject:
            raise ValueError(f"语法错误: {cypher}")

    def query(self, cypher, params=None):
        self.queries.append((cypher, params))
        return self.records


def test_executor_format():
    text = CypherExecutor(_FakeDriver()).format([{"name": "iPhone"}, {"name": "华为"}])
    assert "iPhone" in text


# —— 端到端编排 ——
class _PassHybrid:
    def retrieve(self, query, top_k):
        return [SearchResult(id="n1", text="苹果", score=0.9, metadata={})]


def _qa(driver, **kwargs):
    return GraphRagQA(
        router=MockLabelRouter(),
        entry_retriever=EntryRetriever(_PassHybrid()),
        generator=MockCypherGenerator(),
        validator=CypherValidator(driver),
        executor=CypherExecutor(driver),
        **kwargs,
    )


def test_graphrag_orchestration_with_fake_driver():
    driver = _FakeDriver(records=[{"name": "iPhone"}])
    ans = _qa(driver).ask("苹果品牌有哪些商品")
    assert not ans.no_answer
    assert ans.cypher  # 记录生成的 Cypher（可追溯）
    assert "iPhone" in ans.text


def test_graphrag_user_query_requires_user_id():
    driver = _FakeDriver(records=[{"name": "SKU"}])
    ans = _qa(driver).ask("我购买过什么", user_id=None)
    assert ans.no_answer is True  # 未提供 user_id，被安全过滤拦截
    assert "user_id" in ans.text


def test_graphrag_user_query_with_user_id():
    driver = _FakeDriver(records=[{"name": "SKU"}])
    ans = _qa(driver).ask("我购买过什么", user_id="u1")
    assert not ans.no_answer
    assert driver.queries[0][1] == {"user_id": "u1"}  # user_id 以参数绑定传入
