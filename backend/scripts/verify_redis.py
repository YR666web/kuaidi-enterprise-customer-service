"""RedisSaver 与分布式限流真实集成验证。"""

from uuid import uuid4

from langchain_core.messages import HumanMessage
from redis import Redis

from app.agent.graph import build_graph, get_checkpointer
from app.core.config import settings
from app.platform.ratelimit import RedisRateLimiter


def verify() -> dict:
    client = Redis.from_url(settings.redis.url, decode_responses=True)
    if not client.ping():
        raise RuntimeError("Redis PING 失败")

    # 两个限流器实例共享同一 Redis 窗口。
    key = f"verify-{uuid4().hex}"
    limiter_a = RedisRateLimiter(client, limit=2, window_seconds=60)
    limiter_b = RedisRateLimiter(client, limit=2, window_seconds=60)
    if not limiter_a.allow(key) or not limiter_b.allow(key) or limiter_a.allow(key):
        raise AssertionError("Redis 共享限流验证失败")

    # 用第一个 saver 写入 checkpoint，再用全新 saver 读回，证明非进程内状态。
    thread_id = f"redis-verify-{uuid4().hex}"
    saver_a = get_checkpointer("redis")
    saver_a.setup()
    graph_a = build_graph(saver_a)
    graph_a.invoke(
        {"user_input": "你好", "session_id": thread_id},
        {"configurable": {"thread_id": thread_id}},
    )

    saver_b = get_checkpointer("redis")
    saver_b.setup()
    graph_b = build_graph(saver_b)
    state = graph_b.get_state({"configurable": {"thread_id": thread_id}}).values
    messages = state.get("messages", [])
    if not any(isinstance(message, HumanMessage) for message in messages):
        raise AssertionError("新 RedisSaver 实例未读回 checkpoint")

    for saver in (saver_a, saver_b):
        redis_client = getattr(saver, "_redis", None)
        if redis_client is not None:
            redis_client.close()
    client.delete(f"stacklang:ratelimit:{key}")
    client.close()
    return {
        "redis_url": settings.redis.url,
        "checkpoint_restored": True,
        "shared_rate_limit": True,
    }


if __name__ == "__main__":
    print(verify())
