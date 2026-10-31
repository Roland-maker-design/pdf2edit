"""Excel（xlsx）输出。

不是"把整页铺进格子"——那是看着像 Excel、其实不能算。
这里只输出真正被识别为表格的区域，每个表一个工作表，
并且把数字写成数字类型（带格式），让用户能直接求和。

如果整份文档里没识别到任何表格，就明确拒绝，而不是硬造一个没用的表。
"""

from __future__ import annotations

import re
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, Side
from openpyxl.utils import get_column_letter

from ..ir import Document

_PLAIN_NUMBER = re.compile(r"^[-+]?\d+(?:\.\d+)?$")
_THOUSANDS = re.compile(r"^[-+]?\d{1,3}(?:,\d{3})+(?:\.\d+)?$")
_PERCENT = re.compile(r"^([-+]?\d+(?:\.\d+)?)\s*%$")


def coerce(text: str) -> tuple[object, str | None]:
    """把单元格文本转成合适的 Excel 值。返回 (值, 数字格式)。"""
    s = (text or "").strip()
    if not s:
        return None, None

    m = _PERCENT.match(s)
    if m:
        return float(m.group(1)) / 100.0, "0.0%"

    if _THOUSANDS.match(s):
        return float(s.replace(",", "")), "#,##0.00"

    if _PLAIN_NUMBER.match(s):
        value = float(s)
        if value.is_integer():
            return int(value), "0"
        return value, "0.00"

    return s, None


def _cell_width(value: object) -> int:
    if value is None:
        return 6
    text = str(value)
    # 中文按两个字符宽估算
    return max(6, sum(2 if ord(ch) > 127 else 1 for ch in text) + 2)


def _fill_sheet(ws, rows: list[list[str]]) -> None:
    thin = Side(style="thin", color="999999")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    for r, row in enumerate(rows, start=1):
        for c in range(1, len(row) + 1):
            value, fmt = coerce(row[c - 1])
            cell = ws.cell(row=r, column=c, value=value)
            cell.border = border
            if fmt:
                cell.number_format = fmt
            if r == 1:
                cell.font = Font(bold=True)
                cell.alignment = Alignment(horizontal="center", vertical="center")

    for c in range(1, max((len(r) for r in rows), default=0) + 1):
        width = max(_cell_width(coerce(rows[r][c - 1])[0]) for r in range(len(rows)) if c <= len(rows[r]))
        ws.column_dimensions[get_column_letter(c)].width = width

    # 首行做表头，冻结它
    if len(rows) > 1:
        ws.freeze_panes = "A2"


def render(ir: Document, out_path: str | Path) -> Path:
    tables = [b for b in ir.blocks if b.kind == "table" and b.rows]
    if not tables:
        raise ValueError("没有检测到表格，Excel 模式下这会是空文件；请改用 md / docx 输出")

    wb = Workbook()
    wb.remove(wb.active)

    for idx, block in enumerate(tables, start=1):
        ws = wb.create_sheet(f"表{idx}")
        _fill_sheet(ws, block.rows or [])

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(out))
    return out
