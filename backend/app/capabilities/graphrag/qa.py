"""GraphRAG 编排：标签路由 → 入口检索 → Text2Cypher → 校验自校正 → 执行格式化。"""

from dataclasses import dataclass, field

from app.capabilities.graphrag.entry import EntryRetriever
from app.capabilities.graphrag.executor import CypherExecutor, enforce_user_filter
from app.capabilities.graphrag.router import LabelRouter
from app.capabilities.graphrag.schema import NodeType
from app.capabilities.graphrag.text2cypher import CypherGenerator, generate_with_self_correction
from app.capabilities.graphrag.validator import CypherValidator


@dataclass
class GraphAnswer:
    """图谱问答结果。"""

    text: str
    no_answer: bool = False
    cypher: str = ""  # 生成的 Cypher（可追溯）
    records: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class GraphRagQA:
    """GraphRAG 编排器。"""

    def __init__(
        self,
        router: LabelRouter,
        entry_retriever: EntryRetriever,
        generator: CypherGenerator,
        validator: CypherValidator,
        executor: CypherExecutor,
        *,
        max_retries: int = 3,
        entry_top_k: int = 3,
    ) -> None:
        self.router = router
        self.entry_retriever = entry_retriever
        self.generator = generator
        self.validator = validator
        self.executor = executor
        self.max_retries = max_retries
        self.entry_top_k = entry_top_k

    def ask(self, query: str, user_id: str | None = None) -> GraphAnswer:
        route = self.router.route(query)
        entity_text = " ".join(e.value for e in route.entities) or query
        entry_nodes = self.entry_retriever.retrieve(entity_text, top_k=self.entry_top_k)

        cypher, errors = generate_with_self_correction(
            self.generator, self.validator, query, route, entry_nodes, max_retries=self.max_retries
        )
        if not cypher:
            return GraphAnswer(text="无法生成有效的图谱查询。", no_answer=True, errors=errors)

        has_user = NodeType.USER in route.node_types
        ok, msg = enforce_user_filter(cypher, has_user, user_id)
        if not ok:
            return GraphAnswer(text=msg or "查询被安全过滤拦截。", no_answer=True, errors=[msg])

        params = {"user_id": user_id} if has_user else None
        records = self.executor.execute(cypher, params)
        return GraphAnswer(
            text=self.executor.format(records), cypher=cypher, records=records, errors=errors
        )
