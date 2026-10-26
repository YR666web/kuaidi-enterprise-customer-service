"""知识库管理服务：上传 → 解析 → 切分 → 向量化入库 → 预览 / 删除 / 检索。"""

import os
import tempfile
import uuid

from app.capabilities.rag import build_rag_service
from app.db.session import SessionLocal
from app.models.knowledge import (
    KnowledgeDocument,
    KnowledgeDocumentTenant,
    KnowledgeDocumentVersion,
)
from app.retrieval.hybrid import BM25Retriever, Document, VectorRetriever


class KnowledgeService:
    """知识库 CRUD + 检索问答。"""

    def __init__(self) -> None:
        rag = build_rag_service()
        self.pipeline = rag.pipeline
        self.qa = rag.qa
        self.hybrid = self.pipeline.hybrid

        self.collection = None
        self.bm25 = None
        for retriever in self.hybrid.retrievers:
            if isinstance(retriever, VectorRetriever):
                self.collection = retriever.collection
            elif isinstance(retriever, BM25Retriever):
                self.bm25 = retriever

        # 启动时从 Chroma 重建 BM25（BM25 为内存态，重启后需恢复）
        self._rebuild_bm25()

    def upload(self, content: bytes, filename: str, tenant_id: str = "default") -> dict:
        """上传文档：解析、切分、向量化入库，并记录元信息。"""
        ext = os.path.splitext(filename)[1].lower()
        doc_id = uuid.uuid4().hex[:12]
        doc_type = {
            ".pdf": "pdf", ".md": "markdown", ".markdown": "markdown", ".txt": "text",
        }.get(ext, "text")

        # PDF 解析需要文件路径，先落临时文件，入库后删除
        tmp = tempfile.NamedTemporaryFile(suffix=ext or ".txt", delete=False)
        try:
            tmp.write(content)
            tmp.close()
            chunks = self.pipeline.ingest(tmp.name, doc_id=doc_id, tenant_id=tenant_id)
        finally:
            os.unlink(tmp.name)

        with SessionLocal() as db:
            doc = KnowledgeDocument(
                doc_id=doc_id,
                name=filename,
                type=doc_type,
                size=len(content),
                chunks=len(chunks),
                status="ready",
            )
            db.add(doc)
            db.add(KnowledgeDocumentVersion(
                doc_id=doc_id, version=1, name=filename, size=len(content), chunks=len(chunks)
            ))
            db.add(KnowledgeDocumentTenant(doc_id=doc_id, tenant_id=tenant_id))
            db.commit()
            db.refresh(doc)
            return self._to_dict(doc)

    def list_documents(self, tenant_id: str = "default") -> list[dict]:
        with SessionLocal() as db:
            docs = (
                db.query(KnowledgeDocument)
                .join(
                    KnowledgeDocumentTenant,
                    KnowledgeDocument.doc_id == KnowledgeDocumentTenant.doc_id,
                )
                .filter(KnowledgeDocumentTenant.tenant_id == tenant_id)
                .order_by(KnowledgeDocument.uploaded_at.desc())
                .all()
            )
            return [self._to_dict(d) for d in docs]

    def preview(self, doc_id: str, tenant_id: str = "default") -> list[dict]:
        """返回文档的 chunk 片段列表（按 index 排序）。"""
        if self.collection is None:
            return []
        data = self.collection.get(
            where={"$and": [{"doc_id": doc_id}, {"tenant_id": tenant_id}]},
            include=["documents", "metadatas"],
        )
        result = []
        for i, text in enumerate(data.get("documents", [])):
            meta = (data.get("metadatas") or [{}])[i] or {}
            result.append({"index": meta.get("index"), "page": meta.get("page"), "text": text})
        result.sort(key=lambda x: (x["index"] is None, x["index"] or 0))
        return result

    def delete(self, doc_id: str, tenant_id: str = "default") -> bool:
        with SessionLocal() as db:
            scoped = db.query(KnowledgeDocumentTenant).filter(
                KnowledgeDocumentTenant.doc_id == doc_id,
                KnowledgeDocumentTenant.tenant_id == tenant_id,
            ).first()
            deleted = 0
            if scoped:
                deleted = db.query(KnowledgeDocument).filter(
                    KnowledgeDocument.doc_id == doc_id
                ).delete()
                db.delete(scoped)
            db.commit()
        if deleted and self.collection is not None:
            self.collection.delete(where={"$and": [{"doc_id": doc_id}, {"tenant_id": tenant_id}]})
            self._rebuild_bm25()
        return bool(deleted)

    def replace(
        self, doc_id: str, content: bytes, filename: str, tenant_id: str = "default"
    ) -> dict | None:
        """原地更新文档，保留 doc_id，避免引用链接失效。"""
        ext = os.path.splitext(filename)[1].lower()
        with SessionLocal() as db:
            scoped = db.query(KnowledgeDocumentTenant).filter(
                KnowledgeDocumentTenant.doc_id == doc_id,
                KnowledgeDocumentTenant.tenant_id == tenant_id,
            ).first()
            doc = (
                db.query(KnowledgeDocument).filter(KnowledgeDocument.doc_id == doc_id).first()
                if scoped else None
            )
            if doc is None:
                return None
            if self.collection is not None:
                self.collection.delete(where={"doc_id": doc_id})
            tmp = tempfile.NamedTemporaryFile(suffix=ext or ".txt", delete=False)
            try:
                tmp.write(content)
                tmp.close()
                chunks = self.pipeline.ingest(tmp.name, doc_id=doc_id, tenant_id=tenant_id)
            finally:
                os.unlink(tmp.name)
            doc.name = filename
            doc.type = {
                ".pdf": "pdf", ".md": "markdown", ".markdown": "markdown", ".txt": "text",
            }.get(ext, "text")
            doc.size = len(content)
            doc.chunks = len(chunks)
            doc.status = "ready"
            latest = (
                db.query(KnowledgeDocumentVersion)
                .filter(KnowledgeDocumentVersion.doc_id == doc_id)
                .order_by(KnowledgeDocumentVersion.version.desc())
                .first()
            )
            db.add(KnowledgeDocumentVersion(
                doc_id=doc_id,
                version=(latest.version + 1 if latest else 1),
                name=filename,
                size=len(content),
                chunks=len(chunks),
            ))
            db.commit()
            db.refresh(doc)
            self._rebuild_bm25()
            return self._to_dict(doc)

    def versions(self, doc_id: str, tenant_id: str = "default") -> list[dict]:
        with SessionLocal() as db:
            belongs_to_tenant = db.query(KnowledgeDocumentTenant).filter(
                KnowledgeDocumentTenant.doc_id == doc_id,
                KnowledgeDocumentTenant.tenant_id == tenant_id,
            ).first()
            if belongs_to_tenant is None:
                return []
            rows = (
                db.query(KnowledgeDocumentVersion)
                .filter(KnowledgeDocumentVersion.doc_id == doc_id)
                .order_by(KnowledgeDocumentVersion.version.desc())
                .all()
            )
            return [
                {
                    "docId": row.doc_id,
                    "version": row.version,
                    "name": row.name,
                    "size": row.size,
                    "chunks": row.chunks,
                    "createdAt": int(row.created_at.timestamp() * 1000),
                }
                for row in rows
            ]

    def ask(self, question: str, tenant_id: str = "default") -> dict:
        ans = self.qa.answer(question, tenant_id=tenant_id)
        return {
            "text": ans.text,
            "no_answer": ans.no_answer,
            "sources": [
                {"doc_id": s.doc_id, "snippet": s.snippet, "page": s.page} for s in ans.sources
            ],
        }

    def _rebuild_bm25(self) -> None:
        """删除文档后，从 Chroma 重新读取全部 chunk，重建 BM25 索引。"""
        if self.bm25 is None or self.collection is None:
            return
        data = self.collection.get(include=["documents", "metadatas"])
        docs = [
            Document(
                id=data["ids"][i],
                text=data["documents"][i],
                metadata=(data.get("metadatas") or [{}])[i] or {},
            )
            for i in range(len(data.get("ids", [])))
        ]
        self.bm25.index(docs)

    @staticmethod
    def _to_dict(doc: KnowledgeDocument) -> dict:
        return {
            "id": doc.doc_id,
            "name": doc.name,
            "type": doc.type,
            "size": doc.size,
            "chunks": doc.chunks,
            "status": doc.status,
            "uploadedAt": int(doc.uploaded_at.timestamp() * 1000),
        }


# 模块级单例：上传/检索时懒加载向量模型
knowledge_service = KnowledgeService()
