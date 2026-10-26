"""RAG 知识问答测试：解析、切分、入库、检索问答、引用、无答案阈值。"""

from app.capabilities.rag.chunker import SemanticChunker
from app.capabilities.rag.loader import load, markdown_to_text
from app.capabilities.rag.pipeline import RagPipeline
from app.capabilities.rag.qa import MockAnswerGenerator, RagQA
from app.retrieval.hybrid import HybridRetrieval, SearchResult


# —— Markdown / 解析 ——
def test_markdown_to_text():
    md = "# 标题\n\n**加粗** [链接](http://x) 和 `代码`\n\n- 列表项"
    text = markdown_to_text(md)
    assert "#" not in text
    assert "**" not in text
    assert "[链接](http://x)" not in text
    assert "标题" in text
    assert "加粗" in text


def test_load_text_and_markdown(tmp_path):
    (tmp_path / "a.txt").write_text("纯文本内容", encoding="utf-8")
    (tmp_path / "b.md").write_text("# 标题\n\n正文内容", encoding="utf-8")
    assert load(str(tmp_path / "a.txt"))[0].text == "纯文本内容"
    assert "标题" in load(str(tmp_path / "b.md"))[0].text
    assert load(str(tmp_path / "b.md"))[0].page is None


def test_load_pdf_page(tmp_path):
    from pypdf import PdfWriter

    p = tmp_path / "a.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with open(p, "wb") as f:
        writer.write(f)
    sections = load(str(p))
    assert len(sections) == 1
    assert sections[0].page == 1


# —— 语义切分 ——
def test_semantic_chunker():
    chunker = SemanticChunker(chunk_size=10, overlap=0)
    text = "第一句。第二句！第三句？第四句。第五句。"
    chunks = chunker.split(text)
    assert len(chunks) >= 2  # 多块
    assert all(len(c) <= 10 for c in chunks)  # 每块不超 chunk_size
    assert "第一句" in chunks[0]
    assert "第五句" in chunks[-1]


def test_semantic_chunker_overlap():
    chunker = SemanticChunker(chunk_size=10, overlap=3)
    chunks = chunker.split("一二三四五六七八九十。十一十二十三十四十五。")
    assert len(chunks) >= 2
    assert chunks[1].startswith(chunks[0][-3:])  # 下一块保留上一块末尾 overlap 字符


# —— 入库流水线 ——
class _FakeHybrid:
    def __init__(self):
        self.indexed = []

    def index(self, documents):
        self.indexed.extend(documents)


def test_pipeline_ingest(tmp_path):
    p = tmp_path / "policy.md"
    p.write_text("# 退货政策\n\n七天内可退货。\n\n超过七天不退。", encoding="utf-8")
    fake = _FakeHybrid()
    pipeline = RagPipeline(fake, SemanticChunker(chunk_size=10, overlap=0))
    chunks = pipeline.ingest(str(p), doc_id="policy")
    assert chunks
    for c in chunks:
        assert c.metadata["doc_id"] == "policy"
        assert c.metadata["page"] is None  # markdown 无页码
    assert chunks[0].metadata["index"] == 0


# —— 检索问答 ——
class _FakeRetriever:
    def __init__(self, results):
        self.results = results

    def retrieve(self, query, top_k):
        return self.results[:top_k]


class _PassReranker:
    def rerank(self, query, candidates, top_k):
        return candidates[:top_k]


def _mk(chunk_id, doc_id, text, score=0.8):
    return SearchResult(
        id=chunk_id, text=text, score=score,
        metadata={"doc_id": doc_id, "page": None, "index": 0},
    )


def _qa(results, *, threshold=0.0, top_k=2):
    hybrid = HybridRetrieval(
        retrievers=[_FakeRetriever(results)], reranker=_PassReranker()
    )
    return RagQA(hybrid, generator=MockAnswerGenerator(), top_k=top_k, score_threshold=threshold)


def test_rag_qa_answer_with_citations():
    qa = _qa([
        _mk("p#0", "policy", "七天内可退货"),
        _mk("p#1", "policy", "超过七天不退"),
    ])
    ans = qa.answer("退货政策")
    assert not ans.no_answer
    assert "[1]" in ans.text and "[2]" in ans.text  # 引用标注
    assert len(ans.sources) == 2
    assert ans.sources[0].doc_id == "policy"  # [1] → sources[0]，可追溯


def test_rag_qa_no_answer_below_threshold():
    qa = _qa([_mk("p#0", "policy", "不相关内容", score=0.1)], threshold=0.5)
    ans = qa.answer("问题")
    assert ans.no_answer is True
    assert ans.sources == []


def test_rag_qa_no_answer_when_empty():
    qa = _qa([])
    ans = qa.answer("问题")
    assert ans.no_answer is True
