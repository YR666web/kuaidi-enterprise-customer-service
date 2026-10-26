"""Neo4j 图谱 schema：节点类型与关系（供 Text2Cypher 提示词）。"""

from enum import StrEnum


class NodeType(StrEnum):
    CATEGORY = "Category"    # 分类
    TRADEMARK = "Trademark"  # 品牌
    SPU = "SPU"              # 标准产品单元
    SKU = "SKU"              # 最小库存单元
    ATTR = "Attr"            # 属性
    USER = "User"            # 用户


# Neo4j schema 描述（Text2Cypher 的提示词上下文）
SCHEMA_DESCRIPTION = """
节点：
- (:Category {name, category_id})
- (:Trademark {name, trademark_id})
- (:SPU {name, spu_id})
- (:SKU {name, sku_id, price})
- (:Attr {name, value})
- (:User {user_id, name})
关系：
- (:Category)-[:CONTAINS]->(:SPU)
- (:Trademark)-[:PRODUCES]->(:SPU)
- (:SPU)-[:HAS_SKU]->(:SKU)
- (:SKU)-[:HAS_ATTR]->(:Attr)
- (:User)-[:PURCHASED]->(:SKU)
""".strip()
