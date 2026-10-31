"""P0 主线的端到端测试。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pymupdf
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

CLEAN = ROOT / "fixtures" / "clean_basic.pdf"
BROKEN = ROOT / "fixtures" / "01.生存游戏.pdf"


@pytest.fixture(scope="session")
def clean_pdf() -> Path:
    if not CLEAN.exists():
        subprocess.run(
            [sys.executable, str(ROOT / "fixtures" / "generate_clean.py")], check=True
        )
    return CLEAN


def test_quality_rejects_broken_text_layer(clean_pdf: Path) -> None:
    from pdf2edit.quality import assess

    report = assess(pymupdf.open(str(BROKEN)))
    assert report.ok is False
    assert "文字层" in report.reason


def test_quality_accepts_clean_pdf(clean_pdf: Path) -> None:
    from pdf2edit.quality import assess

    report = assess(pymupdf.open(str(clean_pdf)))
    assert report.ok is True, report.reason


def test_first_block_is_h1(clean_pdf: Path) -> None:
    from pdf2edit.structure import build_document

    doc = build_document(clean_pdf)
    assert doc.blocks[0].kind == "heading"
    assert doc.blocks[0].level == 1
    assert "第一章" in doc.blocks[0].text


def test_numbered_heading_not_treated_as_list(clean_pdf: Path) -> None:
    from pdf2edit.structure import build_document

    doc = build_document(clean_pdf)
    headings = [b for b in doc.blocks if b.kind == "heading"]
    assert any(b.text.startswith("1.1") for b in headings)


def test_has_list_items(clean_pdf: Path) -> None:
    from pdf2edit.structure import build_document

    doc = build_document(clean_pdf)
    items = [b for b in doc.blocks if b.kind == "list_item"]
    assert len(items) == 2


def test_cjk_lines_joined_without_space(clean_pdf: Path) -> None:
    from pdf2edit.structure import build_document

    doc = build_document(clean_pdf)
    joined = [b.text for b in doc.blocks if b.kind == "paragraph"]
    assert any("是否正确。第二行" in t for t in joined), joined


def test_page_numbers_removed(clean_pdf: Path) -> None:
    from pdf2edit.structure import build_document

    doc = build_document(clean_pdf)
    texts = {b.text.strip() for b in doc.blocks}
    assert "1" not in texts and "2" not in texts


def test_markdown_rendering(clean_pdf: Path) -> None:
    from pdf2edit.structure import build_document
    from pdf2edit.writers.markdown import render

    md = render(build_document(clean_pdf))
    assert md.startswith("# 第一章 总论")
    assert "- 第一条要点\n- 第二条要点" in md
    assert "## 1.1 背景" in md


# --- 浏览器打印的真实 PDF（列表无项目符号、含表格） ---

PRINTED = ROOT / "fixtures" / "print_export.pdf"


@pytest.mark.skipif(not PRINTED.exists(), reason="缺少 print_export.pdf")
def test_lists_detected_by_indent() -> None:
    from pdf2edit.structure import build_document

    doc = build_document(PRINTED)
    items = [b for b in doc.blocks if b.kind == "list_item"]
    assert len(items) == 3, [b.text for b in items]
    assert items[0].text.startswith("第一")


@pytest.mark.skipif(not PRINTED.exists(), reason="缺少 print_export.pdf")
def test_table_detected() -> None:
    from pdf2edit.structure import build_document

    doc = build_document(PRINTED)
    tables = [b for b in doc.blocks if b.kind == "table"]
    assert len(tables) == 1
    rows = tables[0].rows
    assert rows[0] == ["指标", "2024", "2025"]
    assert rows[2] == ["准确率", "91.2%", "93.7%"]


@pytest.mark.skipif(not PRINTED.exists(), reason="缺少 print_export.pdf")
def test_percentage_not_treated_as_list() -> None:
    from pdf2edit.structure import build_document

    doc = build_document(PRINTED)
    assert not any(b.kind == "list_item" and "%" in b.text for b in doc.blocks)


@pytest.mark.skipif(not PRINTED.exists(), reason="缺少 print_export.pdf")
def test_table_rendered_as_pipe_table() -> None:
    from pdf2edit.structure import build_document
    from pdf2edit.writers.markdown import render

    md = render(build_document(PRINTED))
    assert "| 指标 | 2024 | 2025 |" in md
    assert "| 准确率 | 91.2% | 93.7% |" in md


# --- Word 导出的真实 PDF（H1/H2 只差 1pt，项目符号是独立一段，表格基线差 2.5pt） ---

WORD = ROOT / "fixtures" / "word_export.pdf"


@pytest.mark.skipif(not WORD.exists(), reason="缺少 word_export.pdf")
def test_word_heading_levels_by_size_rank() -> None:
    from pdf2edit.structure import build_document

    doc = build_document(WORD)
    h1 = [b for b in doc.blocks if b.kind == "heading" and b.level == 1]
    h2 = [b for b in doc.blocks if b.kind == "heading" and b.level == 2]
    assert [b.text for b in h1] == ["第一章 绪论"]
    assert [b.text for b in h2] == ["1.1 研究背景", "1.2 主要数据"]


@pytest.mark.skipif(not WORD.exists(), reason="缺少 word_export.pdf")
def test_word_bullet_marker_not_a_table() -> None:
    from pdf2edit.structure import build_document

    doc = build_document(WORD)
    items = [b for b in doc.blocks if b.kind == "list_item"]
    assert len(items) == 3
    assert items[0].text.startswith("第一")
    assert not any(b.kind == "table" and any("•" in c for r in (b.rows or []) for c in r) for b in doc.blocks)


@pytest.mark.skipif(not WORD.exists(), reason="缺少 word_export.pdf")
def test_word_table_rows_grouped() -> None:
    from pdf2edit.structure import build_document

    doc = build_document(WORD)
    tables = [b for b in doc.blocks if b.kind == "table"]
    assert len(tables) == 1
    rows = tables[0].rows
    assert rows[0] == ["指标", "2024", "2025"]
    assert rows[1] == ["样本量", "1200", "1580"]
    assert rows[2] == ["准确率", "91.2%", "93.7%"]


# --- docx 输出 ---

@pytest.mark.skipif(not WORD.exists(), reason="缺少 word_export.pdf")
def test_docx_uses_builtin_styles(tmp_path: Path) -> None:
    from docx import Document as DocxDocument

    from pdf2edit.structure import build_document
    from pdf2edit.writers.docx_writer import render

    out = tmp_path / "out.docx"
    render(build_document(WORD), out)

    doc = DocxDocument(str(out))
    styles = [p.style.name for p in doc.paragraphs if p.text.strip()]
    assert "Heading 1" in styles
    assert styles.count("Heading 2") == 2
    assert styles.count("List Bullet") == 3


@pytest.mark.skipif(not WORD.exists(), reason="缺少 word_export.pdf")
def test_docx_table_is_real_table(tmp_path: Path) -> None:
    from docx import Document as DocxDocument

    from pdf2edit.structure import build_document
    from pdf2edit.writers.docx_writer import render

    out = tmp_path / "out.docx"
    render(build_document(WORD), out)

    doc = DocxDocument(str(out))
    assert len(doc.tables) == 1
    table = doc.tables[0]
    assert len(table.rows) == 3 and len(table.columns) == 3
    assert table.cell(0, 0).text == "指标"
    assert table.cell(2, 2).text == "93.7%"


@pytest.mark.skipif(not WORD.exists(), reason="缺少 word_export.pdf")
def test_docx_keeps_body_text(tmp_path: Path) -> None:
    from docx import Document as DocxDocument

    from pdf2edit.structure import build_document
    from pdf2edit.writers.docx_writer import render

    out = tmp_path / "out.docx"
    render(build_document(WORD), out)

    doc = DocxDocument(str(out))
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "国内外学者对该问题已有大量研究" in text
    assert "Last paragraph in English to verify spacing is preserved." in text


# --- html 输出 ---

@pytest.mark.skipif(not WORD.exists(), reason="缺少 word_export.pdf")
def test_html_semantic_tags() -> None:
    from pdf2edit.structure import build_document
    from pdf2edit.writers.html_writer import render

    html = render(build_document(WORD))
    assert "<h1>第一章 绪论</h1>" in html
    assert "<h2>1.1 研究背景</h2>" in html
    assert "<ul>" in html and html.count("<li>") == 3
    assert "<th>指标</th>" in html
    assert "<td>93.7%</td>" in html


@pytest.mark.skipif(not WORD.exists(), reason="缺少 word_export.pdf")
def test_html_has_no_absolute_positioning() -> None:
    from pdf2edit.structure import build_document
    from pdf2edit.writers.html_writer import render

    html = render(build_document(WORD))
    assert "position:absolute" not in html
    assert "position: absolute" not in html


def test_html_escapes_special_characters() -> None:
    from pdf2edit.ir import Block, Document
    from pdf2edit.writers.html_writer import render

    ir = Document(blocks=[Block("paragraph", text='<script>alert("x")</script> & more')])
    html = render(ir)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "&amp; more" in html


def test_html_uses_first_heading_as_title() -> None:
    from pdf2edit.ir import Block, Document
    from pdf2edit.writers.html_writer import render

    ir = Document(blocks=[Block("heading", text="第一章 绪论", level=1), Block("paragraph", text="正文")])
    html = render(ir)
    assert "<title>第一章 绪论</title>" in html
    assert '<html lang="zh-CN">' in html


# --- pptx 输出 ---

@pytest.mark.skipif(not WORD.exists(), reason="缺少 word_export.pdf")
def test_pptx_slide_and_shapes(tmp_path: Path) -> None:
    from pptx import Presentation

    from pdf2edit.structure import build_document
    from pdf2edit.writers.pptx_writer import render

    out = tmp_path / "out.pptx"
    render(build_document(WORD), out)

    prs = Presentation(str(out))
    assert len(prs.slides) == 1
    slide = prs.slides[0]
    texts = [sh.text_frame.text for sh in slide.shapes if sh.has_text_frame]
    tables = [sh.table for sh in slide.shapes if sh.has_table]

    assert any("第一章 绪论" in t for t in texts)
    assert any("第一，理论基础尚不完善。" in t for t in texts)
    assert len(tables) == 1
    assert len(tables[0].rows) == 3
    assert tables[0].cell(0, 0).text == "指标"
    assert tables[0].cell(2, 2).text == "93.7%"


@pytest.mark.skipif(not WORD.exists(), reason="缺少 word_export.pdf")
def test_pptx_slide_size_matches_pdf_page(tmp_path: Path) -> None:
    from pptx import Presentation
    from pptx.util import Pt

    from pdf2edit.structure import build_document
    from pdf2edit.writers.pptx_writer import render

    ir = build_document(WORD)
    page_size = next(b.page_size for b in ir.blocks if b.page_size)
    out = tmp_path / "size.pptx"
    render(ir, out)

    prs = Presentation(str(out))
    assert abs(prs.slide_width - Pt(page_size[0])) < 100
    assert abs(prs.slide_height - Pt(page_size[1])) < 100


def test_pptx_degrades_without_geometry(tmp_path: Path) -> None:
    """没有坐标时必须能退化，不能崩。"""
    from pptx import Presentation

    from pdf2edit.ir import Block, Document
    from pdf2edit.writers.pptx_writer import render

    ir = Document(blocks=[
        Block("heading", text="标题", level=1, page=1, size=18),
        Block("paragraph", text="正文一段", page=1, size=11),
    ])
    out = tmp_path / "nogeo.pptx"
    render(ir, out)
    prs = Presentation(str(out))
    assert len(prs.slides) == 1
    assert len(prs.slides[0].shapes) == 2


# --- xlsx 输出 ---

def test_coerce_numbers_and_percent() -> None:
    from pdf2edit.writers.xlsx_writer import coerce

    assert coerce("1200") == (1200, "0")
    assert coerce("91.2%") == (0.912, "0.0%")
    assert coerce("1,200") == (1200.0, "#,##0.00")
    assert coerce("3.14") == (3.14, "0.00")
    assert coerce("准确率") == ("准确率", None)
    assert coerce("") == (None, None)


@pytest.mark.skipif(not WORD.exists(), reason="缺少 word_export.pdf")
def test_xlsx_real_numbers(tmp_path: Path) -> None:
    from openpyxl import load_workbook

    from pdf2edit.structure import build_document
    from pdf2edit.writers.xlsx_writer import render

    out = tmp_path / "out.xlsx"
    render(build_document(WORD), out)

    wb = load_workbook(str(out))
    assert wb.sheetnames == ["表1"]
    ws = wb["表1"]

    assert ws["A1"].value == "指标"
    assert ws["B2"].value == 1200 and isinstance(ws["B2"].value, int)
    assert abs(ws["B3"].value - 0.912) < 1e-9
    assert abs(ws["C3"].value - 0.937) < 1e-9
    assert isinstance(ws["B3"].value, float)
    assert "%" in (ws["B3"].number_format or "")
    assert ws.freeze_panes == "A2"


@pytest.mark.skipif(not CLEAN.exists(), reason="缺少 clean_basic.pdf")
def test_xlsx_refuses_without_table(tmp_path: Path) -> None:
    from pdf2edit.structure import build_document
    from pdf2edit.writers.xlsx_writer import render

    with pytest.raises(ValueError, match="没有检测到表格"):
        render(build_document(CLEAN), tmp_path / "empty.xlsx")


# --- 压测样本：双栏排版 / 跨页长表格 ---

MULTI = ROOT / "fixtures" / "multicol.pdf"
LONG = ROOT / "fixtures" / "long_table.pdf"


@pytest.mark.skipif(not MULTI.exists(), reason="缺少 multicol.pdf")
def test_multicol_reading_order() -> None:
    from pdf2edit.structure import build_document

    doc = build_document(MULTI)
    assert not any(b.kind == "table" for b in doc.blocks), "双栏正文被误判成表格"

    paras = [b.text for b in doc.blocks if b.kind == "paragraph"]
    left = [p for p in paras if p.startswith("【左栏")]
    right = [p for p in paras if p.startswith("【右栏")]
    assert len(left) == 3, left
    assert len(right) == 3, right

    # 阅读顺序：左栏全部读完再读右栏
    idx_left_last = max(i for i, p in enumerate(paras) if p.startswith("【左栏"))
    idx_right_first = min(i for i, p in enumerate(paras) if p.startswith("【右栏"))
    assert idx_left_last < idx_right_first


@pytest.mark.skipif(not LONG.exists(), reason="缺少 long_table.pdf")
def test_cross_page_table_merged() -> None:
    from pdf2edit.structure import build_document

    doc = build_document(LONG)
    tables = [b for b in doc.blocks if b.kind == "table"]
    assert len(tables) == 1, f"跨页表格被切成了 {len(tables)} 张"

    rows = tables[0].rows
    assert rows[0] == ["序号", "名称", "数量", "比例"]
    assert sum(1 for r in rows if r[0] == "序号") == 1, "表头重复出现"
    assert len(rows) == 46, f"应为表头 + 45 行，实际 {len(rows)}"
    assert rows[-1][0] == "45"
    assert rows[1][2] == "10"
