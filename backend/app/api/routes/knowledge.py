"""知识库管理 API：上传 / 列表 / 预览 / 删除 / 检索问答。"""

import fastapi
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.platform.rbac import Permission, require_permission
from app.services.knowledge import knowledge_service

router = APIRouter(prefix="/knowledge", tags=["knowledge"])
_knowledge_read = fastapi.Depends(require_permission(Permission.KNOWLEDGE_READ))
_knowledge_write = fastapi.Depends(require_permission(Permission.KNOWLEDGE_WRITE))


class AskRequest(BaseModel):
    question: str


@router.post("/documents")
async def upload_document(
    file: UploadFile = File(...),
    tenant=_knowledge_write,
) -> dict:
    """上传文档：解析 → 切分 → 向量化入库。"""
    filename = file.filename
    if not filename:
        raise HTTPException(status_code=400, detail="缺少文件名")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="文件为空")
    return knowledge_service.upload(content, filename, tenant.tenant_id)


@router.get("/documents")
def list_documents(tenant=_knowledge_read) -> list[dict]:
    """文档列表。"""
    return knowledge_service.list_documents(tenant.tenant_id)


@router.get("/documents/{doc_id}")
def preview_document(
    doc_id: str, tenant=_knowledge_read
) -> dict:
    """文档内容预览（chunk 片段列表）。"""
    chunks = knowledge_service.preview(doc_id, tenant.tenant_id)
    if not chunks:
        raise HTTPException(status_code=404, detail="文档不存在或尚未入库")
    return {"chunks": chunks}


@router.delete("/documents/{doc_id}")
def delete_document(
    doc_id: str, tenant=_knowledge_write
) -> dict:
    """删除文档（元信息 + Chroma chunk + 重建 BM25）。"""
    if not knowledge_service.delete(doc_id, tenant.tenant_id):
        raise HTTPException(status_code=404, detail="文档不存在")
    return {"ok": True}


@router.put("/documents/{doc_id}")
async def replace_document(
    doc_id: str,
    file: UploadFile = File(...),
    tenant=_knowledge_write,
) -> dict:
    """更新文档内容并保留原文档 ID。"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="缺少文件名")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="文件为空")
    result = knowledge_service.replace(doc_id, content, file.filename, tenant.tenant_id)
    if result is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    return result


@router.get("/documents/{doc_id}/versions")
def document_versions(doc_id: str, tenant=_knowledge_read) -> list[dict]:
    return knowledge_service.versions(doc_id, tenant.tenant_id)


@router.post("/ask")
def ask(req: AskRequest, tenant=_knowledge_read) -> dict:
    """检索问答（用于验证知识库检索）。"""
    return knowledge_service.ask(req.question, tenant.tenant_id)
