"""订单、物流与售后仓储及 Workflow 动作适配器。"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.db.base import Base

# Workflow 既可在 FastAPI lifespan 中运行，也会被独立单测直接调用。
# 确保仓储在两种入口下都能使用。
from app.db.session import SessionLocal, engine
from app.models.business import OrderRecord, ReturnRequestRecord

Base.metadata.create_all(bind=engine)


@dataclass
class Order:
    order_id: str
    tracking_no: str = "SF1234567890"
    status: str = "已发货"
    receiver_name: str = ""
    receiver_phone: str = ""
    receiver_address: str = ""


@dataclass
class ReturnRequest:
    request_id: str
    reason: str
    goods_type: str
    status: str = "待审核"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class OrderRepository:
    def get(self, order_id: str = "default") -> Order:
        with SessionLocal() as db:
            record = db.query(OrderRecord).filter(OrderRecord.order_id == order_id).first()
            if record is None:
                record = OrderRecord(order_id=order_id)
                db.add(record)
                db.commit()
                db.refresh(record)
            order = Order(
                record.order_id, record.tracking_no, record.status,
                record.receiver_name, record.receiver_phone, record.receiver_address,
            )
        return order

    def update_address(self, order_id: str, **fields: str) -> Order:
        with SessionLocal() as db:
            record = db.query(OrderRecord).filter(OrderRecord.order_id == order_id).first()
            if record is None:
                record = OrderRecord(order_id=order_id)
                db.add(record)
            for key in ("receiver_name", "receiver_phone", "receiver_address"):
                if fields.get(key):
                    setattr(record, key, fields[key])
            db.commit()
            db.refresh(record)
            order = Order(
                record.order_id, record.tracking_no, record.status,
                record.receiver_name, record.receiver_phone, record.receiver_address,
            )
        return order


class LogisticsRepository:
    def track(self, tracking_no: str) -> dict[str, str]:
        # 真实物流状态必须来自已接入并授权的承运商 API，不能用演示值冒充。
        return {
            "tracking_no": tracking_no,
            "status": "未接入实时查询",
            "estimate": "当前无法核验物流轨迹",
        }


class AfterSalesRepository:
    def create_return(self, reason: str, goods_type: str) -> ReturnRequest:
        with SessionLocal() as db:
            next_id = (db.query(ReturnRequestRecord).count() + 1)
            request = ReturnRequest(f"R{next_id:06d}", reason, goods_type)
            db.add(ReturnRequestRecord(
                request_id=request.request_id,
                reason=request.reason,
                goods_type=request.goods_type,
                status=request.status,
            ))
            db.commit()
        return request


@dataclass
class BusinessRepositories:
    orders: OrderRepository = field(default_factory=OrderRepository)
    logistics: LogisticsRepository = field(default_factory=LogisticsRepository)
    after_sales: AfterSalesRepository = field(default_factory=AfterSalesRepository)


def build_action_handler(repositories: BusinessRepositories | None = None):
    if repositories is not None:
        from app.core.config import BusinessIntegrationSettings
        from app.services.business_gateway import BusinessGateway, LocalBusinessProvider

        gateway = BusinessGateway(
            LocalBusinessProvider(
                repositories.orders, repositories.logistics, repositories.after_sales
            ),
            BusinessIntegrationSettings(),
        )
    else:
        from app.services.business_gateway import build_business_gateway

        gateway = build_business_gateway()

    def handle(action: str, slots: dict[str, Any], flow_id: str) -> str:
        if action == "query_logistics":
            result = gateway.track(str(slots.get("tracking_no", "")))
            return (
                f"已收到物流单号 {result['tracking_no']}。{result['estimate']}；"
                "接入承运商的授权查询接口后，才能提供真实的物流状态。"
            )
        if action == "submit_address":
            order = gateway.update_address("default", **slots)
            return (
                f"收货地址已修改为：{order.receiver_name}，{order.receiver_phone}，"
                f"{order.receiver_address}。"
            )
        if action in {"handle_fresh_return", "handle_normal_return", "submit_return"}:
            request = gateway.create_return(
                str(slots.get("reason", "用户申请")), str(slots.get("goods_type", "普通"))
            )
            return f"退货申请 {request.request_id} 已提交，当前状态：{request.status}。"
        return f"已完成{flow_id}业务操作：{action}。"

    return handle
