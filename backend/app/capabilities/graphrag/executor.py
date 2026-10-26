"""Cypher 执行 + 结果格式化 + 安全过滤。"""

from typing import Protocol


class GraphDriver(Protocol):
    """图数据库驱动接口（可插拔：Neo4j / 测试假驱动）。"""

    def explain(self, cypher: str) -> None: ...

    def query(self, cypher: str, params: dict | None = None) -> list[dict]: ...


class Neo4jDriver:
    """Neo4j 驱动（本机社区版 bolt://localhost:7687），懒加载。"""

    def __init__(self, uri: str, user: str, password: str, database: str = "neo4j") -> None:
        self.uri = uri
        self.user = user
        self.password = password
        self.database = database
        self._driver = None

    def _load(self):
        if self._driver is None:
            from neo4j import GraphDatabase

            self._driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
        return self._driver

    def explain(self, cypher: str) -> None:
        """EXPLAIN 语法校验（只读，不执行）。"""
        with self._load().session(database=self.database) as session:
            session.run(f"EXPLAIN {cypher}")

    def query(self, cypher: str, params: dict | None = None) -> list[dict]:
        """执行只读查询（需只读 DB 角色）。"""
        with self._load().session(database=self.database) as session:
            result = session.run(cypher, params or {})
            return [record.data() for record in result]


class CypherExecutor:
    """执行 Cypher 并格式化结果。"""

    def __init__(self, driver: GraphDriver) -> None:
        self.driver = driver

    def execute(self, cypher: str, params: dict | None = None) -> list[dict]:
        return self.driver.query(cypher, params)

    def format(self, records: list[dict]) -> str:
        if not records:
            return "未查询到相关结果。"
        lines = ["，".join(f"{k}={v}" for k, v in r.items()) for r in records[:5]]
        return "查询到以下结果：" + "；".join(lines)


def enforce_user_filter(
    cypher: str, has_user: bool, user_id: str | None
) -> tuple[bool, str | None]:
    """安全过滤：用户相关查询必须带 $user_id 过滤（防跨用户越权）。"""
    if not has_user:
        return True, None
    if "$user_id" not in cypher:
        return False, "用户相关查询缺少 user_id 过滤"
    if not user_id:
        return False, "用户相关查询需要提供 user_id"
    return True, None
