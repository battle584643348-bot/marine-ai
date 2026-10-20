"""文档管理 API：上传 / 列表 / 删除 / 重建索引。"""
import asyncio
import shutil
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

router = APIRouter(prefix="/api/documents", tags=["documents"])

ALLOWED = {".pdf", ".docx", ".xlsx", ".xlsm", ".txt", ".md", ".markdown", ".csv", ".log"}


@router.get("")
async def list_documents(request: Request):
    index = request.app.state.index
    return {"documents": index.list_documents(), "total_chunks": len(index.chunks)}


@router.post("/upload")
async def upload_documents(request: Request, files: List[UploadFile] = File(...)):
    index = request.app.state.index
    embed_fn = request.app.state.embed_fn
    cfg = request.app.state.cfg
    upload_dir = Path(cfg.paths()["uploads"])
    upload_dir.mkdir(parents=True, exist_ok=True)

    added, errors = [], []
    for f in files:
        suffix = Path(f.filename or "").suffix.lower()
        if suffix not in ALLOWED:
            errors.append({"name": f.filename, "error": f"不支持的类型 {suffix}"})
            continue
        dest = upload_dir / (f.filename or "upload")
        try:
            with open(dest, "wb") as out:
                shutil.copyfileobj(f.file, out)
            meta = await asyncio.to_thread(
                index.add_document, dest, embed_fn,
                int(cfg.get("rag.chunk_size", 800)), int(cfg.get("rag.chunk_overlap", 120)),
            )
            added.append({"doc_id": meta.doc_id, "name": meta.name, "num_chunks": meta.num_chunks})
        except Exception as e:  # noqa: BLE001
            errors.append({"name": f.filename, "error": str(e)})
    return {"added": added, "errors": errors, "total_chunks": len(index.chunks)}


@router.delete("/{doc_id}")
async def delete_document(doc_id: str, request: Request):
    index = request.app.state.index
    if not index.remove_document(doc_id):
        raise HTTPException(404, "文档不存在")
    return {"ok": True}


@router.post("/reindex")
async def reindex(request: Request):
    index = request.app.state.index
    embed_fn = request.app.state.embed_fn
    cfg = request.app.state.cfg
    upload_dir = Path(cfg.paths()["uploads"])
    if upload_dir.exists():
        for p in sorted(upload_dir.iterdir()):
            if p.suffix.lower() in ALLOWED:
                await asyncio.to_thread(
                    index.add_document, p, embed_fn,
                    int(cfg.get("rag.chunk_size", 800)), int(cfg.get("rag.chunk_overlap", 120)),
                )
    return {"ok": True, "total_chunks": len(index.chunks), "documents": index.list_documents()}


@router.get("/{doc_id}/chunks")
async def doc_chunks(doc_id: str, request: Request, limit: int = 3):
    index = request.app.state.index
    doc = index.docs.get(doc_id)
    if not doc:
        raise HTTPException(404, "文档不存在")
    chunks = [c for c in index.chunks if c.doc_id == doc_id][:limit]
    return {"doc_id": doc_id, "name": doc.name, "chunks": [c.text[:800] for c in chunks]}
