"""技能：知识库深度检索。"""
from typing import Any, Dict

from .base import Skill


class KnowledgeSearchSkill(Skill):
    name = "knowledge_search"
    title = "知识库检索"
    description = (
        "在已上传的海工/船舶技术文档知识库中进行检索，返回与关键词相关的原文片段及来源。"
        "适合用户要求'查一下知识库/资料里关于XX的内容'、需要原文依据的场景。"
    )
    parameters = [
        {"name": "query", "type": "string", "description": "检索关键词或问题，尽量使用原文中的专业术语", "required": True},
        {"name": "top_k", "type": "number", "description": "返回片段条数，默认 6", "required": False},
    ]

    async def run(self, ctx, args: Dict[str, Any]) -> Dict[str, Any]:
        query = str(args.get("query", "")).strip()
        if not query:
            return {"type": "text", "content": "缺少检索关键词（query）。"}
        top_k = int(args.get("top_k") or 6)
        hits = ctx.search_knowledge(query, top_k=top_k)
        if not hits:
            return {
                "type": "text",
                "content": f"知识库未命中「{query}」。当前库共 {len(ctx.index.chunks)} 个片段。"
                           "建议：1) 先上传相关技术文档；2) 换用更贴近原文的术语重试。",
            }
        lines = [f"知识库命中 {len(hits)} 条（相关度由高到低）：\n"]
        for h in hits:
            doc = ctx.index.docs.get(h["doc_id"])
            name = doc.name if doc else "?"
            lines.append(f"### [{name}]（相关度 {h['score']}）\n{h['text']}\n")
        return {"type": "text", "content": "\n".join(lines),
                "meta": {"hits": len(hits)}}
