"""标签路由：识别节点类型（Category/Trademark/SPU/SKU/Attr/User）与实体。"""

from dataclasses import dataclass, field
from typing import Protocol

from app.capabilities.graphrag.schema import NodeType


@dataclass
class EntityRef:
    """识别出的实体（节点类型 + 匹配值）。"""

    node_type: NodeType
    value: str


@dataclass
class RouteResult:
    """标签路由结果。"""

    node_types: list[NodeType] = field(default_factory=list)
    entities: list[EntityRef] = field(default_factory=list)


class LabelRouter(Protocol):
    """标签路由接口（可插拔：Mock / LLM structured output）。"""

    def route(self, query: str) -> RouteResult: ...


# 节点类型 → 触发关键词（Mock；阶段后续替换为 LLM structured output）
_TYPE_KEYWORDS: dict[NodeType, tuple[str, ...]] = {
    NodeType.CATEGORY: ("分类", "类目", "品类", "有哪些类别"),
    NodeType.TRADEMARK: ("品牌", "商标", "哪个牌子"),
    NodeType.SPU: ("商品", "spu", "手机", "电脑", "产品"),
    NodeType.SKU: ("sku", "型号", "规格", "售价", "价格"),
    NodeType.ATTR: ("属性", "颜色", "内存", "尺寸", "参数"),
    NodeType.USER: ("我", "我的", "订单", "购买", "已购", "user"),
}

# 已知实体 → 节点类型（Mock 实体抽取；阶段后续接 LLM NER）
_KNOWN_ENTITIES: dict[str, NodeType] = {
    "苹果": NodeType.TRADEMARK,
    "华为": NodeType.TRADEMARK,
    "手机": NodeType.CATEGORY,
    "电脑": NodeType.CATEGORY,
}


class MockLabelRouter:
    """占位：关键词匹配节点类型 + 已知实体抽取（阶段后续接 LLM）。"""

    def route(self, query: str) -> RouteResult:
        node_types = [t for t, kws in _TYPE_KEYWORDS.items() if any(k in query for k in kws)]
        entities = [EntityRef(nt, name) for name, nt in _KNOWN_ENTITIES.items() if name in query]
        return RouteResult(node_types=node_types, entities=entities)
