"""Agent 运行上下文：供技能与 Agent 循环共享。"""
from typing import List, Optional

from ..core.config import Config
from ..rag.index import DocumentIndex


class AgentContext:
    def __init__(self, cfg: Config, provider, index: DocumentIndex, registry,
                 llm_max_tokens: int = 4096):
        self.cfg = cfg
        self.provider = provider
        self.index = index
        self.registry = registry
        self.llm_max_tokens = llm_max_tokens

    @property
    def paths(self):
        return self.cfg.paths()

    async def llm_call(self, system: str, user: str, temperature: float | None = None) -> str:
        """技能内部需要调用模型时使用（一次性，非流式）。"""
        parts = await self.provider.chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=temperature, max_tokens=self.llm_max_tokens,
        )
        return "".join(parts)

    def search_knowledge(self, query: str, top_k: Optional[int] = None,
                         embed_query=None) -> List[dict]:
        cfg = self.cfg
        k = top_k or int(cfg.get("rag.search_top_k", 8))
        return self.index.search(
            query, top_k=k,
            w_sparse=float(cfg.get("rag.hybrid_weight_sparse", 0.6)),
            w_dense=float(cfg.get("rag.hybrid_weight_dense", 0.4)),
            embed_query=embed_query,
        )
