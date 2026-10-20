"""Agent 循环：RAG 上下文注入 → 模型流式输出 → 技能调用协议 → 循环直至给出最终答案。

技能调用协议：模型如需调用技能，仅输出一行 JSON（允许包裹在 ```json 代码块中）：
    {"tool": "<skill_name>", "args": {...}}
无需技能时直接输出最终回答。技能结果以 [技能执行结果] 消息回灌，继续循环（上限 max_tool_rounds）。
"""
import json
import re
from pathlib import Path
from typing import AsyncIterator, Dict, List, Optional

from ..core.config import Config
from ..rag.index import DocumentIndex
from ..skills.registry import SkillRegistry
from .context import AgentContext

_SESSIONS: Dict[str, List[dict]] = {}
_JSON_BLOCK = re.compile(r"```(?:json)?\s*(.*?)```", re.S)
_BRANCHES_FILE = Path(__file__).resolve().parents[3] / "data" / "branches.json"
_DEFAULT_BRANCH = "overall"


class Agent:
    def __init__(self, cfg: Config, provider, index: DocumentIndex, registry: SkillRegistry,
                 embed_query=None):
        self.cfg = cfg
        self.provider = provider
        self.index = index
        self.registry = registry
        self.embed_query = embed_query
        self.ctx = AgentContext(cfg, provider, index, registry,
                                llm_max_tokens=int(cfg.get("llm.max_tokens", 4096)))
        self.max_rounds = int(cfg.get("agent.max_tool_rounds", 4))
        self.branches = self._load_branches()

    # ------------------------------------------------ 分支
    @staticmethod
    def _load_branches() -> List[dict]:
        if not _BRANCHES_FILE.exists():
            return []
        try:
            return json.loads(_BRANCHES_FILE.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return []

    def get_branch(self, branch_id: str) -> dict:
        branch_id = branch_id or _DEFAULT_BRANCH
        for b in self.branches:
            if b.get("id") == branch_id:
                return b
        return {"id": _DEFAULT_BRANCH, "name": "综合助手", "icon": "⚓",
                "desc": "", "skills": [], "prompt": ""}

    def branch_skills(self, branch_id: str) -> List:
        branch = self.get_branch(branch_id)
        allowed = set(branch.get("skills") or [])
        if not allowed:
            return []
        return [s for s in self.registry.enabled_skills() if s.name in allowed]

    @staticmethod
    def _session_key(session_id: str, branch: str) -> str:
        return f"{session_id}::{branch or _DEFAULT_BRANCH}"

    # ------------------------------------------------ 会话
    def get_history(self, session_id: str, branch: str = _DEFAULT_BRANCH) -> List[dict]:
        return _SESSIONS.get(self._session_key(session_id, branch), [])

    def _push(self, key: str, role: str, content: str):
        _SESSIONS.setdefault(key, []).append({"role": role, "content": content})
        turns = int(self.cfg.get("agent.history_turns", 12))
        if len(_SESSIONS[key]) > turns * 2 + 4:
            _SESSIONS[key] = _SESSIONS[key][-turns * 2:]

    def clear_session(self, session_id: str, branch: str = _DEFAULT_BRANCH):
        _SESSIONS.pop(self._session_key(session_id, branch), None)

    # ------------------------------------------------ 系统提示
    def _system_prompt(self, context_text: str = "", branch: str = _DEFAULT_BRANCH) -> str:
        branch_def = self.get_branch(branch)
        branch_prompt = branch_def.get("prompt", "")
        skills = self.branch_skills(branch)
        skill_lines = []
        for s in skills:
            params = ", ".join(f"{p['name']}({p.get('type','string')})" for p in s.parameters)
            skill_lines.append(f'- name: {s.name} | title: {s.title} | 参数: {params} | 说明: {s.description}')
        skill_text = "\n".join(skill_lines) if skill_lines else "（当前分支未启用技能，请直接以专业知识回答）"
        ctx_block = (
            "\n\n【知识库上下文】（仅作依据，可能有噪音，引用时标注来源文件名）\n" + context_text
            if context_text else ""
        )
        return (
            f"你是「海工智舱」的【{branch_def.get('name','综合助手')}】分支。\n"
            f"分支定位：{branch_prompt or branch_def.get('desc','')}\n"
            "行为准则：\n"
            "1. 专业严谨：涉及电气/机械/仪表/结构问题给出可执行依据与数值，不编造标准条款（引用标准只写标准号与适用主题，注明以最新官方版本为准）。\n"
            "2. 技能调用：以下技能可帮助你完成任务。若用户请求可用技能完成（检索知识库、标准速查、工程计算、生成SOP/ITR、中英翻译、生成Excel表格），"
            "第一轮回复必须**仅输出一行 JSON**（可包在```json中），格式 {\"tool\":\"<技能name>\",\"args\":{...}}，不要附带任何其他文字。\n"
            "3. 无需技能时直接给出最终答案。\n"
            "4. 引用知识库内容时在句末标注 [来源:文件名]。\n"
            "5. 用与用户一致的语言回复；输出 Markdown；数值结果给公式与过程。\n\n"
            f"【可用技能】\n{skill_text}{ctx_block}"
        )

    # ------------------------------------------------ 主循环
    async def run_turn(self, session_id: str, user_message: str,
                       branch: str = _DEFAULT_BRANCH) -> AsyncIterator[dict]:
        key = self._session_key(session_id, branch)
        # RAG 自动接地
        sources: List[str] = []
        if self.index.chunks:
            hits = self.index.search(
                user_message, top_k=int(self.cfg.get("rag.top_k", 5)),
                w_sparse=float(self.cfg.get("rag.hybrid_weight_sparse", 0.6)),
                w_dense=float(self.cfg.get("rag.hybrid_weight_dense", 0.4)),
                embed_query=self.embed_query,
            )
            if hits:
                lines = []
                for h in hits:
                    doc = self.index.docs.get(h["doc_id"])
                    name = doc.name if doc else "?"
                    lines.append(f"[{name}] {h['text'][:600]}")
                    if name not in sources:
                        sources.append(name)
                yield {"type": "grounding", "sources": sources}
                context_text = "\n\n".join(lines)
            else:
                context_text = ""
        else:
            context_text = ""

        history = self.get_history(session_id, branch)
        messages: List[dict] = [{"role": "system", "content": self._system_prompt(context_text, branch)}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_message})
        self._push(key, "user", user_message)

        used_tools: List[str] = []
        final_sources = list(sources)
        tool_round = 0

        while True:
            # 阶段1：流式输出并收集
            buffer: List[str] = []
            try:
                async for piece in self.provider.stream(messages,
                                                        temperature=self.cfg.get("llm.temperature", 0.3),
                                                        max_tokens=self.cfg.get("llm.max_tokens", 4096)):
                    buffer.append(piece)
                    yield {"type": "token", "text": piece}
            except Exception as e:  # noqa: BLE001
                yield {"type": "error", "message": f"模型调用失败：{e}。请检查「设置」中的模型配置。"}
                return

            reply = "".join(buffer).strip()
            call = self._parse_tool_call(reply)

            if call and tool_round < self.max_rounds:
                tool_round += 1
                skill_name = call.get("tool", "")
                skill = self.registry.get(skill_name) if self.registry.is_enabled(skill_name) else None
                if skill is None:
                    yield {"type": "error",
                           "message": f"技能 {skill_name} 不存在或未启用（可在「技能」面板开启）。"}
                    return
                args = call.get("args") or {}
                used_tools.append(skill_name)
                yield {"type": "tool_start", "skill": skill_name, "title": skill.title, "args": args}
                try:
                    result = await skill.run(self.ctx, args)
                except Exception as e:  # noqa: BLE001
                    result = {"type": "text", "content": f"[技能执行错误] {e}"}
                preview = result.get("content", "")
                yield {"type": "tool_end", "skill": skill_name, "title": skill.title,
                       "summary": preview[:400]}
                messages.append({"role": "user", "content": f"[技能「{skill_name}」执行结果]\n{preview}"})
                self._push(key, "assistant", f"（已调用技能：{skill_name}）")
                continue

            # 最终答案（或超限兜底）
            if tool_round >= self.max_rounds and call:
                yield {"type": "token", "text": "\n（技能调用次数已达上限，以上为已获取的结果摘要。）"}
            self._push(key, "assistant", reply)
            yield {"type": "done", "sources": final_sources, "tools": used_tools}
            return

    # ------------------------------------------------ 解析
    def _parse_tool_call(self, reply: str) -> Optional[Dict]:
        if not reply:
            return None
        candidates = []
        for block in _JSON_BLOCK.findall(reply):
            candidates.append(block.strip())
        candidates.append(reply.strip())
        for cand in candidates:
            if not cand.startswith("{"):
                continue
            try:
                obj = json.loads(cand)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and obj.get("tool"):
                return obj
        return None
