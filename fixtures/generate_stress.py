"""生成压测样本：三栏、页眉页脚、脚注。

用 PyMuPDF 直接画，坐标完全可控，能精确复现这三类结构信号。
"""

from __future__ import annotations

from pathlib import Path

import pymupdf

CJK = "china-s"
LAT = "helv"


def three_columns(path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page()          # A4: 595 x 842
    page.insert_text((50, 70), "三栏排版测试", fontsize=20, fontname=CJK)

    cols = [(50, "第一"), (222, "第二"), (394, "第三")]
    for x, label in cols:
        y = 110.0
        for i in range(1, 4):
            text = f"【{label}栏第{i}段】这是用于验证三栏排版的示例文本，内容需要足够长以便折行。"
            # 每行 14 字（约 147pt），栏间距 172pt，保证栏之间真有空白走廊
            for k in range(0, len(text), 14):
                chunk = text[k:k + 14]
                if chunk:
                    page.insert_text((x, y), chunk, fontsize=10.5, fontname=CJK)
                    y += 15
            y += 8
    doc.save(str(path))
    print(f"已生成 {path}")


def headers_footers(path: Path) -> None:
    doc = pymupdf.open()
    for pno in (1, 2):
        page = doc.new_page()
        page.insert_text((60, 40), "内部资料 · 请勿外传", fontsize=8, fontname=CJK)      # 页眉
        page.insert_text((60, 100), f"第{pno}节 正文标题", fontsize=16, fontname=CJK)
        y = 140.0
        for i in range(6):
            page.insert_text(
                (60, y),
                f"这是第{pno}页的第{i + 1}行正文，用来验证页眉页脚会不会混进正文。",
                fontsize=11,
                fontname=CJK,
            )
            y += 18
        page.insert_text((60, 800), f"内部资料 · 第 {pno} 页 · 共 2 页", fontsize=8, fontname=CJK)  # 页脚
    doc.save(str(path))
    print(f"已生成 {path}")


def footnotes(path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((60, 90), "脚注测试", fontsize=18, fontname=CJK)

    y = 130.0
    lines = [
        "正文第一段提到了一个需要注释的概念[1]，这里继续写一些内容让段落足够长。",
        "正文第二段同样引用了一个来源[2]，用于检验脚注是否会被错误地并入正文。",
    ]
    for idx, line in enumerate(lines):
        page.insert_text((60, y), line, fontsize=11, fontname=CJK)
        y += 32 if idx == 0 else 20      # 段间留更大间距，符合真实排版

    # 脚注分隔线 + 脚注区（字号更小，位于页面底部）
    page.draw_line(pymupdf.Point(60, 740), pymupdf.Point(200, 740), color=(0, 0, 0), width=0.5)
    page.insert_text((60, 756), "[1] 参见某文献，2019 年。", fontsize=8, fontname=CJK)
    page.insert_text((60, 770), "[2] 参见另一文献，2021 年。", fontsize=8, fontname=CJK)

    doc.save(str(path))
    print(f"已生成 {path}")


if __name__ == "__main__":
    out = Path(__file__).resolve().parent
    three_columns(out / "three_cols.pdf")
    headers_footers(out / "headers_footers.pdf")
    footnotes(out / "footnotes.pdf")
