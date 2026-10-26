from app.platform.ratelimit import RateLimiter, RedisRateLimiter


def test_rate_limiter_blocks_after_limit():
    limiter = RateLimiter(limit=2, window_seconds=60)
    assert limiter.allow("tenant")
    assert limiter.allow("tenant")
    assert not limiter.allow("tenant")
    assert limiter.allow("other")


def test_redis_rate_limiter_uses_atomic_script():
    class FakeRedis:
        def __init__(self):
            self.calls = 0

        def eval(self, script, key_count, key, *args):
            self.calls += 1
            assert "ZREMRANGEBYSCORE" in script
            assert key_count == 1
            assert key.startswith("stacklang:ratelimit:")
            return int(self.calls <= 2)

    redis = FakeRedis()
    limiter = RedisRateLimiter(redis, limit=2, window_seconds=60)
    assert limiter.allow("tenant")
    assert limiter.allow("tenant")
    assert not limiter.allow("tenant")
