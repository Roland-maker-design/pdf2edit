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


def f1_deep_list(out: Path) -> None:
    """四级嵌套列表。"""
    doc = pymupdf.open()
    p = _page(doc)
    p.insert_text((60, 80), "四级列表测试", fontsize=16, fontname=CJK)
    rows = [
        (80, "• 一级：总体要求"),
        (110, "◦ 二级：数据准备"),
        (140, "▪ 三级：清洗规则"),
        (170, "· 四级：缺失值处理"),
        (140, "▪ 三级：校验规则"),
        (110, "◦ 二级：模型训练"),
        (80, "• 一级：交付标准"),
    ]
    y = 120.0
    for x, text in rows:
        p.insert_text((x, y), text, fontsize=11, fontname=CJK)
        y += 18
    doc.save(str(out))


def f2_multilang(out: Path) -> None:
    """中日韩俄混排（每种语言都用支持该字符集的字体，否则生成端就丢字）。"""
    doc = pymupdf.open()
    p = _page(doc)
    p.insert_text((60, 80), "多语言混排测试", fontsize=16, fontname=CJK)

    arial = r"C:\Windows\Fonts\arial.ttf"
    lines = [
        (CJK, "中文：本项目用于验证多语言混排的提取效果。"),
        (CJK, "日本語：このプロジェクトは多言語の抽出を検証します。"),
        ("korea", "한국어: 이 프로젝트는 다국어 추출을 검증합니다."),
    ]
    y = 120.0
    for font, line in lines:
        p.insert_text((60, y), line, fontsize=11, fontname=font)
        y += 24

    # 西里尔字母需要 Unicode 字体
    p.insert_text((60, y), "Русский: Этот проект проверяет извлечение текста.",
                  fontsize=11, fontname="Arial", fontfile=arial)
    y += 24

    p.insert_text((60, y), "混合：中文 + English + 日本語 + Русский 在一行里。",
                  fontsize=11, fontname=CJK)
    doc.save(str(out))


def f3_vertical_text(out: Path) -> None:
    """旋转 90 度的文字（模拟竖排/侧标签）。"""
    doc = pymupdf.open()
    p = _page(doc)
    p.insert_text((60, 80), "竖排文字测试", fontsize=16, fontname=CJK)
    p.insert_text((540, 120), "这是旋转了九十度的侧边文字", fontsize=11, fontname=CJK, rotate=90)
    for i in range(4):
        p.insert_text((60, 130 + i * 18), f"正文第 {i + 1} 行，旁边有一段旋转文字。",
                      fontsize=11, fontname=CJK)
    doc.save(str(out))



def g1_gov_document(out: Path) -> None:
    """中文公文样式：居中标红标题、仿宋正文、首行缩进、右下落款、页脚页码。"""
    doc = pymupdf.open()
    p = doc.new_page()                      # A4
    width = 595.0

    # 标题：居中、二号字、红色（公文标准是红色小标宋）
    title = "关于加强文档转换质量管理的通知"
    tw = len(title) * 16 * 0.6
    p.insert_text(((width - tw) / 2, 120), title, fontsize=16, fontname=CJK,
                  color=(0.8, 0.05, 0.05))

    p.insert_text((470, 150), "文档字〔2026〕7 号", fontsize=10, fontname=CJK)

    y = 190.0
    body = [
        "各部门、各单位：",
        "为提升电子文档的转换质量，现就有关事项通知如下。",
        "一、明确责任。各部门应当指定专人负责文档的归档与转换，确保来源可靠、格式规范。",
        "二、规范流程。转换前须核验文档是否为电子版原件，扫描件、翻拍件不得作为归档底稿。",
        "三、加强检查。每季度开展一次抽查，对转换质量不合格的单位予以通报。",
    ]
    for line in body:
        p.insert_text((60, y), line, fontsize=12, fontname=CJK)
        y += 26

    p.insert_text((430, 380), "文档管理办公室", fontsize=12, fontname=CJK)
    p.insert_text((420, 404), "2026 年 11 月 1 日", fontsize=12, fontname=CJK)

    p.insert_text((250, 800), "— 1 —", fontsize=10, fontname=CJK)
    doc.save(str(out))


def g2_mixed_scan(out: Path) -> None:
    """混合型：3 页文字 + 1 页纯图片（模拟扫描页）。"""
    doc = pymupdf.open()
    for i in range(1, 4):
        p = doc.new_page()
        p.insert_text((60, 80), f"第 {i} 节", fontsize=16, fontname=CJK)
        for j in range(8):
            p.insert_text((60, 120 + j * 18),
                          f"第 {i} 页正文第 {j + 1} 行，本节共八行文字，用于占位。",
                          fontsize=11, fontname=CJK)

    # 第 3 页做成纯图片（扫描页），没有任何文字层
    scanned = doc.new_page()
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 400, 560), 0)
    pix.set_rect(pix.irect, (235, 235, 235))
    for row in range(10):
        pix.set_rect(pymupdf.IRect(30, 40 + row * 50, 370, 46 + row * 50), (60, 60, 60))
    scanned.insert_image(pymupdf.Rect(60, 80, 460, 640), pixmap=pix)

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
        "f1_deep_list": f1_deep_list,
        "f2_multilang": f2_multilang,
        "f3_vertical_text": f3_vertical_text,
        "g1_gov_document": g1_gov_document,
        "g2_mixed_scan": g2_mixed_scan,
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
