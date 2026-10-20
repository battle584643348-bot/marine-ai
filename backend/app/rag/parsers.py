"""文档解析：PDF / DOCX / XLSX / TXT / MD → 文本段。"""
from pathlib import Path
from typing import List, Tuple


def parse_file(path: Path) -> List[Tuple[str, str]]:
    """返回 [(来源标签, 文本)]。来源标签如 'p3'（PDF 第3页）/ 'T2'（表格第2个）。"""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _parse_pdf(path)
    if suffix == ".docx":
        return _parse_docx(path)
    if suffix in (".xlsx", ".xlsm"):
        return _parse_xlsx(path)
    if suffix in (".txt", ".md", ".markdown", ".csv", ".log"):
        return _parse_text(path)
    raise ValueError(f"暂不支持的文件类型：{suffix}（支持 pdf/docx/xlsx/txt/md/csv）")


def _read_bytes_smart(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "gbk", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _parse_text(path: Path) -> List[Tuple[str, str]]:
    text = _read_bytes_smart(path)
    return [("全文", text)]


def _parse_pdf(path: Path) -> List[Tuple[str, str]]:
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    out = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        text = " ".join(text.split())
        if text.strip():
            out.append((f"第{i}页", text))
    if not out:
        raise ValueError("PDF 未提取到文字（可能是扫描件，需先 OCR）")
    return out


def _parse_docx(path: Path) -> List[Tuple[str, str]]:
    import docx
    d = docx.Document(str(path))
    out: List[Tuple[str, str]] = []
    buf: List[str] = []
    for para in d.paragraphs:
        t = para.text.strip()
        if not t:
            continue
        buf.append(t)
        if para.style and "Heading" in (para.style.name or "") or len(buf) >= 40:
            out.append(("正文", "\n".join(buf)))
            buf = []
    if buf:
        out.append(("正文", "\n".join(buf)))
    for ti, table in enumerate(d.tables, start=1):
        lines = []
        for row in table.rows:
            cells = [c.text.strip().replace("\n", " ") for c in row.cells]
            lines.append(" | ".join(cells))
        out.append((f"表格{ti}", "\n".join(lines)))
    return out


def _parse_xlsx(path: Path) -> List[Tuple[str, str]]:
    import openpyxl
    wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    out = []
    for ws in wb.worksheets:
        lines = []
        for row in ws.iter_rows(values_only=True):
            vals = ["" if v is None else str(v) for v in row]
            line = " | ".join(vals).strip()
            if line:
                lines.append(line)
        if lines:
            out.append((f"工作表「{ws.title}」", "\n".join(lines)))
    return out
