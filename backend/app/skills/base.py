"""技能基类：每个技能向模型暴露 name/title/description/parameters。"""
from typing import Any, Dict, List


class Skill:
    name: str = ""
    title: str = ""
    description: str = ""
    # 参数 Schema：[{name, type: "string"|"number"|"boolean", description, required, enum?}]
    parameters: List[Dict[str, Any]] = []

    async def run(self, ctx, args: Dict[str, Any]) -> Dict[str, Any]:
        """返回 {"type": "text"|"file"|"table", "content": str, "meta": {...}}"""
        raise NotImplementedError

    def brief(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "parameters": self.parameters,
        }
