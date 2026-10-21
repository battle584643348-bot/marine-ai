"""配置 / 健康检查 / 生成文件下载 API。"""
import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

# `..` 表示「上一级包」，即 app/core/files.py。
# 绝对导入（from app.core.files import ...）也能跑，但相对导入不受启动目录影响，
# 在 uvicorn 从别的目录启动时更稳。
from ..core.files import resolve_generated_rel

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


@router.get("/files/{file_path:path}")
async def download_file(file_path: str, request: Request):
    """下载 generated/ 目录下的文件，支持子目录。

    【路由声明 `{file_path:path}` 里那个 `:path` 是整个修复的关键】
      FastAPI（底层是 Starlette）的路径参数默认用 `str` 转换器，它的正则大致是
      `[^/]+` —— 遇到斜杠就停。所以旧的 `/files/{filename}` 只能匹配
      `/files/a.pdf`，而 `diagram_mark/a.pdf` 因为有斜杠，整条路由压根匹配不上，
      请求直接 404（连函数都没进）。
      `:path` 换成了 `.*`，允许斜杠，于是多级子目录才能被一个参数吃下来。

    【安全注意】
      放开斜杠等于放开了 `../` 的入口，所以参数一进来就必须过
      resolve_generated_rel 的越界检查 —— 见 core/files.py 里的说明。
      这就是「放宽匹配」和「收紧校验」必须同时做的原因：只放开不校验 = 任意文件读取。
    """
    cfg = request.app.state.cfg
    path = resolve_generated_rel(cfg, file_path)

    # 返回 404 而不是 403：403 等于告诉攻击者"这个文件存在，只是你没权限"，
    # 反而帮他确认了目录结构。404 什么都不透露。
    if path is None:
        raise HTTPException(404, "文件不存在")

    # FileResponse 会自动做三件事：
    #   1. 按扩展名猜 MIME 类型（pdf → application/pdf）
    #   2. 支持 Range 请求（浏览器的 PDF 阅读器要靠它做分段加载）
    #   3. 传了 filename= 就自动加响应头
    #      Content-Disposition: attachment; filename*=utf-8''...
    #      没有 attachment 这个值，Chrome 会在标签页里直接打开 PDF 而不是下载；
    #      而 filename*=utf-8'' 是 RFC 5987 规定的「非 ASCII 文件名」写法，
    #      有了它，中文文件名下载下来才不会变成一串百分号。
    return FileResponse(str(path), filename=path.name)

