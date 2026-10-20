"""语义向量封装（可选）：依赖 Ollama /api/embed，不可用时整体回退关键词检索。"""
from typing import Callable, List, Optional

import httpx


def build_embed_fn(cfg) -> Optional[Callable[[List[str]], Optional[List[List[float]]]]]:
    """构建稠密向量函数 embed(texts)->[[float]]；Ollama embedding 未启用/不可达时返回 None。"""
    enabled = bool(cfg.get("llm.ollama.embedding_enabled", False))
    if not enabled:
        return None
    base_url = cfg.get("llm.ollama.base_url", "http://127.0.0.1:11434").rstrip("/")
    model = cfg.get("llm.ollama.embedding_model", "bge-m3")

    def embed(texts: List[str]) -> Optional[List[List[float]]]:
        try:
            with httpx.Client(timeout=httpx.Timeout(300, connect=5)) as client:
                resp = client.post(f"{base_url}/api/embed", json={"model": model, "input": texts})
            resp.raise_for_status()
            return resp.json().get("embeddings")
        except Exception:  # noqa: BLE001
            return None

    return embed


def build_embed_query_fn(embed_fn) -> Optional[Callable[[str], Optional[List[float]]]]:
    if embed_fn is None:
        return None
    def embed_query(text: str) -> Optional[List[float]]:
        res = embed_fn([text])
        return res[0] if res else None
    return embed_query
