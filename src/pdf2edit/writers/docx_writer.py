"""Word（docx）输出：流式结构，全部使用 Word 内置样式。

为什么坚持内置样式：用户在 Word 里改一次"标题 1"，全篇标题跟着变。
这才能算"真的能改"；用硬编码字号做出来的东西，改起来比截图还费劲。

关于 python-docx 的取舍：设计文档原本写"它会写不了合并单元格"，
实测它能 `cell.merge`，而 P1 只需要流式表格，所以先用它。
真要做复杂合并/浮动对象时再考虑手写 OOXML。
"""

from __future__ import annotations

from pathlib import Path

from docx import Document as DocxDocument
from docx.shared import Pt

from ..ir import Document


def render(ir: Document, out_path: str | Path) -> Path:
    doc = DocxDocument()

    for block in ir.blocks:
        if block.kind == "heading":
            level = max(1, min(6, block.level or 1))
            doc.add_heading(block.text, level=level)
        elif block.kind == "list_item":
            doc.add_paragraph(block.text, style="List Bullet")
        elif block.kind == "code":
            para = doc.add_paragraph()
            lines = block.text.split("\n")
            for idx, line in enumerate(lines):
                run = para.add_run(line)
                run.font.name = "Courier New"
                run.font.size = Pt(9)
                if idx < len(lines) - 1:
                    run.add_break()
        elif block.kind == "table":
            rows = block.rows or []
            if not rows:
                continue
            width = max(len(r) for r in rows)
            table = doc.add_table(rows=len(rows), cols=width)
            table.style = "Table Grid"
            for r, row in enumerate(rows):
                for c in range(width):
                    table.cell(r, c).text = row[c] if c < len(row) else ""
        else:
            doc.add_paragraph(block.text)

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out))
    return out
