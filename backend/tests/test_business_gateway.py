from app.core.config import BusinessIntegrationSettings
from app.services.business_gateway import (
    BusinessGateway,
    BusinessIntegrationError,
    DemoBusinessProvider,
    build_business_gateway,
)


def test_demo_provider_is_explicitly_labelled_as_sandbox():
    gateway = BusinessGateway(DemoBusinessProvider(), BusinessIntegrationSettings(provider="demo"))
    result = gateway.track("SF123")
    assert result["status"] == "沙盒运输中"
    assert "演示供应商" in result["estimate"]


def test_circuit_breaker_opens_after_repeated_provider_failure():
    class BrokenProvider:
        def track(self, _tracking_no):
            raise RuntimeError("upstream down")

        def update_address(self, *_args, **_kwargs):
            raise RuntimeError("upstream down")

        def create_return(self, *_args):
            raise RuntimeError("upstream down")

    settings = BusinessIntegrationSettings(circuit_failure_threshold=2, circuit_reset_seconds=60)
    gateway = BusinessGateway(BrokenProvider(), settings)
    for _ in range(2):
        try:
            gateway.track("SF123")
        except BusinessIntegrationError:
            pass
    try:
        gateway.track("SF123")
    except BusinessIntegrationError as exc:
        assert "保护" in str(exc)
    else:
        raise AssertionError("连续失败后应熔断")


def test_unknown_provider_rejected():
    try:
        build_business_gateway(BusinessIntegrationSettings(provider="unknown"))
    except ValueError as exc:
        assert "未知业务供应商" in str(exc)
    else:
        raise AssertionError("未知供应商应拒绝")
