"""结构重建：行组 → 标题、段落、列表、表格。

实测得到的四条经验：
1. 标题层级按字号**分档排序**，不能比倍数——Word 的 H1/H2 只差 1pt。
2. 同一 y 上的多段是表格行；但 Word 表格单元格的基线会差 2~3pt，要用 y 中心 + 容差。
3. 项目符号（•）在 Word 里是独立一段，必须识别成标记，否则会被当成两列表格。
4. 无符号列表靠缩进判定（浏览器打印的 <ul> 就是这样）。
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pymupdf

from .extract import Line, extract_lines
from .ir import Block, Document

BULLET_CHARS = "•·●○▪◦‣–—*"
LIST_NUM = re.compile(r"^(\d{1,2})[.、)）](?![\d%])")
PAGE_NUM = re.compile(r"^[-—–\s]*\d{1,4}[-—–\s]*$")
PAGE_CN = re.compile(r"^第\s*\d+\s*页(\s*共\s*\d+\s*页)?$")

ROW_TOLERANCE = 3.0      # 同一行的 y 中心容差（Word 表格实测差 2.5pt）
COL_TOLERANCE = 12.0     # 列起点对齐容差


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


def _center_y(ln: Line) -> float:
    return (ln.bbox[1] + ln.bbox[3]) / 2


def _is_marker(text: str) -> bool:
    """整段只有项目符号。"""
    return bool(text) and all(ch in BULLET_CHARS or ch.isspace() for ch in text)


def _body_size(lines: list[Line]) -> float:
    counter: Counter[float] = Counter()
    for ln in lines:
        counter[round(ln.size, 1)] += len(ln.text)
    return counter.most_common(1)[0][0]


def _body_left(lines: list[Line], body: float) -> float:
    counter: Counter[float] = Counter()
    for ln in lines:
        if abs(ln.size - body) < 0.6:
            counter[round(ln.bbox[0] / 2) * 2] += 1
    if not counter:
        return min(ln.bbox[0] for ln in lines)
    return float(counter.most_common(1)[0][0])


def _heading_levels(lines: list[Line], body: float) -> dict[float, int]:
    """把所有比正文大的字号降序排列，第 1 大的就是一级标题。"""
    sizes = sorted(
        {round(ln.size, 1) for ln in lines if ln.size > body * 1.05},
        reverse=True,
    )
    return {s: i + 1 for i, s in enumerate(sizes[:6])}


def _is_footer(ln: Line) -> bool:
    text = ln.text.strip()
    return bool(PAGE_NUM.match(text) or PAGE_CN.match(text))


def _classify(ln: Line, body: float, body_left: float, levels: dict[float, int]) -> tuple[str, int]:
    level = levels.get(round(ln.size, 1))
    if level:
        return "heading", level
    if ln.text[:1] in BULLET_CHARS:
        return "list_item", 0
    if LIST_NUM.match(ln.text):
        return "list_item", 0
    if ln.size <= body * 1.05 and ln.bbox[0] - body_left > body * 1.0:
        return "list_item", 0
    return "paragraph", 0


def _group_rows(lines: list[Line]) -> list[list[Line]]:
    rows: list[list[Line]] = []
    for ln in sorted(lines, key=lambda l: (l.page, _center_y(l), l.bbox[0])):
        if rows:
            head = rows[-1][0]
            if head.page == ln.page and abs(_center_y(head) - _center_y(ln)) <= ROW_TOLERANCE:
                rows[-1].append(ln)
                continue
        rows.append([ln])
    return rows


def _row_text(row: list[Line]) -> str:
    return "\n".join(ln.text for ln in sorted(row, key=lambda l: l.bbox[0]))


def _looks_like_table(rows: list[list[Line]], i: int) -> bool:
    if i + 1 >= len(rows):
        return False
    a, b = rows[i], rows[i + 1]
    if len(a) < 2 or len(b) < 2 or len(a) != len(b):
        return False
    a_cols = [ln.bbox[0] for ln in sorted(a, key=lambda l: l.bbox[0])]
    b_cols = [ln.bbox[0] for ln in sorted(b, key=lambda l: l.bbox[0])]
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
    levels = _heading_levels(lines, body)
    rows = _group_rows(lines)
    ir = Document(source=Path(pdf_path))

    buf: list[Line] = []
    i = 0
    while i < len(rows):
        row = rows[i]

        # 1) 项目符号行：标记 + 正文，是列表不是表格
        if len(row) >= 2 and any(_is_marker(ln.text) for ln in row):
            _flush(buf, ir)
            buf = []
            text = " ".join(
                ln.text.strip() for ln in sorted(row, key=lambda l: l.bbox[0]) if not _is_marker(ln.text)
            )
            ir.add(Block("list_item", text=text, page=row[0].page))
            i += 1
            continue

        # 2) 表格：连续多行、每行多格、列对齐
        if _looks_like_table(rows, i):
            _flush(buf, ir)
            buf = []
            table, i = _collect_table(rows, i)
            ir.add(Block("table", rows=table, page=rows[i - 1][0].page))
            continue

        # 3) 普通行
        ln = row[0]
        i += 1
        if _is_footer(ln):
            continue
        kind, level = _classify(ln, body, body_left, levels)
        if kind == "paragraph":
            buf.append(ln)
        else:
            _flush(buf, ir)
            buf = []
            ir.add(Block(kind, text=ln.text, level=level, page=ln.page))
    _flush(buf, ir)
    return ir
