"""边界与异常样本生成器。

四轮压测：
A. 结构特性：首行缩进、多级列表、代码块、上下标、中英混排
B. PDF 特性：旋转页、混合页面尺寸、空白页、加密、表单
C. 规模：100 页、超长单行、高密度小字
D. 异常：截断损坏、非 PDF 文件、零页
"""

from __future__ import annotations

from pathlib import Path

import pymupdf

CJK = "china-s"
MONO = "cour"
LAT_FALLBACK = "helv"


def _page(doc):
    return doc.new_page()


def a1_first_line_indent(out: Path) -> None:
    doc = pymupdf.open()
    p = _page(doc)
    p.insert_text((60, 90), "首行缩进测试", fontsize=16, fontname=CJK)
    y = 130.0
    for para in range(3):
        p.insert_text((60 + 21, y), f"第{para + 1}段第一行从缩进位置开始，用于验证首行缩进是否被误判成列表。",
                      fontsize=11, fontname=CJK)
        y += 16
        p.insert_text((60, y), "这是紧随其后的续行，位置回到正文左边界，不应该算列表项。", fontsize=11, fontname=CJK)
        y += 28
    doc.save(str(out))


def a2_nested_list(out: Path) -> None:
    doc = pymupdf.open()
    p = _page(doc)
    p.insert_text((60, 90), "多级列表测试", fontsize=16, fontname=CJK)
    rows = [
        (80, "• 第一级条目一"),
        (110, "◦ 第二级条目一"),
        (140, "▪ 第三级条目一"),
        (110, "◦ 第二级条目二"),
        (80, "• 第一级条目二"),
    ]
    y = 130.0
    for x, text in rows:
        p.insert_text((x, y), text, fontsize=11, fontname=CJK)
        y += 18
    doc.save(str(out))


def a3_code_block(out: Path) -> None:
    doc = pymupdf.open()
    p = _page(doc)
    p.insert_text((60, 90), "代码块测试", fontsize=16, fontname=CJK)
    p.insert_text((60, 120), "下面是一段代码，使用等宽字体，缩进有意义。", fontsize=11, fontname=CJK)
    y = 150.0
    for line in ("def hello(name):", '    print(f"hi {name}")', "    return None", "", "hello('world')"):
        if line:
            p.insert_text((60, y), line, fontsize=10, fontname=MONO)
        y += 14
    doc.save(str(out))


def a4_super_subscript(out: Path) -> None:
    doc = pymupdf.open()
    p = _page(doc)
    p.insert_text((60, 90), "上下标与公式测试", fontsize=16, fontname=CJK)
    p.insert_text((60, 130), "水分子是 H", fontsize=12, fontname=CJK)
    p.insert_text((135, 135), "2", fontsize=8, fontname=LAT_FALLBACK)
    p.insert_text((143, 130), "O，能量公式 E=mc", fontsize=12, fontname=CJK)
    p.insert_text((250, 135), "2", fontsize=8, fontname=LAT_FALLBACK)
    p.insert_text((258, 130), "，面积 S=πr²。", fontsize=12, fontname=CJK)
    doc.save(str(out))


def a5_mixed_cjk_latin(out: Path) -> None:
    doc = pymupdf.open()
    p = _page(doc)
    p.insert_text((60, 90), "中英混排测试", fontsize=16, fontname=CJK)
    lines = [
        "本次实验使用 Python 3.10 和 PyMuPDF 1.28，处理了 1,234 份文件。",
        "准确率从 91.2% 提升到 93.7%，误报率下降到 2.4%。",
        "The quick brown fox jumps over the lazy dog 12345 times.",
    ]
    y = 130.0
    for line in lines:
        p.insert_text((60, y), line, fontsize=11, fontname=CJK)
        y += 18
    doc.save(str(out))


def b1_rotated(out: Path) -> None:
    doc = pymupdf.open()
    p = _page(doc)
    p.insert_text((60, 90), "旋转页面测试", fontsize=16, fontname=CJK)
    for i in range(4):
        p.insert_text((60, 130 + i * 18), f"这段文字所在的页面被旋转了 90 度，第 {i + 1} 行。",
                      fontsize=11, fontname=CJK)
    p.set_rotation(90)
    doc.save(str(out))


def b2_mixed_sizes(out: Path) -> None:
    doc = pymupdf.open()
    p1 = doc.new_page(width=595, height=842)        # A4
    p1.insert_text((60, 90), "A4 页面", fontsize=16, fontname=CJK)
    for i in range(6):
        p1.insert_text((60, 130 + i * 18), f"A4 页面的第 {i + 1} 行正文，用于验证异尺寸页面的处理。",
                       fontsize=11, fontname=CJK)
    p2 = doc.new_page(width=842, height=1191)       # A3
    p2.insert_text((60, 90), "A3 页面", fontsize=16, fontname=CJK)
    for i in range(6):
        p2.insert_text((60, 130 + i * 18), f"A3 页面的第 {i + 1} 行正文，页面更宽更大。",
                       fontsize=11, fontname=CJK)
    doc.save(str(out))


def b3_blank_middle(out: Path) -> None:
    doc = pymupdf.open()
    p1 = _page(doc)
    p1.insert_text((60, 90), "第一页有内容", fontsize=14, fontname=CJK)
    for i in range(5):
        p1.insert_text((60, 130 + i * 18), f"第一页正文第 {i + 1} 行，后面会跟一个空白页。",
                       fontsize=11, fontname=CJK)
    _page(doc)                                       # 空白页
    p3 = _page(doc)
    p3.insert_text((60, 90), "第三页有内容", fontsize=14, fontname=CJK)
    for i in range(5):
        p3.insert_text((60, 130 + i * 18), f"第三页正文第 {i + 1} 行，用于确认空白页不影响后续。",
                       fontsize=11, fontname=CJK)
    doc.save(str(out))


def b4_encrypted(out: Path) -> None:
    doc = pymupdf.open()
    p = _page(doc)
    p.insert_text((60, 90), "加密文档测试", fontsize=16, fontname=CJK)
    p.insert_text((60, 130), "这份文件设置了所有者密码，但用户密码为空，应当能正常读取。",
                  fontsize=11, fontname=CJK)
    doc.save(str(out), encryption=pymupdf.PDF_ENCRYPT_AES_256,
             owner_pw="owner-secret", user_pw="")


def b5_form(out: Path) -> None:
    doc = pymupdf.open()
    p = _page(doc)
    p.insert_text((60, 90), "表单字段测试", fontsize=16, fontname=CJK)
    p.insert_text((60, 130), "下面是一个表单字段，转换时应当被忽略而不是造成崩溃。",
                  fontsize=11, fontname=CJK)
    for i in range(4):
        p.insert_text((60, 170 + i * 18), f"表单页正文第 {i + 1} 行，用于保证字符量达到闸门要求。",
                      fontsize=11, fontname=CJK)
    widget = pymupdf.Widget()
    widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
    widget.field_name = "name"
    widget.rect = pymupdf.Rect(100, 236, 300, 256)
    p.add_widget(widget)
    doc.save(str(out))


def c1_many_pages(out: Path) -> None:
    doc = pymupdf.open()
    for i in range(1, 101):
        p = doc.new_page()
        p.insert_text((60, 90), f"第 {i} 章", fontsize=16, fontname=CJK)
        for j in range(5):
            p.insert_text((60, 130 + j * 18), f"这是第 {i} 页的第 {j + 1} 行正文内容。",
                          fontsize=11, fontname=CJK)
    doc.save(str(out))


def c2_long_line(out: Path) -> None:
    doc = pymupdf.open()
    p = _page(doc)
    long_text = "这是一段非常长的、不会自动换行的文本" * 6
    p.insert_text((20, 120), long_text, fontsize=8, fontname=CJK)
    doc.save(str(out))


def e1_merged_cells(out: Path) -> None:
    """表头横跨三列的合并单元格（用线条画格子）。"""
    doc = pymupdf.open()
    p = _page(doc)
    p.insert_text((60, 70), "合并单元格测试", fontsize=16, fontname=CJK)

    xs = [60, 180, 300, 420]
    ys = [100, 130, 160, 190]
    for y in ys:
        p.draw_line(pymupdf.Point(xs[0], y), pymupdf.Point(xs[-1], y), width=0.7)
    for x in [xs[0], xs[-1]]:
        p.draw_line(pymupdf.Point(x, ys[0]), pymupdf.Point(x, ys[-1]), width=0.7)
    # 表头下方不画竖线 → 视觉上是一个跨三列的单元格
    for x in xs[1:-1]:
        for y0, y1 in ((ys[1], ys[3]),):
            p.draw_line(pymupdf.Point(x, y0), pymupdf.Point(x, y1), width=0.7)

    p.insert_text((180, 122), "合并表头（跨三列）", fontsize=11, fontname=CJK)
    data = [("甲", "乙", "丙"), ("1", "2", "3")]
    for r, row in enumerate(data):
        for c, value in enumerate(row):
            p.insert_text((xs[c] + 20, ys[r + 1] + 20), value, fontsize=11, fontname=CJK)
    doc.save(str(out))


def e2_multiline_cell(out: Path) -> None:
    """单元格里有两行文字。"""
    doc = pymupdf.open()
    p = _page(doc)
    p.insert_text((60, 70), "单元格内换行测试", fontsize=16, fontname=CJK)

    xs = [60, 220, 360, 500]
    ys = [100, 150, 200, 250]
    for y in ys:
        p.draw_line(pymupdf.Point(xs[0], y), pymupdf.Point(xs[-1], y), width=0.7)
    for x in xs:
        p.draw_line(pymupdf.Point(x, ys[0]), pymupdf.Point(x, ys[-1]), width=0.7)

    p.insert_text((80, 125), "项目", fontsize=11, fontname=CJK)
    p.insert_text((240, 125), "说明", fontsize=11, fontname=CJK)
    p.insert_text((380, 125), "数值", fontsize=11, fontname=CJK)

    p.insert_text((80, 175), "甲", fontsize=11, fontname=CJK)
    p.insert_text((240, 170), "第一行说明", fontsize=11, fontname=CJK)
    p.insert_text((240, 188), "第二行说明", fontsize=11, fontname=CJK)   # 同一格第二行
    p.insert_text((380, 175), "12", fontsize=11, fontname=CJK)

    p.insert_text((80, 225), "乙", fontsize=11, fontname=CJK)
    p.insert_text((240, 225), "单行说明", fontsize=11, fontname=CJK)
    p.insert_text((380, 225), "34", fontsize=11, fontname=CJK)
    doc.save(str(out))


def e3_huge_font(out: Path) -> None:
    """海报级的超大标题。"""
    doc = pymupdf.open()
    p = doc.new_page(width=595, height=842)
    p.insert_text((40, 200), "年度报告", fontsize=72, fontname=CJK)
    p.insert_text((40, 280), "2025 年度工作总结与展望", fontsize=28, fontname=CJK)
    for i in range(4):
        p.insert_text((40, 340 + i * 20), f"这是正文第 {i + 1} 行，用于验证超大字号与正文的相对关系。",
                      fontsize=12, fontname=CJK)
    doc.save(str(out))


def d1_corrupt(out: Path) -> None:
    doc = pymupdf.open()
    p = _page(doc)
    p.insert_text((60, 90), "这份文件会被截断", fontsize=16, fontname=CJK)
    tmp = out.with_suffix(".tmp.pdf")
    doc.save(str(tmp))
    data = tmp.read_bytes()
    out.write_bytes(data[: len(data) // 2])
    tmp.unlink()


def d2_not_pdf(out: Path) -> None:
    out.write_text("这不是一个 PDF 文件，只是一段普通文本。", encoding="utf-8")


def main() -> None:
    out = Path(__file__).resolve().parent / "edge"
    out.mkdir(exist_ok=True)

    cases = {
        "a1_first_line_indent": a1_first_line_indent,
        "a2_nested_list": a2_nested_list,
        "a3_code_block": a3_code_block,
        "a4_super_subscript": a4_super_subscript,
        "a5_mixed_cjk_latin": a5_mixed_cjk_latin,
        "b1_rotated": b1_rotated,
        "b2_mixed_sizes": b2_mixed_sizes,
        "b3_blank_middle": b3_blank_middle,
        "b4_encrypted": b4_encrypted,
        "b5_form": b5_form,
        "c1_many_pages": c1_many_pages,
        "c2_long_line": c2_long_line,
        "e1_merged_cells": e1_merged_cells,
        "e2_multiline_cell": e2_multiline_cell,
        "e3_huge_font": e3_huge_font,
        "d1_corrupt": d1_corrupt,
        "d2_not_pdf": d2_not_pdf,
    }
    for name, fn in cases.items():
        path = out / f"{name}.pdf"
        try:
            fn(path)
            print(f"  ok  {name}.pdf")
        except Exception as exc:  # noqa: BLE001
            print(f"  FAIL {name}: {exc}")


if __name__ == "__main__":
    main()
