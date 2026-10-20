"""LLM 提供方抽象：Ollama（本地）/ OpenAI 兼容接口 / Mock（离线联调）。

统一异步接口：
    async def chat(messages) -> list[str]         # 一次性返回
    async def stream(messages) -> AsyncIterator[str]  # 逐片增量
    async def check() -> (ok, detail)
"""
import asyncio
import json
from typing import AsyncIterator, List, Optional

import httpx

from .config import Config, api_key_from_env


class LLMProvider:
    name = "base"
    label = "Base"

    async def chat(self, messages: List[dict], temperature: float | None = None,
                   max_tokens: int | None = None) -> List[str]:
        parts = []
        async for p in self.stream(messages, temperature, max_tokens):
            parts.append(p)
        return parts

    async def stream(self, messages: List[dict], temperature: float | None = None,
                     max_tokens: int | None = None) -> AsyncIterator[str]:
        raise NotImplementedError

    async def check(self) -> tuple[bool, str]:
        raise NotImplementedError


# ---------------------------------------------------------------- Ollama
class OllamaProvider(LLMProvider):
    name = "ollama"
    label = "Ollama（本地）"

    def __init__(self, base_url: str, model: str, temperature: float = 0.3):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature

    async def stream(self, messages, temperature=None, max_tokens=None):
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": {"temperature": temperature if temperature is not None else self.temperature},
        }
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
        async with httpx.AsyncClient(timeout=httpx.Timeout(300, connect=5)) as client:
            async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if obj.get("error"):
                        raise RuntimeError(f"Ollama: {obj['error']}")
                    piece = obj.get("message", {}).get("content", "")
                    if piece:
                        yield piece
                    if obj.get("done"):
                        break

    async def check(self):
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(4, connect=2)) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
            resp.raise_for_status()
            names = [m.get("name", "") for m in resp.json().get("models", [])]
            hit = self.model in names or any(n.startswith(self.model) for n in names)
            return True, f"Ollama 可达；模型 {self.model} {'已安装' if hit else '未安装（请执行 ollama pull ' + self.model + '）'}"
        except Exception as e:  # noqa: BLE001
            return False, f"Ollama 不可达：{e}"

    async def embed(self, texts: List[str], model: str) -> Optional[List[List[float]]]:
        """可选语义向量；不可用时返回 None，调用方回退关键词检索。"""
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(120, connect=5)) as client:
                resp = await client.post(f"{self.base_url}/api/embed", json={"model": model, "input": texts})
            resp.raise_for_status()
            return resp.json().get("embeddings")
        except Exception:  # noqa: BLE001
            return None


# ------------------------------------------------- OpenAI 兼容接口
class OpenAICompatProvider(LLMProvider):
    name = "openai"
    label = "OpenAI 兼容接口"

    def __init__(self, base_url: str, api_key: str, model: str, temperature: float = 0.3):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.temperature = temperature

    def _headers(self):
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    async def stream(self, messages, temperature=None, max_tokens=None):
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "temperature": temperature if temperature is not None else self.temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        async with httpx.AsyncClient(timeout=httpx.Timeout(300, connect=10)) as client:
            async with client.stream("POST", f"{self.base_url}/chat/completions",
                                     json=payload, headers=self._headers()) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        obj = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    delta = obj.get("choices", [{}])[0].get("delta", {})
                    piece = delta.get("content", "")
                    if piece:
                        yield piece

    async def check(self):
        if not self.api_key:
            return False, "未配置 API Key（设置页填写，或设置环境变量 MARINE_LLM_API_KEY）"
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(20, connect=10)) as client:
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    json={"model": self.model, "messages": [{"role": "user", "content": "hi"}],
                          "max_tokens": 1},
                    headers=self._headers(),
                )
            if resp.status_code in (200, 201):
                return True, f"接口可用，模型 {self.model}"
            body = resp.text[:300]
            return False, f"接口返回 {resp.status_code}：{body}"
        except Exception as e:  # noqa: BLE001
            return False, f"连接失败：{e}"


# ------------------------------------------------- Mock（离线联调）
class MockProvider(LLMProvider):
    name = "mock"
    label = "Mock（离线联调）"

    def __init__(self, model: str = "mock-dry-run"):
        self.model = model

    async def stream(self, messages, temperature=None, max_tokens=None):
        user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        reply = (
            "[Mock 模式] 未配置真实模型，本回复用于验证系统链路。\n"
            f"收到消息：{user[:80]}。\n"
            "如需真实问答：安装 Ollama 并拉取模型，或在「设置」中填写 API Key 后切换 provider。"
        )
        # 模拟流式
        for i in range(0, len(reply), 12):
            yield reply[i:i + 12]
            await asyncio.sleep(0.005)

    async def check(self):
        return True, "Mock 离线模式运行中"


# ------------------------------------------------- 工厂
async def build_provider(cfg: Config) -> LLMProvider:
    provider = (cfg.get("llm.provider", "auto") or "auto").lower()
    temperature = float(cfg.get("llm.temperature", 0.3))

    if provider == "mock":
        return MockProvider()

    if provider == "ollama":
        return OllamaProvider(
            base_url=cfg.get("llm.ollama.base_url", "http://127.0.0.1:11434"),
            model=cfg.get("llm.ollama.model", "qwen2.5:14b"),
            temperature=temperature,
        )

    if provider == "openai":
        return OpenAICompatProvider(
            base_url=cfg.get("llm.openai_compatible.base_url", "https://api.deepseek.com/v1"),
            api_key=api_key_from_env(cfg),
            model=cfg.get("llm.openai_compatible.model", "deepseek-chat"),
            temperature=temperature,
        )

    # auto：优先本地 Ollama，回退 API
    ollama = OllamaProvider(
        base_url=cfg.get("llm.ollama.base_url", "http://127.0.0.1:11434"),
        model=cfg.get("llm.ollama.model", "qwen2.5:14b"),
        temperature=temperature,
    )
    ok, _ = await ollama.check()
    if ok:
        return ollama
    key = api_key_from_env(cfg)
    if key:
        return OpenAICompatProvider(
            base_url=cfg.get("llm.openai_compatible.base_url", "https://api.deepseek.com/v1"),
            api_key=key,
            model=cfg.get("llm.openai_compatible.model", "deepseek-chat"),
            temperature=temperature,
        )
    return MockProvider()
