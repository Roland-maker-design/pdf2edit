"""PDF 体检脚本 —— 判断一份 PDF 属于哪一类，决定它能走哪条转换链路。

用法:
    python tools/probe_pdf.py <pdf> [<pdf> ...]

输出: 页数、文本层字符数、图像覆盖率、字体清单、是否伪电子版等。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pymupdf as fitz  # PyMuPDF（1.28 起 firz 已弃用）


def probe(path: Path) -> dict:
    doc = fitz.open(path)
    pages = doc.page_count

    text_chars = 0
    image_area = 0.0
    page_area = 0.0
    fonts: set[str] = set()
    text_pages = 0

    for page in doc:
        area = abs(page.rect.width * page.rect.height)
        page_area += area

        chars = len(page.get_text("text").strip())
        text_chars += chars
        if chars > 50:
            text_pages += 1

        for img in page.get_images(full=True):
            try:
                for r in page.get_image_rects(img[0]):
                    image_area += abs(r.width * r.height)
            except Exception:
                pass

        for f in page.get_fonts(full=True):
            fonts.add(f[3])

    return {
        "file": path.name,
        "pages": pages,
        "text_chars": text_chars,
        "chars_per_page": round(text_chars / pages, 1) if pages else 0,
        "text_page_ratio": round(text_pages / pages, 2) if pages else 0,
        "image_coverage": round(min(image_area / page_area, 9.99), 2) if page_area else 0,
        "fonts": sorted(fonts),
    }


def classify(p: dict) -> str:
    if p["chars_per_page"] < 20:
        return "扫描件 / 图片型（无文本层）—— 本项目不支持"
    if p["image_coverage"] > 0.85 and p["chars_per_page"] < 300:
        return "疑似伪电子版（整页图 + 薄文本层）—— 需人工确认"
    if p["text_page_ratio"] < 0.8:
        return "混合型（部分页面无文本层）—— 需按页分流"
    return "电子版 PDF（可用）"


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    for a in argv[1:]:
        path = Path(a)
        if not path.exists():
            print(f"跳过不存在的文件: {path}")
            continue
        try:
            p = probe(path)
        except Exception as e:  # noqa: BLE001
            print(f"[{path.name}] 解析失败: {e}")
            continue

        print(f"\n=== {p['file']} ===")
        print(f"  页数            : {p['pages']}")
        print(f"  文本字符总数    : {p['text_chars']}（每页 {p['chars_per_page']}）")
        print(f"  有文本的页占比  : {p['text_page_ratio']}")
        print(f"  图像覆盖率      : {p['image_coverage']}")
        print(f"  字体            : {', '.join(p['fonts']) if p['fonts'] else '（无嵌入字体）'}")
        print(f"  判定            : {classify(p)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
