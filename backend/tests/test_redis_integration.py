import os

import pytest

from scripts.verify_redis import verify


@pytest.mark.integration
def test_real_redis_checkpoint_and_rate_limit():
    if os.getenv("RUN_REDIS_INTEGRATION") != "1":
        pytest.skip("设置 RUN_REDIS_INTEGRATION=1 后才运行真实 Redis 测试")
    report = verify()
    assert report["checkpoint_restored"]
    assert report["shared_rate_limit"]
