"""生成一份"干净"的测试 PDF：有真实文本层、正常 ToUnicode。

用 PyMuPDF 直接绘制，模拟 Word/LaTeX 导出的文档结构：
H1、H2、中文正文、列表、页码。
"""

from __future__ import annotations

from pathlib import Path

import pymupdf

CJK = "china-s"   # PyMuPDF 内置简体中文字体
LAT = "helv"


def build(out_path: Path) -> None:
    doc = pymupdf.open()

    # --- 第 1 页 ---
    p = doc.new_page()
    p.insert_text((72, 90), "第一章 总论", fontsize=20, fontname=CJK)

    y = 130.0
    p.insert_text((72, y), "这是一段中文正文，用来测试段落合并是否正确。", fontsize=11, fontname=CJK)
    y += 16
    p.insert_text((72, y), "第二行紧接着上一行，不应该被插入空格。", fontsize=11, fontname=CJK)
    y += 32

    for item in ("• 第一条要点", "• 第二条要点"):
        p.insert_text((72, y), item, fontsize=11, fontname=CJK)
        y += 16

    p.insert_text((300, 800), "1", fontsize=9, fontname=LAT)

    # --- 第 2 页 ---
    p2 = doc.new_page()
    p2.insert_text((72, 90), "1.1 背景", fontsize=14, fontname=CJK)
    p2.insert_text(
        (72, 120),
        "Second page paragraph in English, to check that spaces are kept.",
        fontsize=11,
        fontname=LAT,
    )
    p2.insert_text((300, 800), "2", fontsize=9, fontname=LAT)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out_path))
    print(f"已生成 {out_path}")


if __name__ == "__main__":
    build(Path(__file__).with_name("clean_basic.pdf"))
