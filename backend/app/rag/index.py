"""轻量检索索引：中英混排分词 → TF-IDF 稀疏向量（纯 Python 实现，零重依赖）；
可选叠加语义稠密向量（Ollama embedding 就绪时启用），形成混合召回。
索引持久化为 JSON。

分词策略：英文按词（小写）；中文按相邻二字二元组 + 单字兜底。
检索：稀疏余弦 + 可选稠密余弦加权；精确关键词命中再加权（工程术语强相关）。
"""
import json
import math
import re
import time
from collections import Counter
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from .chunker import chunk_text
from .parsers import parse_file

_WORD = re.compile(r"[a-z0-9]+")
_HAN = re.compile(r"[\u4e00-\u9fff]")


def tokenize(text: str) -> List[str]:
    text = (text or "").lower()
    toks = _WORD.findall(text)
    hans = _HAN.findall(text)
    if len(hans) == 1:
        toks.append(hans[0])
    elif hans:
        for i in range(len(hans) - 1):
            toks.append(hans[i] + hans[i + 1])
        toks.append(hans[-1])  # 尾部单字兜底
    return toks


def _tfidf_vector(tokens: List[str], idf: Dict[str, float]) -> Tuple[Dict[str, float], float]:
    if not tokens:
        return {}, 0.0
    tf = Counter(tokens)
    vec = {t: (cnt / len(tokens)) * idf.get(t, 1.0) for t, cnt in tf.items()}
    norm = math.sqrt(sum(w * w for w in vec.values()))
    return vec, norm


def _cosine(a: Dict[str, float], na: float, b: Dict[str, float], nb: float) -> float:
    if na <= 0 or nb <= 0:
        return 0.0
    dot = 0.0
    for t, w in a.items():
        bw = b.get(t)
        if bw:
            dot += w * bw
    return dot / (na * nb)


class Chunk:
    __slots__ = ("chunk_id", "doc_id", "text", "vec", "norm", "dense")

    def __init__(self, chunk_id: int, doc_id: str, text: str,
                 vec: Optional[Dict[str, float]] = None, norm: float = 0.0,
                 dense: Optional[List[float]] = None):
        self.chunk_id = chunk_id
        self.doc_id = doc_id
        self.text = text
        self.vec = vec or {}
        self.norm = norm
        self.dense = dense


class DocMeta:
    __slots__ = ("doc_id", "name", "path", "size", "added_at", "num_chunks")

    def __init__(self, doc_id: str, name: str, path: str, size: int, added_at: float, num_chunks: int = 0):
        self.doc_id = doc_id
        self.name = name
        self.path = path
        self.size = size
        self.added_at = added_at
        self.num_chunks = num_chunks


class DocumentIndex:
    def __init__(self, index_path: str):
        self.index_path = Path(index_path)
        self.docs: Dict[str, DocMeta] = {}
        self.chunks: List[Chunk] = []
        self._idf: Dict[str, float] = {}

    # ------------------------------------------------ 构建
    def add_document(self, path: Path, embed_fn: Optional[Callable[[List[str]], Optional[List[List[float]]]]] = None,
                     chunk_size: int = 800, overlap: int = 120) -> DocMeta:
        sections = parse_file(path)
        doc_id = f"doc_{int(time.time() * 1000)}"
        meta = DocMeta(doc_id, path.name, str(path), path.stat().st_size, time.time())

        all_chunks: List[str] = []
        for _label, txt in sections:
            all_chunks.extend(chunk_text(f"[{path.name}] {txt}", chunk_size, overlap))

        dense_list = None
        if embed_fn and all_chunks:
            try:
                dense_list = embed_fn(all_chunks)
            except Exception:  # noqa: BLE001
                dense_list = None

        new_chunks: List[Chunk] = []
        for i, text in enumerate(all_chunks):
            vec, norm = _tfidf_vector(tokenize(text), self._idf)
            dense = dense_list[i] if (dense_list and i < len(dense_list)) else None
            new_chunks.append(Chunk(len(self.chunks) + i, doc_id, text, vec, norm, dense))
        self.chunks.extend(new_chunks)
        meta.num_chunks = len(all_chunks)
        self.docs[doc_id] = meta
        self._rebuild_idf()
        self.save()
        return meta

    def _rebuild_idf(self):
        n = max(1, len(self.chunks))
        df: Counter = Counter()
        for c in self.chunks:
            for t in set(c.vec.keys()):
                df[t] += 1
        self._idf = {t: math.log((n + 1) / (cnt + 1)) + 1 for t, cnt in df.items()}
        for c in self.chunks:
            c.vec, c.norm = _tfidf_vector(tokenize(c.text), self._idf)

    def remove_document(self, doc_id: str) -> bool:
        if doc_id not in self.docs:
            return False
        del self.docs[doc_id]
        self.chunks = [c for c in self.chunks if c.doc_id != doc_id]
        self._rebuild_idf()
        self.save()
        return True

    def list_documents(self) -> List[Dict]:
        return [
            {"doc_id": m.doc_id, "name": m.name, "size": m.size,
             "added_at": m.added_at, "num_chunks": m.num_chunks}
            for m in self.docs.values()
        ]

    # ------------------------------------------------ 检索
    def search(self, query: str, top_k: int = 5,
               w_sparse: float = 0.6, w_dense: float = 0.4,
               embed_query: Optional[Callable[[str], Optional[List[float]]]] = None) -> List[Dict]:
        if not self.chunks:
            return []
        q_vec, q_norm = _tfidf_vector(tokenize(query), self._idf)
        q_dense = embed_query(query) if (embed_query and self._has_dense()) else None

        results: List[Tuple[float, Chunk]] = []
        for c in self.chunks:
            s = w_sparse * _cosine(q_vec, q_norm, c.vec, c.norm)
            if q_dense and c.dense:
                s += w_dense * _dense_cosine(q_dense, c.dense)
            if s > 0:
                results.append((s, c))
        results.sort(key=lambda x: -x[0])

        # 精确关键词命中加权（工程术语强相关）
        raw_q = (query or "").strip().lower()
        if raw_q and len(raw_q) >= 2:
            boosted = []
            for s, c in results[:100]:
                boosted.append((s * 1.25 if raw_q in c.text.lower() else s, c))
            boosted.sort(key=lambda x: -x[0])
            results = boosted

        return [{"chunk_id": c.chunk_id, "doc_id": c.doc_id, "text": c.text, "score": round(s, 4)}
                for s, c in results[:top_k]]

    def _has_dense(self) -> bool:
        return any(c.dense is not None for c in self.chunks)

    # ------------------------------------------------ 持久化
    def save(self):
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "docs": [{k: getattr(m, k) for k in DocMeta.__slots__} for m in self.docs.values()],
            "chunks": [{"chunk_id": c.chunk_id, "doc_id": c.doc_id, "text": c.text,
                        "vec": c.vec, "norm": c.norm, "dense": c.dense} for c in self.chunks],
        }
        self.index_path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    def load(self):
        if not self.index_path.exists():
            return
        try:
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return
        self.docs = {d["doc_id"]: DocMeta(**d) for d in data.get("docs", [])}
        self.chunks = [Chunk(**c) for c in data.get("chunks", [])]
        self._rebuild_idf()


def _dense_cosine(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)
