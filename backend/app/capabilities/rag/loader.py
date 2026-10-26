"""文档解析：PDF / Markdown / 纯文本。"""

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ParsedSection:
    """解析出的文本段（PDF 按页，Markdown/文本为整体）。"""

    text: str
    page: int | None = None


def load(path: str) -> list[ParsedSection]:
    """按扩展名分发解析。"""
    ext = Path(path).suffix.lower()
    if ext == ".pdf":
        return load_pdf(path)
    if ext in (".md", ".markdown"):
        return [ParsedSection(text=load_markdown(path))]
    return [ParsedSection(text=load_text(path))]


def load_text(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def load_markdown(path: str) -> str:
    return markdown_to_text(load_text(path))


def load_pdf(path: str) -> list[ParsedSection]:
    """PDF 按页提取文本（pypdf）。"""
    from pypdf import PdfReader

    reader = PdfReader(path)
    return [
        ParsedSection(text=page.extract_text() or "", page=i)
        for i, page in enumerate(reader.pages, start=1)
    ]


def markdown_to_text(md: str) -> str:
    """轻量 Markdown → 纯文本（去代码块、标题、链接、加粗/斜体、列表标记）。"""
    text = md
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)  # 代码块
    text = re.sub(r"`([^`]*)`", r"\1", text)  # 行内代码
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)  # 图片
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)  # 链接
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.MULTILINE)  # 标题
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)  # 加粗
    text = re.sub(r"__([^_]+)__", r"\1", text)
    text = re.sub(r"\*([^*\s][^*]*)\*", r"\1", text)  # 斜体
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)  # 列表
    return text.strip()
