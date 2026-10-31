"""生成一份 docx（用 python-docx，不碰 Word COM）。

Word 只负责最后一步"打开并导出 PDF"，避免 COM 建表卡死的老问题。
"""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.shared import Pt


def build(out_path: Path) -> None:
    doc = Document()

    doc.add_heading("第一章 绪论", level=1)
    doc.add_paragraph("本节介绍研究背景与意义，用于验证标题层级识别是否可靠。")
    doc.add_paragraph(
        "对于中文正文，Word 往往把一个自然段写成一行，也可能因为排版被折成多行，"
        "这里故意写长一些来触发折行。"
    )

    doc.add_heading("1.1 研究背景", level=2)
    doc.add_paragraph("国内外学者对该问题已有大量研究，主要集中在三个方面。")
    for item in ("第一，理论基础尚不完善。", "第二，实证数据相对匮乏。", "第三，方法体系有待统一。"):
        doc.add_paragraph(item, style="List Bullet")

    doc.add_heading("1.2 主要数据", level=2)
    table = doc.add_table(rows=3, cols=3)
    table.style = "Table Grid"
    data = [
        ("指标", "2024", "2025"),
        ("样本量", "1200", "1580"),
        ("准确率", "91.2%", "93.7%"),
    ]
    for r, row in enumerate(data):
        for c, value in enumerate(row):
            table.cell(r, c).text = value

    doc.add_paragraph("Last paragraph in English to verify spacing is preserved.")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out_path))
    print(f"已生成 {out_path}")


if __name__ == "__main__":
    build(Path(__file__).resolve().parent.parent / "fixtures" / "word_export.docx")
