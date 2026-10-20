"""文本切块：按段落聚合，块间带重叠以保证上下文连续。"""
import re
from typing import List

_PARA_SPLIT = re.compile(r"\n\s*\n")


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 120) -> List[str]:
    text = text.strip()
    if not text:
        return []
    paras = [p.strip() for p in _PARA_SPLIT.split(text) if p.strip()]
    chunks: List[str] = []
    cur = ""
    for p in paras:
        if len(p) >= chunk_size:  # 超长段落内部再切（重叠分段）
            if cur:
                chunks.append(cur)
                cur = ""
            step = chunk_size - overlap
            for i in range(0, len(p), step):
                chunks.append(p[i:i + chunk_size])
            continue
        if cur and len(cur) + len(p) + 2 > chunk_size:
            # 新块开头带上上一块尾部 overlap 字符，保证上下文衔接
            chunks.append(cur)
            cur = cur[-overlap:] + "\n" + p
        else:
            cur = (cur + "\n" + p).strip() if cur else p
    if cur:
        chunks.append(cur)
    return chunks
