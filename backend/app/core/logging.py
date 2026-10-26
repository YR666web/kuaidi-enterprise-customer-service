"""日志配置。

骨架阶段使用标准库 logging；阶段后续可替换为 structlog + OpenTelemetry，
见《技术设计文档》第 10 节（可观测性）。
"""

import logging


def setup_logging(level: int = logging.INFO) -> None:
    """初始化根日志器（幂等，可多次调用）。"""
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    )
