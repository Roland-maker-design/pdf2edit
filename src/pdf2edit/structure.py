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
GAP_MIN_WIDTH_RATIO = 0.015   # 栏间空白至少占页宽 1.5%（三栏排版实测只有 2~3%）
GAP_MAX_LINE_RATIO = 0.15     # 越过该空白的行数低于 15% 才算"走廊"
CELL_SHORT_CHARS = 12         # 单元格文本中位数不超过此值，才像表格而非分栏正文
MARGIN_BAND_RATIO = 0.07      # 页眉/页脚判定带
HEADING_MIN_RATIO = 1.12      # 标题至少要这么大倍数
HEADING_MIN_DELTA = 1.5       # 且至少大这么多 pt（防止 10→11 被当成标题）
MONO_HINTS = ("cour", "mono", "consol", "menlo", "courier", "code")


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
    sizes = sorted(
        {
            round(ln.size, 1)
            for ln in lines
            if ln.size >= body * HEADING_MIN_RATIO and ln.size - body >= HEADING_MIN_DELTA
        },
        reverse=True,
    )
    return {s: i + 1 for i, s in enumerate(sizes[:6])}


def _is_mono(font: str) -> bool:
    lowered = font.lower()
    return any(hint in lowered for hint in MONO_HINTS)


def _is_footer(ln: Line) -> bool:
    text = ln.text.strip()
    return bool(PAGE_NUM.match(text) or PAGE_CN.match(text))


def _is_margin_noise(ln: Line, body: float) -> bool:
    """页眉/页脚：位于页边带内，且字号明显小于正文。"""
    if ln.size >= body * 0.95:
        return False
    top_band = ln.bbox[1] < ln.page_height * MARGIN_BAND_RATIO
    bottom_band = ln.bbox[3] > ln.page_height * (1 - MARGIN_BAND_RATIO)
    return top_band or bottom_band


def _is_short_cell_row(row: list[Line]) -> bool:
    """一行里每格文字都很短，才像表格行；分栏正文的"一行"文字很长。"""
    lengths = sorted(len(ln.text.strip()) for ln in row)
    median = lengths[len(lengths) // 2]
    return median <= CELL_SHORT_CHARS


def _classify(ln: Line, body: float, body_left: float, levels: dict[float, int]) -> tuple[str, int]:
    if _is_mono(ln.font):
        return "code", 0
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


def _find_gaps(lines: list[Line], page_width: float) -> list[tuple[float, float]]:
    """列出所有纵向空白走廊，宽的在前。

    只保留"两侧都有内容"的走廊——页边空白（扫描区两端）不算，
    否则递归切栏会一刀砍在左边距上。
    """
    if len(lines) < 6:
        return []
    step = max(1.0, page_width / 400)
    limit = max(1, int(len(lines) * GAP_MAX_LINE_RATIO))
    min_width = page_width * GAP_MIN_WIDTH_RATIO

    lo = min(ln.bbox[0] for ln in lines)
    hi = max(ln.bbox[2] for ln in lines)

    gaps: list[tuple[float, float]] = []
    run_start: float | None = None
    x = page_width * 0.05
    while x < page_width * 0.95:
        covering = sum(1 for ln in lines if ln.bbox[0] <= x <= ln.bbox[2])
        if covering <= limit:
            if run_start is None:
                run_start = x
        else:
            if run_start is not None and x - run_start >= min_width:
                gaps.append((run_start, x))
            run_start = None
        x += step
    if run_start is not None and page_width * 0.95 - run_start >= min_width:
        gaps.append((run_start, page_width * 0.95))

    # 只留夹在内容中间的走廊
    valid = [(a, b) for a, b in gaps if a > lo + 1 and b < hi - 1]
    valid.sort(key=lambda g: g[1] - g[0], reverse=True)
    return valid


def _xy_split(lines: list[Line], page_width: float, depth: int = 0) -> list[list[Line]]:
    """递归切栏：一刀切成左右，再对每侧继续切，直到没走廊。三栏及以上靠它。"""
    if len(lines) < 6 or depth >= 3:
        return [sorted(lines, key=_center_y)]

    left: list[Line] = []
    right: list[Line] = []
    gap: tuple[float, float] | None = None
    for cand in _find_gaps(lines, page_width):
        mid = (cand[0] + cand[1]) / 2
        l = [ln for ln in lines if ln.bbox[2] <= mid]
        r = [ln for ln in lines if ln.bbox[0] >= mid]
        # 每侧至少 3 行才算真的一栏：单个页码/页脚凑出来的"右侧"不算
        if len(l) >= 3 and len(r) >= 3:
            left, right, gap = l, r, cand
            break
    if gap is None:
        return [sorted(lines, key=_center_y)]

    mid = (gap[0] + gap[1]) / 2
    spanning = [ln for ln in lines if ln.bbox[2] > mid > ln.bbox[0]]

    groups = _xy_split(left, page_width, depth + 1) + _xy_split(right, page_width, depth + 1)
    for ln in sorted(spanning, key=_center_y):
        groups.append([ln])
    groups.sort(key=lambda g: _center_y(g[0]))
    return groups


def _has_table_run(rows: list[list[Line]], min_run: int = 2) -> bool:
    """连续两行以上"每格都短"才算表格；零星单行短说明不了问题。"""
    run = 0
    for row in rows:
        if len(row) >= 2 and _is_short_cell_row(row):
            run += 1
            if run >= min_run:
                return True
        else:
            run = 0
    return False


def _reading_groups(page_lines: list[Line], page_width: float) -> list[list[Line]]:
    """排成阅读顺序的分组。

    含表格的页不切栏（切栏会把表格列间空白当走廊）；
    多栏页先剔除表格行再递归切栏。
    """
    rows = _group_rows(page_lines)
    # 有表格就整页按行处理：跨页/多栏混排在当前版本不支持
    if _has_table_run(rows):
        return [sorted(page_lines, key=_center_y)]

    # 页码/页脚不参与切栏，否则会凑出并不存在的"右侧内容"
    body_lines = [ln for ln in page_lines if not _is_footer(ln)]
    if len(body_lines) < 6:
        return [sorted(page_lines, key=_center_y)]

    return _xy_split(body_lines, page_width)


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
    """表格行必须"每格都短"；否则那是分栏正文，不是表格。"""
    row = rows[i]
    if len(row) >= 3:
        return _is_short_cell_row(row)
    if len(row) != 2 or not _is_short_cell_row(row):
        return False
    if i + 1 >= len(rows) or len(rows[i + 1]) != 2:
        return False
    a, b = _cols_of(row), _cols_of(rows[i + 1])
    return all(abs(x - y) <= COL_TOLERANCE for x, y in zip(a, b))


def _collect_table(rows: list[list[Line]], i: int) -> tuple[list[list[str]], list[Line], int]:
    out: list[list[str]] = []
    lines: list[Line] = []
    while i < len(rows) and len(rows[i]) >= 2 and _is_short_cell_row(rows[i]):
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


def _list_indent_centers(lines: list[Line], body: float, body_left: float) -> list[float]:
    """按"列表行自己的缩进位置"聚档。

    不能拿正文左边界当基准——有些文档整页都是列表，根本没有正文行。
    """
    xs: set[int] = set()
    for ln in lines:
        is_listish = ln.text[:1] in BULLET_CHARS or bool(LIST_NUM.match(ln.text))
        indented = abs(ln.size - body) < 0.6 and ln.bbox[0] - body_left > body * 0.5
        if is_listish or indented:
            xs.add(round(ln.bbox[0]))

    clusters: list[list[float]] = []
    for x in sorted(xs):
        if clusters and x - clusters[-1][-1] <= body * 0.8:
            clusters[-1].append(x)
        else:
            clusters.append([x])
    return [sum(c) / len(c) for c in clusters]


def _level_of(x: float, centers: list[float], body: float) -> int:
    for idx, center in enumerate(centers):
        if abs(x - center) <= body * 0.8:
            return idx + 1
    return 1


def _clean_list_text(text: str) -> str:
    return text.lstrip("•·●○▪◦‣–—* ").strip()


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

    code_buf: list[Line] = []

    def flush_code() -> None:
        if not code_buf:
            return
        ir.add(
            Block(
                "code",
                text="\n".join(l.raw for l in code_buf),
                page=code_buf[0].page,
                **_geo(code_buf),
            )
        )
        code_buf.clear()

    def flush_all() -> None:
        flush()
        flush_code()

    for pno in sorted(pages):
        page_lines = pages[pno]
        page_width = page_lines[0].page_width
        for group in _reading_groups(page_lines, page_width):
            # 正文左边界必须按栏算：用全页算会把右栏整体当成缩进的列表
            group_left = _body_left(group, body) if group else body_left
            rows = _group_rows(group)
            # 列表层级只从单格行统计：表格单元格本来就是多列的，会把层级顶歪
            single_cell = [r[0] for r in rows if len(r) == 1]
            indent_centers = _list_indent_centers(single_cell, body, group_left)
            # 用该栏内"小间距"的中位数估行距，段间距阈值 = 行距 + 0.6 字
            inner = [b.bbox[1] - a.bbox[3] for a, b in zip(group, group[1:])]
            small = sorted(g for g in inner if 0 <= g < body)
            base_gap = small[len(small) // 2] if small else 0.0
            para_gap = base_gap + body * 0.6 if small else body * 1.6
            i = 0
            warned_here = False
            while i < len(rows):
                row = rows[i]

                if len(row) >= 2 and any(_is_marker(ln.text) for ln in row):
                    flush_all()
                    ir.add(
                        Block(
                            "list_item",
                            text=_clean_list_text(_row_text(row)),
                            level=_level_of(row[0].bbox[0], indent_centers, body),
                            page=pno,
                            **_geo(row),
                        )
                    )
                    warned_here = False
                    i += 1
                    continue

                if _looks_like_table(rows, i):
                    flush_all()
                    table, table_lines, i = _collect_table(rows, i)
                    _append_table(ir, table, pno, _geo(table_lines))
                    warned_here = False
                    continue

                if len(row) > 1:
                    # 多格行但不成表：拼起来，绝不丢单元格
                    flush_all()
                    if _is_short_cell_row(row) and not warned_here:
                        # 静默降级比报错更糟：这里是"看起来像表格却没成形"
                        ir.add(Block("warning", text="疑似表格未能识别，下方内容可能需要人工整理"))
                        warned_here = True
                    ir.add(Block("paragraph", text=_row_text(row), page=pno, **_geo(row)))
                    i += 1
                    continue

                ln = row[0]
                i += 1
                if _is_footer(ln) or _is_margin_noise(ln, body):
                    continue
                kind, level = _classify(ln, body, group_left, levels)
                if kind == "list_item":
                    level = _level_of(ln.bbox[0], indent_centers, body)
                if kind == "code":
                    flush()
                    code_buf.append(ln)
                elif kind == "paragraph":
                    flush_code()
                    buf.append(ln)
                else:
                    flush_all()
                    text = _clean_list_text(ln.text) if kind == "list_item" else ln.text
                    ir.add(Block(kind, text=text, level=level, page=pno, **_geo([ln])))
            flush_all()
    flush()
    return ir
