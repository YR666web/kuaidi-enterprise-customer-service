"""pytest 配置：慢测试（加载真实模型）默认跳过，用 `--run-slow` 显式运行。"""

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--run-slow", action="store_true", default=False, help="运行慢测试（加载真实模型）"
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-slow"):
        return
    skip_slow = pytest.mark.skip(reason="慢测试，需 --run-slow 才运行")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)


@pytest.fixture(autouse=True)
def _force_mock_llm(monkeypatch):
    """测试统一用关键词意图路由，避免依赖真实 LLM（.env 里的 key）。"""
    from app.agent import nodes, router

    monkeypatch.setattr(nodes, "INTENT_ROUTER", router.KeywordIntentRouter())
