"""结构重建：行 → 标题/段落/列表。

规则先走启发式，够用就好；模型裁决留给后面的表格和公式。
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pymupdf

from .extract import Line, extract_lines
from .ir import Block, Document

BULLET_CHARS = "•·●○▪◦‣–—*"
LIST_NUM = re.compile(r"^(\d{1,2})[.、)）]\s*")
PAGE_NUM = re.compile(r"^[-—–\s]*\d{1,4}[-—–\s]*$")
PAGE_CN = re.compile(r"^第\s*\d+\s*页(\s*共\s*\d+\s*页)?$")


def _is_cjk(ch: str) -> bool:
    return "\u4e00" <= ch <= "\u9fff" or "\u3000" <= ch <= "\u303f" or "\uff00" <= ch <= "\uffef"


def _needs_space(left: str, right: str) -> bool:
    """行合并时要不要补空格。中文之间不加，英文之间一定要加。"""
    if not left or not right:
        return False
    a, b = left[-1], right[0]
    if _is_cjk(a) or _is_cjk(b):
        return False
    if a in "-–/":
        return False
    return True


def _join(left: str, right: str) -> str:
    return left + (" " if _needs_space(left, right) else "") + right


def _body_size(lines: list[Line]) -> float:
    """按字符数加权的字号众数，比按行数更稳。"""
    counter: Counter[float] = Counter()
    for ln in lines:
        counter[round(ln.size, 1)] += len(ln.text)
    return counter.most_common(1)[0][0]


def _is_footer(ln: Line) -> bool:
    """只认确凿的页码样式，避免误删正文（单页文档尤其危险）。"""
    text = ln.text.strip()
    return bool(PAGE_NUM.match(text) or PAGE_CN.match(text))


def _classify(ln: Line, body: float) -> tuple[str, int]:
    # 字号优先：`1.1 背景` 这类编号标题要先于列表判断
    if ln.size > body * 1.35:
        return "heading", 1
    if ln.size > body * 1.15:
        return "heading", 2
    if ln.bold and ln.size > body * 1.05:
        return "heading", 3
    if ln.text[:1] in BULLET_CHARS:
        return "list_item", 0
    if LIST_NUM.match(ln.text):
        return "list_item", 0
    return "paragraph", 0


def _flush(buf: list[Line], doc: Document) -> None:
    """把连续的行合成段落；间距过大或字号变化就断段。"""
    if not buf:
        return
    cur = buf[0]
    text = cur.text
    for nxt in buf[1:]:
        gap = nxt.bbox[1] - cur.bbox[3]
        broken = (
            gap > cur.size * 1.6
            or abs(nxt.size - cur.size) > 0.6
            or nxt.page != cur.page
        )
        if broken:
            doc.add(Block("paragraph", text=text, page=cur.page))
            text = nxt.text
        else:
            text = _join(text, nxt.text)
        cur = nxt
    doc.add(Block("paragraph", text=text, page=cur.page))


def build_document(pdf_path: str | Path) -> Document:
    doc = pymupdf.open(str(pdf_path))
    lines = extract_lines(doc)
    if not lines:
        raise ValueError("没有提取到任何文本行")

    body = _body_size(lines)
    ir = Document(source=Path(pdf_path))

    buf: list[Line] = []
    for ln in lines:
        if _is_footer(ln):
            continue
        kind, level = _classify(ln, body)
        if kind == "paragraph":
            buf.append(ln)
        else:
            _flush(buf, ir)
            buf = []
            ir.add(Block(kind, text=ln.text, level=level, page=ln.page))
    _flush(buf, ir)
    return ir
