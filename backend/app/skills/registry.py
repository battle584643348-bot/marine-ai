"""技能注册表：自动发现技能模块，管理启停状态（持久化到 user_config）。"""
import importlib
import pkgutil
from pathlib import Path
from typing import Dict, List, Optional

from ..core.config import Config
from .base import Skill

_PACKAGE = __name__.rsplit(".", 1)[0]  # backend.app.skills


class SkillRegistry:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._skills: Dict[str, Skill] = {}
        self._enabled: List[str] = []
        self._discover()
        self._load_enabled()

    def _discover(self):
        pkg_dir = Path(__file__).parent
        for mod in pkgutil.iter_modules([str(pkg_dir)]):
            if mod.name.startswith("_") or mod.name == "base":
                continue
            module = importlib.import_module(f"{_PACKAGE}.{mod.name}")
            for attr in vars(module).values():
                if isinstance(attr, type) and issubclass(attr, Skill) and attr is not Skill and attr.name:
                    self._skills[attr.name] = attr()

    def _load_enabled(self):
        configured = self.cfg.get("skills.enabled", None)
        if isinstance(configured, list) and configured:
            self._enabled = [n for n in configured if n in self._skills]
        else:
            self._enabled = list(self._skills.keys())

    def persist_enabled(self):
        self.cfg.set("skills.enabled", list(self._enabled))

    # --------------------------------------------- 查询
    def all(self) -> List[Skill]:
        return list(self._skills.values())

    def get(self, name: str) -> Optional[Skill]:
        return self._skills.get(name)

    def enabled_names(self) -> List[str]:
        return list(self._enabled)

    def is_enabled(self, name: str) -> bool:
        return name in self._enabled

    def enabled_skills(self) -> List[Skill]:
        return [self._skills[n] for n in self._enabled if n in self._skills]

    # --------------------------------------------- 启停
    def toggle(self, name: str) -> bool:
        if name not in self._skills:
            return False
        if name in self._enabled:
            self._enabled.remove(name)
        else:
            self._enabled.append(name)
        self.persist_enabled()
        return True

    def list_with_state(self) -> List[Dict]:
        out = []
        for s in self._skills.values():
            b = s.brief()
            b["enabled"] = s.name in self._enabled
            out.append(b)
        return out
