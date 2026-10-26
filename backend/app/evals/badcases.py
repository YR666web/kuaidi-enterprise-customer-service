"""文件化 badcase 回归集。

每行一个 JSON 对象，方便把人工质检、线上告警或面试演示中的失败样本直接沉淀进仓库。
不存放真实用户身份、订单号或其他敏感信息。
"""

import json
from dataclasses import dataclass
from pathlib import Path

from app.agent.state import Intent

BADCASE_PATH = Path(__file__).resolve().parents[2] / "data" / "evals" / "badcases.jsonl"


@dataclass(frozen=True)
class Badcase:
    id: str
    query: str
    expected_intent: Intent
    expected_tier: str
    category: str
    severity: str
    regression: str


def load_badcases(path: Path = BADCASE_PATH) -> tuple[Badcase, ...]:
    """读取版本控制下的 JSONL，并在启动评测时严格校验字段。"""
    cases: list[Badcase] = []
    ids: set[str] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        try:
            raw = json.loads(line)
            case = Badcase(
                id=str(raw["id"]),
                query=str(raw["query"]),
                expected_intent=Intent(raw["expected_intent"]),
                expected_tier=str(raw.get("expected_tier", "fast")),
                category=str(raw["category"]),
                severity=str(raw.get("severity", "medium")),
                regression=str(raw["regression"]),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"badcase 第 {line_number} 行格式错误: {exc}") from exc
        if not case.id or case.id in ids:
            raise ValueError(f"badcase 第 {line_number} 行 id 为空或重复: {case.id!r}")
        ids.add(case.id)
        cases.append(case)
    return tuple(cases)
