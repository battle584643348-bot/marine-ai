"""海工智舱 - FastAPI 应用入口。"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .agent.loop import Agent
from .api import chat as chat_api
from .api import documents as docs_api
from .api import settings as settings_api
from .api import skills as skills_api
from .core.config import get_config
from .core.embeddings import build_embed_fn, build_embed_query_fn
from .core.llm import build_provider
from .rag.index import DocumentIndex
from .skills.registry import SkillRegistry

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

app = FastAPI(title="海工智舱 Marine AI", version="1.0.0")

app.include_router(chat_api.router)
app.include_router(docs_api.router)
app.include_router(skills_api.router)
app.include_router(settings_api.router)

if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


async def _build_runtime():
    cfg = get_config()
    index = DocumentIndex(cfg.paths()["index"])
    index.load()
    registry = SkillRegistry(cfg)
    provider = await build_provider(cfg)
    embed_fn = build_embed_fn(cfg)
    embed_query = build_embed_query_fn(embed_fn)
    agent = Agent(cfg, provider, index, registry, embed_query)
    app.state.cfg = cfg
    app.state.index = index
    app.state.registry = registry
    app.state.provider = provider
    app.state.embed_fn = embed_fn
    app.state.embed_query = embed_query
    app.state.agent = agent
    app.state.rebuild_runtime = _build_runtime
    return cfg


@app.on_event("startup")
async def startup():
    await _build_runtime()
