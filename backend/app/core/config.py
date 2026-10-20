"""配置加载：config.yaml 为基础，data/user_config.yaml 运行时可覆盖。"""
import copy
import os
from pathlib import Path
from typing import Any, Dict

import yaml

ROOT = Path(__file__).resolve().parents[3]          # marine-ai/
BACKEND_DIR = Path(__file__).resolve().parents[2]   # marine-ai/backend
DATA_DIR = ROOT / "data"
USER_CONFIG_PATH = DATA_DIR / "user_config.yaml"
GENERATED_DIR = ROOT / "generated"

_lock = None


class Config:
    def __init__(self, base_path: Path):
        with open(base_path, "r", encoding="utf-8") as f:
            self._base = yaml.safe_load(f) or {}
        self._user: Dict[str, Any] = {}
        self.reload_user()

    # ---------- 读取 ----------
    def reload_user(self):
        if USER_CONFIG_PATH.exists():
            with open(USER_CONFIG_PATH, "r", encoding="utf-8") as f:
                self._user = yaml.safe_load(f) or {}
        else:
            self._user = {}

    def get(self, dotted: str, default: Any = None) -> Any:
        """支持 'llm.ollama.model' 形式的点路径取值，user 配置优先。"""
        merged = _deep_merge(copy.deepcopy(self._base), copy.deepcopy(self._user))
        node: Any = merged
        for part in dotted.split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return default
        return node

    def raw(self) -> Dict[str, Any]:
        return _deep_merge(copy.deepcopy(self._base), copy.deepcopy(self._user))

    # ---------- 写入（仅写 user 覆盖层，保留原始 config.yaml） ----------
    def set(self, dotted: str, value: Any):
        keys = dotted.split(".")
        node = self._user
        for k in keys[:-1]:
            node = node.setdefault(k, {})
        node[keys[-1]] = value
        self.save()

    def set_many(self, patch: Dict[str, Any]):
        self._user = _deep_merge(self._user, patch)
        self.save()

    def save(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(USER_CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.safe_dump(self._user, f, allow_unicode=True, sort_keys=False)

    def paths(self):
        return {
            "data": str(DATA_DIR),
            "uploads": str(ROOT / self.get("rag.upload_dir", "data/uploads")),
            "index": str(ROOT / self.get("rag.index_path", "data/index.json")),
            "generated": str(GENERATED_DIR),
            "sample": str(DATA_DIR / "sample"),
        }


def _deep_merge(base: Dict, override: Dict) -> Dict:
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


_config: Config | None = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config(ROOT / "config.yaml")
    return _config


def api_key_from_env(cfg: Config) -> str:
    """api_key 优先级：环境变量 > 配置文件。"""
    env_key = os.environ.get("MARINE_LLM_API_KEY")
    if env_key:
        return env_key
    return cfg.get("llm.openai_compatible.api_key", "") or ""
