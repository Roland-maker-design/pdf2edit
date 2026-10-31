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
