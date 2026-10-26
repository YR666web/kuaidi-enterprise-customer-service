"""滑动窗口限流：开发环境内存实现，生产多实例使用 Redis。"""

from collections import defaultdict, deque
from threading import Lock
from time import monotonic
from uuid import uuid4

from app.core.config import PlatformSettings, RedisSettings


class RateLimiter:
    def __init__(self, limit: int = 60, window_seconds: int = 60) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        now = monotonic()
        with self._lock:
            events = self._events[key]
            while events and now - events[0] >= self.window_seconds:
                events.popleft()
            if len(events) >= self.limit:
                return False
            events.append(now)
            return True


class RedisRateLimiter:
    """原子 Redis 滑动窗口，多 worker/多实例共享计数。"""

    _SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]
redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window)
local count = redis.call('ZCARD', key)
if count >= limit then return 0 end
redis.call('ZADD', key, now, member)
redis.call('PEXPIRE', key, window)
return 1
"""

    def __init__(self, redis_client, limit: int = 60, window_seconds: int = 60) -> None:
        self.redis = redis_client
        self.limit = limit
        self.window_ms = window_seconds * 1000

    def allow(self, key: str) -> bool:
        from time import time

        now_ms = int(time() * 1000)
        result = self.redis.eval(
            self._SCRIPT,
            1,
            f"stacklang:ratelimit:{key}",
            now_ms,
            self.window_ms,
            self.limit,
            f"{now_ms}:{uuid4().hex}",
        )
        return bool(result)


def build_rate_limiter(platform: PlatformSettings, redis: RedisSettings):
    if platform.rate_limit_backend == "memory":
        return RateLimiter(platform.rate_limit_requests, platform.rate_limit_window_seconds)
    if platform.rate_limit_backend == "redis":
        from redis import Redis

        client = Redis.from_url(redis.url, decode_responses=True)
        client.ping()
        return RedisRateLimiter(
            client, platform.rate_limit_requests, platform.rate_limit_window_seconds
        )
    raise ValueError(f"未知限流后端: {platform.rate_limit_backend}")
