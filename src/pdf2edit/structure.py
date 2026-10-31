"""结构重建：先切栏，再在栏内做行组 → 标题、段落、列表、表格。

实测得到的经验（每条都对应一个真实失败）：
1. 标题层级按字号分档排序，不比倍数——Word 的 H1/H2 只差 1pt。
2. 多栏必须**先切栏**，否则同一 y 的左右两栏会被当成一行两格。
3. 表格单元格基线会差 2~3pt，行聚合要用 y 中心 + 容差。
4. 表头经常居中、数据左/右对齐，列位置对不上，所以不能拿表头去对齐数据行。
5. 项目符号（•）在 Word 里是独立的一段，要先识别成标记。
6. 多格行若判定不成表格，也要把单元格拼起来，不能只留第一格。
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

ROW_TOLERANCE = 3.0      # 同一行的 y 中心容差
COL_TOLERANCE = 12.0     # 列起点对齐容差
GAP_MIN_WIDTH_RATIO = 0.035   # 栏间空白至少占页宽的 3.5%
GAP_MAX_LINE_RATIO = 0.15     # 越过该空白的行数低于 15% 才算"走廊"


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
    sizes = sorted({round(ln.size, 1) for ln in lines if ln.size > body * 1.05}, reverse=True)
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


# ---------------------------------------------------------------- 栏分割


def _find_column_gap(lines: list[Line], page_width: float) -> tuple[float, float] | None:
    """找一条纵向空白走廊：覆盖它的行数极少，且宽度够大。"""
    if len(lines) < 6:
        return None
    step = max(1.0, page_width / 400)
    limit = max(1, int(len(lines) * GAP_MAX_LINE_RATIO))
    min_width = page_width * GAP_MIN_WIDTH_RATIO

    best: tuple[float, float] | None = None
    run_start: float | None = None
    x = page_width * 0.15
    while x < page_width * 0.85:
        covering = sum(1 for ln in lines if ln.bbox[0] <= x <= ln.bbox[2])
        free = covering <= limit
        if free and run_start is None:
            run_start = x
        elif not free and run_start is not None:
            if x - run_start >= min_width and (best is None or x - run_start > best[1] - best[0]):
                best = (run_start, x)
            run_start = None
        x += step
    if run_start is not None and page_width * 0.85 - run_start >= min_width:
        if best is None or page_width * 0.85 - run_start > best[1] - best[0]:
            best = (run_start, page_width * 0.85)
    return best


def _reading_groups(page_lines: list[Line], page_width: float) -> list[list[Line]]:
    """把一页的行排成阅读顺序的分组：通栏元素自成一组，栏内元素左栏先、右栏后。

    注意：探测栏间隙时必须排除表格行。表格列之间天然有大片空白，
    否则会被误判成栏，把表格拦腰切断。
    """
    rows = _group_rows(page_lines)
    table_ids = {id(ln) for row in rows if len(row) >= 3 for ln in row}
    probe = [ln for ln in page_lines if id(ln) not in table_ids]
    # 一页全被表格占据时没有可靠探针；绝不能退回全部行再去切栏，否则会把表格切断
    if not probe:
        return [sorted(page_lines, key=_center_y)]

    gap = _find_column_gap(probe, page_width)
    if not gap:
        return [sorted(page_lines, key=_center_y)]

    g0, g1 = gap
    mid = (g0 + g1) / 2          # 按中线判定，避免采样步长带来的边缘误差
    spanning, left, right = [], [], []
    for ln in page_lines:
        if ln.bbox[2] <= mid:
            left.append(ln)
        elif ln.bbox[0] >= mid:
            right.append(ln)
        else:
            spanning.append(ln)      # 骑在走廊上的，按通栏处理

    if not left or not right:
        return [sorted(page_lines, key=_center_y)]

    for bucket in (left, right, spanning):
        bucket.sort(key=_center_y)

    groups: list[list[Line]] = [left, right] + [[ln] for ln in spanning]
    # 通栏标题/页尾可能夹在栏前后，按各自首行的 y 排序还原阅读顺序
    groups.sort(key=lambda g: _center_y(g[0]))
    return groups


# ---------------------------------------------------------------- 行组与表格


def _group_rows(lines: list[Line]) -> list[list[Line]]:
    rows: list[list[Line]] = []
    for ln in sorted(lines, key=lambda l: (_center_y(l), l.bbox[0])):
        if rows:
            head = rows[-1][0]
            if abs(_center_y(head) - _center_y(ln)) <= ROW_TOLERANCE:
                rows[-1].append(ln)
                continue
        rows.append([ln])
    return rows


def _row_cells(row: list[Line]) -> list[Line]:
    return sorted(row, key=lambda l: l.bbox[0])


def _row_text(row: list[Line]) -> str:
    return " ".join(ln.text.strip() for ln in _row_cells(row) if not _is_marker(ln.text))


def _cols_of(row: list[Line]) -> list[float]:
    return [ln.bbox[0] for ln in _row_cells(row)]


def _looks_like_table(rows: list[list[Line]], i: int) -> bool:
    """三格以上直接算表；两格要和下一行对齐才认（避免把双栏正文当表格）。"""
    row = rows[i]
    if len(row) >= 3:
        return True
    if len(row) != 2:
        return False
    if i + 1 >= len(rows) or len(rows[i + 1]) != 2:
        return False
    a, b = _cols_of(row), _cols_of(rows[i + 1])
    return all(abs(x - y) <= COL_TOLERANCE for x, y in zip(a, b))


def _collect_table(rows: list[list[Line]], i: int) -> tuple[list[list[str]], list[Line], int]:
    out: list[list[str]] = []
    lines: list[Line] = []
    while i < len(rows) and len(rows[i]) >= 2:
        cells = [ln.text.strip() for ln in _row_cells(rows[i])]
        # 跨页时表头可能重复出现，丢掉重复表头
        if out and cells == out[0]:
            i += 1
            continue
        out.append(cells)
        lines.extend(rows[i])
        i += 1
    return out, lines, i


def _union(lines: list[Line]) -> tuple[float, float, float, float]:
    return (
        min(l.bbox[0] for l in lines),
        min(l.bbox[1] for l in lines),
        max(l.bbox[2] for l in lines),
        max(l.bbox[3] for l in lines),
    )


def _geo(lines: list[Line]) -> dict:
    head = lines[0]
    return {
        "bbox": _union(lines),
        "page_size": (head.page_width, head.page_height),
        "size": head.size,
    }


# ---------------------------------------------------------------- 主流程


def _append_table(ir: Document, rows: list[list[str]], page: int, geo: dict) -> None:
    """跨页表格续接：若上一个是表格且跨了页，就把行接上，重复表头只留一次。"""
    last = ir.blocks[-1] if ir.blocks else None
    if last is not None and last.kind == "table" and last.rows and last.page != page:
        if rows and rows[0] == last.rows[0]:
            last.rows.extend(rows[1:])
        else:
            last.rows.extend(rows)
        return
    ir.add(Block("table", rows=rows, page=page, **geo))


def build_document(pdf_path: str | Path) -> Document:
    doc = pymupdf.open(str(pdf_path))
    lines = extract_lines(doc)
    if not lines:
        raise ValueError("没有提取到任何文本行")

    body = _body_size(lines)
    body_left = _body_left(lines, body)
    levels = _heading_levels(lines, body)
    ir = Document(source=Path(pdf_path))

    # 无坐标时 pptx 也要能用：按页记录，供退化路径取页宽高
    pages: dict[int, list[Line]] = {}
    for ln in lines:
        pages.setdefault(ln.page, []).append(ln)

    buf: list[Line] = []
    # 段间距阈值按当前栏实测的行距自适应，固定倍数在不同排版下必然失效
    para_gap = body * 1.6

    def flush() -> None:
        if not buf:
            return
        cur = buf[0]
        text = cur.text
        acc = [cur]
        for nxt in buf[1:]:
            gap = nxt.bbox[1] - cur.bbox[3]
            broken = gap > para_gap or abs(nxt.size - cur.size) > 0.6
            if broken:
                ir.add(Block("paragraph", text=text, page=cur.page, **_geo(acc)))
                text = nxt.text
                acc = [nxt]
            else:
                text = _join(text, nxt.text)
                acc.append(nxt)
            cur = nxt
        ir.add(Block("paragraph", text=text, page=cur.page, **_geo(acc)))
        buf.clear()

    for pno in sorted(pages):
        page_lines = pages[pno]
        page_width = page_lines[0].page_width
        for group in _reading_groups(page_lines, page_width):
            # 正文左边界必须按栏算：用全页算会把右栏整体当成缩进的列表
            group_left = _body_left(group, body) if group else body_left
            # 用该栏内"小间距"的中位数估行距，段间距阈值 = 行距 + 0.6 字
            inner = [b.bbox[1] - a.bbox[3] for a, b in zip(group, group[1:])]
            small = sorted(g for g in inner if 0 <= g < body)
            base_gap = small[len(small) // 2] if small else 0.0
            para_gap = base_gap + body * 0.6 if small else body * 1.6
            rows = _group_rows(group)
            i = 0
            while i < len(rows):
                row = rows[i]

                if len(row) >= 2 and any(_is_marker(ln.text) for ln in row):
                    flush()
                    ir.add(Block("list_item", text=_row_text(row), page=pno, **_geo(row)))
                    i += 1
                    continue

                if _looks_like_table(rows, i):
                    flush()
                    table, table_lines, i = _collect_table(rows, i)
                    _append_table(ir, table, pno, _geo(table_lines))
                    continue

                if len(row) > 1:
                    # 多格行但不成表：拼起来，绝不丢单元格
                    flush()
                    ir.add(Block("paragraph", text=_row_text(row), page=pno, **_geo(row)))
                    i += 1
                    continue

                ln = row[0]
                i += 1
                if _is_footer(ln):
                    continue
                kind, level = _classify(ln, body, group_left, levels)
                if kind == "paragraph":
                    buf.append(ln)
                else:
                    flush()
                    ir.add(Block(kind, text=ln.text, level=level, page=pno, **_geo([ln])))
            flush()
    flush()
    return ir
