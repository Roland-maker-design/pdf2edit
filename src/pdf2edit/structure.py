"""结构重建：行/行组 → 标题、段落、列表、表格。

三条可用信号：字号（层级）、左边界（缩进/列表）、同一 y 上的多段（表格行）。
启发式够用就好，模型裁决留给更难的版式。
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pymupdf

from .extract import Line, extract_lines
from .ir import Block, Document

BULLET_CHARS = "•·●○▪◦‣–—*"
# 编号列表：1. / 1、 / 1)，但 "91.2%" 这种小数不能算
LIST_NUM = re.compile(r"^(\d{1,2})[.、)）](?![\d%])")
PAGE_NUM = re.compile(r"^[-—–\s]*\d{1,4}[-—–\s]*$")
PAGE_CN = re.compile(r"^第\s*\d+\s*页(\s*共\s*\d+\s*页)?$")

ROW_TOLERANCE = 2.0      # 同一行的 y 容差
COL_TOLERANCE = 12.0     # 判定"列对齐"的 x 容差


def _is_cjk(ch: str) -> bool:
    return "\u4e00" <= ch <= "\u9fff" or "\u3000" <= ch <= "\u303f" or "\uff00" <= ch <= "\uffef"


def _needs_space(left: str, right: str) -> bool:
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
    counter: Counter[float] = Counter()
    for ln in lines:
        counter[round(ln.size, 1)] += len(ln.text)
    return counter.most_common(1)[0][0]


def _body_left(lines: list[Line], body: float) -> float:
    """正文的左边界：正文字号行的 x0 众数。

    不能用中位数——列表项和表格单元格会把它拉偏。
    """
    counter: Counter[float] = Counter()
    for ln in lines:
        if abs(ln.size - body) < 0.6:
            counter[round(ln.bbox[0] / 2) * 2] += 1
    if not counter:
        return min(ln.bbox[0] for ln in lines)
    return float(counter.most_common(1)[0][0])


def _is_footer(ln: Line) -> bool:
    text = ln.text.strip()
    return bool(PAGE_NUM.match(text) or PAGE_CN.match(text))


def _classify(ln: Line, body: float, body_left: float) -> tuple[str, int]:
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
    # 无项目符号但有明显缩进（浏览器打印的 <ul> 就是这样）
    if ln.size <= body * 1.05 and ln.bbox[0] - body_left > body * 1.0:
        return "list_item", 0
    return "paragraph", 0


def _group_rows(lines: list[Line]) -> list[list[Line]]:
    """把同一 y 上的多段并成一行（表格的单元格就是这种形态）。"""
    rows: list[list[Line]] = []
    for ln in sorted(lines, key=lambda l: (l.page, l.bbox[1], l.bbox[0])):
        if rows:
            head = rows[-1][0]
            if head.page == ln.page and abs(head.bbox[1] - ln.bbox[1]) <= ROW_TOLERANCE:
                rows[-1].append(ln)
                continue
        rows.append([ln])
    return rows


def _looks_like_table(rows: list[list[Line]], i: int) -> bool:
    """连续两行以上、每行都有多个单元格、且列起点基本对齐。"""
    if i + 1 >= len(rows):
        return False
    a, b = rows[i], rows[i + 1]
    if len(a) < 2 or len(b) < 2:
        return False
    a_cols = [ln.bbox[0] for ln in sorted(a, key=lambda l: l.bbox[0])]
    b_cols = [ln.bbox[0] for ln in sorted(b, key=lambda l: l.bbox[0])]
    if len(a_cols) != len(b_cols):
        return False
    return all(abs(x - y) <= COL_TOLERANCE for x, y in zip(a_cols, b_cols))


def _collect_table(rows: list[list[Line]], i: int) -> tuple[list[list[str]], int]:
    out: list[list[str]] = []
    while i < len(rows) and len(rows[i]) >= 2:
        out.append([ln.text.strip() for ln in sorted(rows[i], key=lambda l: l.bbox[0])])
        i += 1
    return out, i


def _flush(buf: list[Line], doc: Document) -> None:
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
    body_left = _body_left(lines, body)
    rows = _group_rows(lines)
    ir = Document(source=Path(pdf_path))

    buf: list[Line] = []
    i = 0
    while i < len(rows):
        if _looks_like_table(rows, i):
            _flush(buf, ir)
            buf = []
            table, i = _collect_table(rows, i)
            ir.add(Block("table", rows=table, page=rows[i - 1][0].page))
            continue

        ln = rows[i][0]
        i += 1
        if _is_footer(ln):
            continue
        kind, level = _classify(ln, body, body_left)
        if kind == "paragraph":
            buf.append(ln)
        else:
            _flush(buf, ir)
            buf = []
            ir.add(Block(kind, text=ln.text, level=level, page=ln.page))
    _flush(buf, ir)
    return ir
