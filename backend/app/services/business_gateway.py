"""订单、物流、售后的供应商适配层。

Workflow 只面对统一的业务能力；本地仓储、演示供应商和真实 HTTP 网关可由配置切换。
"""

from dataclasses import dataclass, field
from time import monotonic
from typing import Protocol

import httpx

from app.core.config import BusinessIntegrationSettings, settings
from app.repositories.business import (
    AfterSalesRepository,
    LogisticsRepository,
    Order,
    OrderRepository,
    ReturnRequest,
)


class BusinessIntegrationError(RuntimeError):
    """上游不可用、响应不合法或熔断时的统一错误。"""


class BusinessProvider(Protocol):
    def track(self, tracking_no: str) -> dict[str, str]: ...

    def update_address(self, order_id: str, **fields: str) -> Order: ...

    def create_return(self, reason: str, goods_type: str) -> ReturnRequest: ...


@dataclass
class CircuitBreaker:
    threshold: int
    reset_seconds: float
    failures: int = 0
    opened_at: float | None = None

    def before_call(self) -> None:
        if self.opened_at is None:
            return
        if monotonic() - self.opened_at >= self.reset_seconds:
            self.failures = 0
            self.opened_at = None
            return
        raise BusinessIntegrationError("业务服务暂时繁忙，已启用保护，请稍后重试或转人工")

    def success(self) -> None:
        self.failures = 0
        self.opened_at = None

    def failure(self) -> None:
        self.failures += 1
        if self.failures >= self.threshold:
            self.opened_at = monotonic()


@dataclass
class LocalBusinessProvider:
    orders: OrderRepository = field(default_factory=OrderRepository)
    logistics: LogisticsRepository = field(default_factory=LogisticsRepository)
    after_sales: AfterSalesRepository = field(default_factory=AfterSalesRepository)

    def track(self, tracking_no: str) -> dict[str, str]:
        return self.logistics.track(tracking_no)

    def update_address(self, order_id: str, **fields: str) -> Order:
        return self.orders.update_address(order_id, **fields)

    def create_return(self, reason: str, goods_type: str) -> ReturnRequest:
        return self.after_sales.create_return(reason, goods_type)


class DemoBusinessProvider:
    """明确标注为沙盒的供应商，用于演示端到端接入，不伪装真实物流。"""

    def track(self, tracking_no: str) -> dict[str, str]:
        return {
            "tracking_no": tracking_no,
            "status": "沙盒运输中",
            "estimate": "演示供应商：预计 1 个工作日送达",
        }

    def update_address(self, order_id: str, **fields: str) -> Order:
        return Order(order_id=order_id, **fields)

    def create_return(self, reason: str, goods_type: str) -> ReturnRequest:
        return ReturnRequest(
            request_id=f"DEMO-{int(monotonic() * 1000)}", reason=reason, goods_type=goods_type
        )


class HttpBusinessProvider:
    """面向企业业务网关的 HTTP 适配器；统一超时、有限重试与错误语义。"""

    def __init__(self, config: BusinessIntegrationSettings) -> None:
        if not config.base_url:
            raise ValueError("BUSINESS_INTEGRATION__BASE_URL 是 http 供应商模式的必填项")
        self.base_url = config.base_url.rstrip("/")
        self.timeout = config.timeout_seconds
        self.max_retries = config.max_retries
        self.headers = {"Authorization": f"Bearer {config.api_token}"} if config.api_token else {}

    def _request(self, method: str, path: str, *, payload: dict | None = None) -> dict:
        last_error: Exception | None = None
        for _ in range(self.max_retries + 1):
            try:
                with httpx.Client(timeout=self.timeout, headers=self.headers) as client:
                    response = client.request(method, f"{self.base_url}{path}", json=payload)
                    response.raise_for_status()
                    data = response.json()
                    if not isinstance(data, dict):
                        raise BusinessIntegrationError("业务网关返回格式不正确")
                    return data
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
        raise BusinessIntegrationError(f"业务网关调用失败：{last_error}")

    def track(self, tracking_no: str) -> dict[str, str]:
        data = self._request("GET", f"/logistics/{tracking_no}")
        return {
            "tracking_no": tracking_no,
            "status": str(data.get("status", "未知")),
            "estimate": str(data.get("estimate", "暂未提供")),
        }

    def update_address(self, order_id: str, **fields: str) -> Order:
        data = self._request("PATCH", f"/orders/{order_id}/address", payload=fields)
        return Order(
            order_id=order_id,
            tracking_no=str(data.get("tracking_no", "")),
            status=str(data.get("status", "")),
            receiver_name=str(data.get("receiver_name", fields.get("receiver_name", ""))),
            receiver_phone=str(data.get("receiver_phone", fields.get("receiver_phone", ""))),
            receiver_address=str(data.get("receiver_address", fields.get("receiver_address", ""))),
        )

    def create_return(self, reason: str, goods_type: str) -> ReturnRequest:
        data = self._request(
            "POST", "/after-sales/returns", payload={"reason": reason, "goods_type": goods_type}
        )
        return ReturnRequest(
            request_id=str(data.get("request_id", "")),
            reason=reason,
            goods_type=goods_type,
            status=str(data.get("status", "待审核")),
        )


class BusinessGateway:
    def __init__(self, provider: BusinessProvider, config: BusinessIntegrationSettings) -> None:
        self.provider = provider
        self.breaker = CircuitBreaker(
            config.circuit_failure_threshold, config.circuit_reset_seconds
        )

    def _call(self, fn, *args, **kwargs):
        self.breaker.before_call()
        try:
            result = fn(*args, **kwargs)
        except Exception as exc:
            self.breaker.failure()
            if isinstance(exc, BusinessIntegrationError):
                raise
            raise BusinessIntegrationError("业务服务暂时不可用，请稍后重试或转人工") from exc
        self.breaker.success()
        return result

    def track(self, tracking_no: str) -> dict[str, str]:
        return self._call(self.provider.track, tracking_no)

    def update_address(self, order_id: str, **fields: str) -> Order:
        return self._call(self.provider.update_address, order_id, **fields)

    def create_return(self, reason: str, goods_type: str) -> ReturnRequest:
        return self._call(self.provider.create_return, reason, goods_type)


def build_business_gateway(config: BusinessIntegrationSettings | None = None) -> BusinessGateway:
    config = config or settings.business_integration
    providers: dict[str, BusinessProvider] = {
        "local": LocalBusinessProvider(),
        "demo": DemoBusinessProvider(),
    }
    if config.provider == "http":
        provider: BusinessProvider = HttpBusinessProvider(config)
    else:
        provider = providers.get(config.provider)  # type: ignore[assignment]
        if provider is None:
            raise ValueError(f"未知业务供应商模式: {config.provider}")
    return BusinessGateway(provider, config)
