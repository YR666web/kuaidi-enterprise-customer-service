"""语义切分：句子感知 + 长度约束 + 重叠。"""

import re


class SemanticChunker:
    """按句子切分，聚合到接近 chunk_size 的块（下一块保留上一块末尾 overlap 字符）。"""

    _SENT_RE = re.compile(r"[^。！？!?；;\n]+[。！？!?；;]?")

    def __init__(self, chunk_size: int = 512, overlap: int = 64) -> None:
        self.chunk_size = chunk_size
        self.overlap = overlap

    def split(self, text: str) -> list[str]:
        sentences = [m.group(0).strip() for m in self._SENT_RE.finditer(text)]
        sentences = [s for s in sentences if s]
        chunks: list[str] = []
        current = ""
        for sent in sentences:
            if current and len(current) + len(sent) > self.chunk_size:
                chunks.append(current)
                current = current[-self.overlap:] if self.overlap else ""
            current += sent
        if current:
            chunks.append(current)
        return chunks
