"""监控：Prometheus 指标（会话量/成功率/首字延迟/降级次数）+ 阈值告警。"""

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta

from prometheus_client import CollectorRegistry, Counter, Histogram


@dataclass
class Alert:
    """告警。"""

    name: str
    message: str
    current: float
    threshold: float


def _counter_value(counter: Counter) -> float:
    for metric in counter.collect():
        for sample in metric.samples:
            if sample.name.endswith("_total"):
                return sample.value
    return 0.0


def _histogram_stats(histogram: Histogram) -> tuple[float, float]:
    total = count = 0.0
    for metric in histogram.collect():
        for sample in metric.samples:
            if sample.name.endswith("_sum"):
                total = sample.value
            elif sample.name.endswith("_count"):
                count = sample.value
    return total, count


def _histogram_quantile(histogram: Histogram, quantile: float) -> float:
    """根据 Prometheus 累积 bucket 估算分位数；+Inf 时回退到均值。"""
    total, count = _histogram_stats(histogram)
    if not count:
        return 0.0
    buckets: list[tuple[float, float]] = []
    for metric in histogram.collect():
        for sample in metric.samples:
            if not sample.name.endswith("_bucket"):
                continue
            upper = sample.labels.get("le", "+Inf")
            if upper != "+Inf":
                buckets.append((float(upper), sample.value))
    target = count * quantile
    for upper, cumulative in sorted(buckets):
        if cumulative >= target:
            return upper
    return total / count


class MetricsCollector:
    """会话量、成功率、首字延迟、降级次数指标 + 阈值告警。"""

    def __init__(
        self,
        *,
        error_rate_threshold: float = 0.05,
        latency_threshold_ms: float = 3000.0,
        degradation_threshold: int = 10,
        registry: CollectorRegistry | None = None,
    ) -> None:
        self.registry = registry or CollectorRegistry()
        self.session_total = Counter(
            "stacklang_session_total", "会话总量", registry=self.registry
        )
        self.session_success = Counter(
            "stacklang_session_success", "成功会话", registry=self.registry
        )
        self.latency = Histogram(
            "stacklang_first_token_latency_seconds", "首字延迟", registry=self.registry
        )
        self.degradation = Counter(
            "stacklang_degradation_total", "降级次数", registry=self.registry
        )
        self.error_rate_threshold = error_rate_threshold
        self.latency_threshold_ms = latency_threshold_ms
        self.degradation_threshold = degradation_threshold
        self._recent_sessions: deque[tuple[datetime, bool]] = deque(maxlen=20_000)

    def record_session(self, success: bool = True) -> None:
        self.session_total.inc()
        self._recent_sessions.append((datetime.now(), success))
        if success:
            self.session_success.inc()

    def record_latency(self, seconds: float) -> None:
        self.latency.observe(seconds)

    def record_first_token_latency(self, seconds: float) -> None:
        self.record_latency(seconds)

    def first_token_latency_p95_ms(self) -> float:
        return round(_histogram_quantile(self.latency, 0.95) * 1000.0, 2)

    def trend(self) -> list[dict[str, float | int | str]]:
        """近 24 小时按小时聚合；生产环境可由 Prometheus 长期存储替代。"""
        now = datetime.now().replace(minute=0, second=0, microsecond=0)
        buckets = [(now - timedelta(hours=offset), []) for offset in range(6, -1, -1)]
        for stamp, success in self._recent_sessions:
            for hour, values in buckets:
                if stamp.replace(minute=0, second=0, microsecond=0) == hour:
                    values.append(success)
                    break
        return [
            {
                "time": hour.strftime("%H:00"),
                "sessions": len(values),
                "successRate": sum(values) / len(values) if values else 1.0,
            }
            for hour, values in buckets
        ]

    def record_degradation(self) -> None:
        self.degradation.inc()

    def success_rate(self) -> float:
        total = _counter_value(self.session_total)
        success = _counter_value(self.session_success)
        return success / total if total else 1.0

    def check_alerts(self) -> list[Alert]:
        alerts: list[Alert] = []
        error_rate = 1.0 - self.success_rate()
        if error_rate > self.error_rate_threshold:
            alerts.append(
                Alert("error_rate", "错误率超阈值", error_rate, self.error_rate_threshold)
            )
        total_ms, count = _histogram_stats(self.latency)
        avg_ms = (total_ms / count * 1000.0) if count else 0.0
        if avg_ms > self.latency_threshold_ms:
            alerts.append(Alert("latency", "首字延迟超阈值", avg_ms, self.latency_threshold_ms))
        degradation = _counter_value(self.degradation)
        if degradation > self.degradation_threshold:
            alerts.append(
                Alert("degradation", "降级次数超阈值", degradation, self.degradation_threshold)
            )
        return alerts
