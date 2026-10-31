"""PowerPoint 输出。

pptx 是唯一"绝对定位 == 可编辑"的格式：PPT 原生就是文本框按坐标摆放，
所以在它这里保版式和可编辑并不冲突。

坐标来自 IR 的可选几何字段；没有坐标的块（理论上不该出现）会退化成一页
纵向排列的文本框，而不是直接崩掉。
"""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.util import Pt

from ..ir import Block, Document

DEFAULT_PAGE = (595.0, 842.0)   # A4，单位 pt


def _textbox(slide, block: Block, left: float, top: float, width: float, height: float):
    box = slide.shapes.add_textbox(Pt(left), Pt(top), Pt(width), Pt(height))
    frame = box.text_frame
    frame.word_wrap = True
    frame.margin_left = 0
    frame.margin_right = 0
    frame.margin_top = 0
    frame.margin_bottom = 0

    lines = block.text.split("\n")
    frame.paragraphs[0].text = lines[0]
    for line in lines[1:]:
        frame.add_paragraph().text = line

    size = block.size or 11.0
    for para in frame.paragraphs:
        for run in para.runs:
            run.font.size = Pt(min(size, 12.0) if block.kind == "code" else size)
            run.font.bold = block.kind == "heading"
            if block.kind == "code":
                run.font.name = "Courier New"
    return box


def _table(slide, rows: list[list[str]], left: float, top: float, width: float, height: float, font_size: float = 11.0):
    n_rows = len(rows)
    n_cols = max(len(r) for r in rows)
    shape = slide.shapes.add_table(n_rows, n_cols, Pt(left), Pt(top), Pt(width), Pt(height))
    table = shape.table

    # 锁死行高，否则 PowerPoint 会用默认 18pt 字号撑高表格，盖住下方内容
    row_h = max(height / n_rows, 12.0)
    for r in range(n_rows):
        table.rows[r].height = Pt(row_h)

    size = max(7.0, min(font_size, row_h * 0.62))
    for r, row in enumerate(rows):
        for c in range(n_cols):
            cell = table.cell(r, c)
            cell.text = row[c] if c < len(row) else ""
            cell.margin_left = Pt(2)
            cell.margin_right = Pt(2)
            cell.margin_top = Pt(0)
            cell.margin_bottom = Pt(0)
            for para in cell.text_frame.paragraphs:
                for run in para.runs:
                    run.font.size = Pt(size)
    return shape


def render(ir: Document, out_path: str | Path) -> Path:
    prs = Presentation()
    page_size = next((b.page_size for b in ir.blocks if b.page_size), DEFAULT_PAGE)
    prs.slide_width = Pt(page_size[0])
    prs.slide_height = Pt(page_size[1])
    blank = prs.slide_layouts[6]

    pages: dict[int, list[Block]] = {}
    for block in ir.blocks:
        pages.setdefault(block.page or 1, []).append(block)

    fallback_y = 40.0
    for pno in sorted(pages):
        slide = prs.slides.add_slide(blank)
        fallback_y = 40.0
        for block in pages[pno]:
            if block.bbox and block.page_size:
                left, top, right, bottom = block.bbox
                width = max(right - left, 20.0)
                height = max(bottom - top, 14.0)
                if block.kind == "table" and block.rows:
                    _table(slide, block.rows, left, top, width, height, block.size or 11.0)
                else:
                    _textbox(slide, block, left, top, width, height)
            else:
                # 没有坐标时退化成纵向流式，不崩
                if block.kind == "table" and block.rows:
                    _table(slide, block.rows, 40.0, fallback_y, page_size[0] - 80.0, 14.0 * len(block.rows))
                    fallback_y += 20.0 * len(block.rows)
                else:
                    _textbox(slide, block, 40.0, fallback_y, page_size[0] - 80.0, 20.0)
                    fallback_y += (block.size or 11.0) * 1.8

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out))
    return out
