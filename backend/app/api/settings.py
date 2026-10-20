"""配置 / 健康检查 / 生成文件下载 API。"""
import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["settings"])


class ConfigPatch(BaseModel):
    patch: Dict[str, Any]


def _mask(cfg_raw: Dict) -> Dict:
    import copy
    out = copy.deepcopy(cfg_raw)
    key = out.get("llm", {}).get("openai_compatible", {}).get("api_key", "")
    if key:
        out["llm"]["openai_compatible"]["api_key"] = "***" if key else ""
    return out


@router.get("/config")
async def get_config(request: Request):
    cfg = request.app.state.cfg
    return _mask(cfg.raw())


@router.post("/config")
async def save_config(req: ConfigPatch, request: Request):
    cfg = request.app.state.cfg
    patch = req.patch or {}
    # API Key 保持 *** 视为未修改
    llm = patch.get("llm")
    if llm:
        oa = llm.get("openai_compatible")
        if oa and oa.get("api_key") == "***":
            oa["api_key"] = cfg.get("llm.openai_compatible.api_key", "")
    cfg.set_many(patch)
    app = request.app
    await app.state.rebuild_runtime()
    return {"ok": True, "config": _mask(cfg.raw())}


@router.get("/health")
async def health(request: Request):
    app = request.app
    provider = app.state.provider
    llm_ok, llm_detail = await provider.check()
    cfg = app.state.cfg
    return {
        "llm": {"provider": provider.name, "model": getattr(provider, "model", ""),
                "ok": llm_ok, "detail": llm_detail},
        "rag": {"documents": len(app.state.index.docs), "chunks": len(app.state.index.chunks),
                "embedding": bool(app.state.embed_fn)},
        "skills": {"count": len(app.state.registry.all()),
                   "enabled": app.state.registry.enabled_names()},
        "server": {"host": cfg.get("server.host"), "port": cfg.get("server.port")},
    }


@router.get("/files/{filename}")
async def download_file(filename: str, request: Request):
    cfg = request.app.state.cfg
    base = __import__("pathlib").Path(cfg.paths()["generated"])
    path = (base / filename).resolve()
    if not str(path).startswith(str(base.resolve())) or not path.exists():
        raise HTTPException(404, "文件不存在")
    return FileResponse(str(path), filename=path.name)
