"""应用配置 —— 分层配置，集中管理。

配置来源优先级（由高到低）：
1. 环境变量 / `.env` 文件（字段命名：`<层级>__<字段>`，双下划线分隔）
2. 代码内默认值（本机裸跑默认值，无需 Docker）

使用方式：`from app.core.config import settings`
"""

from functools import lru_cache

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseModel):
    """应用自身配置。"""

    name: str = "快递企业智能客服"
    version: str = "0.1.0"
    debug: bool = False
    environment: str = "development"  # development | production
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )


class DatabaseSettings(BaseModel):
    """业务数据库（开发期 SQLite，阶段 9 换 MySQL）。"""

    url: str = "sqlite:///./stacklang.db"
    echo: bool = False


class RedisSettings(BaseModel):
    """Redis（LangGraph checkpoint 后端，开发期可用 MemorySaver 替代）。"""

    url: str = "redis://localhost:6379/0"


class Neo4jSettings(BaseModel):
    """Neo4j 知识图谱。"""

    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    password: str = "neo4j"


class ChromaSettings(BaseModel):
    """Chroma 向量库（进程内运行）。"""

    persist_dir: str = "./data/chroma"
    collection: str = "knowledge_base"


class EmbeddingSettings(BaseModel):
    """向量模型配置（bge-base-zh-v1.5，本地缓存）。"""

    model_name: str = "BAAI/bge-base-zh-v1.5"
    # HuggingFace cache 根目录（相对 backend/，即项目根 models/）
    cache_dir: str = "../models"
    device: str = "cpu"


class LLMSettings(BaseModel):
    """LLM 配置（DeepSeek，OpenAI 兼容）。"""

    provider: str = "deepseek"
    model: str = "deepseek-chat"
    fast_model: str = "deepseek-flash"
    reasoning_model: str = "deepseek-v4-pro"
    fast_max_tokens: int = 320
    reasoning_max_tokens: int = 2048
    reasoning_effort: str = "high"
    api_key: str = ""
    base_url: str = "https://api.deepseek.com"
    temperature: float = 0.0


class AgentSettings(BaseModel):
    """编排层（LangGraph）配置。

    - checkpoint_backend：memory | redis（redis 需额外安装 langgraph-checkpoint-redis）
    - max_actions：单轮最大动作次数（guard 防死循环）
    """

    checkpoint_backend: str = "memory"
    max_actions: int = 8


class WorkflowSettings(BaseModel):
    """多轮业务办理（Workflow）配置。"""

    flows_dir: str = "data/flows"  # Flow YAML 目录（相对 backend/）


class BusinessIntegrationSettings(BaseModel):
    """订单/物流/售后服务适配器。

    local：本地数据库（默认）；demo：可重复的沙盒供应商；http：调用已授权的业务网关。
    真实环境使用 http，并在环境变量中配置端点与令牌。
    """

    provider: str = "local"  # local | demo | http
    base_url: str = ""
    api_token: str = ""
    timeout_seconds: float = 5.0
    max_retries: int = 2
    circuit_failure_threshold: int = 3
    circuit_reset_seconds: float = 30.0


class RetrievalSettings(BaseModel):
    """检索底座（retrieval）配置。"""

    query_prefix: str = "为这个句子生成表示以用于检索相关文章："  # bge query 侧前缀
    rerank_model: str = "BAAI/bge-reranker-v2-m3"
    rrf_k: int = 60  # RRF 融合常数
    top_k: int = 5  # 默认召回数
    bm25_backend: str = "rank_bm25"  # rank_bm25 | elasticsearch（生产切换位）


class RagSettings(BaseModel):
    """RAG 知识问答配置。"""

    chunk_size: int = 512
    chunk_overlap: int = 64
    top_k: int = 4  # 送入 LLM 的上下文 chunk 数
    score_threshold: float = 0.3  # 低于该相似度返回"无答案"（阈值需按 reranker 校准）
    no_answer_reply: str = "抱歉，未在知识库中找到与您问题相关的答案。"


class GraphRagSettings(BaseModel):
    """GraphRAG 图谱问答配置。"""

    max_retries: int = 3  # Cypher 自校正重试上限
    entry_top_k: int = 3  # 入口节点召回数


class PlatformSettings(BaseModel):
    """平台能力（多租户/RBAC/监控/审计）配置。"""

    jwt_secret: str = "dev-secret-change-me-please-override-32"
    jwt_algorithm: str = "HS256"
    rate_limit_backend: str = "memory"  # memory | redis
    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60
    error_rate_threshold: float = 0.05  # 错误率告警阈值
    latency_threshold_ms: float = 3000.0  # 首字延迟告警阈值（毫秒）
    degradation_threshold: int = 10  # 降级次数告警阈值


class Settings(BaseSettings):
    """顶层配置，聚合各层。"""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),  # 优先 backend/.env，回退项目根 .env
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    app: AppSettings = AppSettings()
    database: DatabaseSettings = DatabaseSettings()
    redis: RedisSettings = RedisSettings()
    neo4j: Neo4jSettings = Neo4jSettings()
    chroma: ChromaSettings = ChromaSettings()
    embedding: EmbeddingSettings = EmbeddingSettings()
    llm: LLMSettings = LLMSettings()
    agent: AgentSettings = AgentSettings()
    workflow: WorkflowSettings = WorkflowSettings()
    business_integration: BusinessIntegrationSettings = BusinessIntegrationSettings()
    retrieval: RetrievalSettings = RetrievalSettings()
    rag: RagSettings = RagSettings()
    graphrag: GraphRagSettings = GraphRagSettings()
    platform: PlatformSettings = PlatformSettings()

    @model_validator(mode="after")
    def validate_production_safety(self):
        if self.app.environment != "production":
            return self
        insecure_secret = self.platform.jwt_secret.startswith("dev-secret-")
        if insecure_secret or len(self.platform.jwt_secret) < 32:
            raise ValueError("生产环境必须配置至少 32 位的非默认 PLATFORM__JWT_SECRET")
        if self.agent.checkpoint_backend != "redis":
            raise ValueError("生产环境必须使用 Redis checkpoint")
        if self.platform.rate_limit_backend != "redis":
            raise ValueError("生产环境必须使用 Redis 限流")
        return self


@lru_cache
def get_settings() -> Settings:
    """返回缓存的 Settings 单例。"""
    return Settings()


settings = get_settings()
