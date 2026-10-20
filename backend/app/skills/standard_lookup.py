"""技能：海工/电气标准速查（内置索引，正式引用以官方原文为准）。"""
import json
from pathlib import Path
from typing import Any, Dict, List

from .base import Skill

_STD_FILE = Path(__file__).resolve().parents[3] / "data" / "standards.json"


class StandardLookupSkill(Skill):
    name = "standard_lookup"
    title = "标准速查"
    description = (
        "查询海工、船舶、电气、继电保护、谐波、电缆等相关国际/国家标准（IEC、IEEE、GB/T、ASME、API 等）的"
        "适用范围、关键要求与条款定位。适合用户询问'XX标准怎么规定''查一下XX标准号/限值'的场景。"
        "注意：结果为速查定位参考，条文原文以最新官方版本为准。"
    )
    parameters = [
        {"name": "keyword", "type": "string", "description": "标准号或主题关键词，如 'IEC 61800'、'谐波'、'电缆载流量'", "required": True},
    ]

    def _load(self) -> List[dict]:
        if not _STD_FILE.exists():
            return []
        return json.loads(_STD_FILE.read_text(encoding="utf-8"))

    async def run(self, ctx, args: Dict[str, Any]) -> Dict[str, Any]:
        keyword = str(args.get("keyword", "")).strip().lower()
        if not keyword:
            return {"type": "text", "content": "缺少检索关键词（keyword）。"}
        entries = self._load()
        if not entries:
            return {"type": "text", "content": "标准索引未加载（data/standards.json 缺失）。"}

        scored = []
        for e in entries:
            hay = " ".join([e.get("id", ""), e.get("title", ""), " ".join(e.get("tags", []))]).lower()
            s = 0.0
            if keyword in e.get("id", "").lower():
                s += 3.0
            if keyword in hay:
                s += 2.0
            elif all(c in hay for c in keyword if c.isalnum()):
                s += 1.0
            if s > 0:
                scored.append((s, e))
        scored.sort(key=lambda x: -x[0])
        if not scored:
            return {"type": "text",
                    "content": f"内置索引未收录「{keyword}」。建议：1) 明确标准号或关键词再查；2) 让我联网核实最新版本。"}

        lines = [f"「{keyword}」相关标准速查（共 {len(scored)} 条）：\n"]
        for s, e in scored[:5]:
            lines.append(f"### {e['id']} —— {e['title']}")
            lines.append(f"**适用范围**：{e.get('scope', '')}")
            pts = e.get("key_points", [])
            if pts:
                lines.append("**关键要求**：")
                lines.extend(f"- {p}" for p in pts)
            lines.append("")
        lines.append("> 注：以上为速查定位参考，进行设计/调试/验收引用时，请以最新官方标准原文为准。")
        return {"type": "text", "content": "\n".join(lines), "meta": {"matches": len(scored[:5])}}
