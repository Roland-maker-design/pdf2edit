"""质量闸门：判断一份 PDF 的文字层可不可信。

依据是硬事实——字体有没有 ToUnicode 码表，而不是猜输出质量。
宁可拒绝，也不要输出需要人肉校对的东西。
"""

from __future__ import annotations

from dataclasses import dataclass

import pymupdf

MIN_CHARS_PER_PAGE = 20.0
MAX_BAD_RATIO = 0.05
MAX_UNMAPPED_SHARE = 0.20


@dataclass
class QualityReport:
    ok: bool
    bad_char_ratio: float = 0.0
    chars_per_page: float = 0.0
    unmapped_share: float = 0.0
    reason: str = ""


def _unreliable_fonts(doc: pymupdf.Document, page: pymupdf.Page) -> set[str]:
    """返回这一页上"无法可靠解码"的字体基名（去掉子集前缀）。

    判据：既没有 ToUnicode 码表，Encoding 又是 Identity-H/V。
    这两种情况同时出现时，字符码与 Unicode 之间不存在任何已知映射，
    提取结果必然是乱码。基础 14 字体（helv/times）虽有标准编码，
    Type0 字体若带具名 CMap（如 GBK-EUC-H）也仍可解码，都不算坏。
    """
    bad: set[str] = set()
    for f in page.get_fonts(full=True):
        xref, basefont = f[0], f[3]
        tounicode = doc.xref_get_key(xref, "ToUnicode")[1]
        encoding = doc.xref_get_key(xref, "Encoding")[1]
        has_no_map = tounicode in ("null", "none")
        is_identity = "Identity" in (encoding or "")
        if has_no_map and is_identity:
            bad.add(basefont.split("+")[-1])
    return bad


def _unmapped_share(doc: pymupdf.Document) -> float:
    """统计有多少字符由"无法解码"的字体渲染。"""
    total = unmapped = 0
    for page in doc:
        bad = _unreliable_fonts(doc, page)
        if not bad:
            continue
        try:
            trace = page.get_texttrace()
        except Exception:
            continue
        for span in trace:
            font = span.get("font", "").split("+")[-1]
            count = len(span.get("chars", ()))
            total += count
            if font in bad:
                unmapped += count
    # 分母用全文字符数，避免只统计坏字体所在页
    if total == 0:
        return 0.0
    return unmapped / total


def assess(doc: pymupdf.Document) -> QualityReport:
    if doc.page_count == 0:
        return QualityReport(False, reason="PDF 没有页面")

    text = "".join(p.get_text("text") for p in doc)
    total = len(text)
    bad = text.count("\ufffd")
    ratio = bad / total if total else 1.0
    cpp = total / doc.page_count

    if cpp < MIN_CHARS_PER_PAGE:
        return QualityReport(
            False, ratio, cpp, 0.0,
            f"每页仅 {cpp:.0f} 个字符，疑似扫描件或图片型 PDF，本项目不处理",
        )

    share = _unmapped_share(doc)
    if share > MAX_UNMAPPED_SHARE:
        return QualityReport(
            False, ratio, cpp, share,
            f"文字层不可靠：{share:.0%} 的字符所用的字体缺少 ToUnicode 码表，"
            f"提取结果会是乱码（常见于 PostScript 打印生成的 PDF）",
        )

    if ratio > MAX_BAD_RATIO:
        return QualityReport(
            False, ratio, cpp, share,
            f"文字层不可靠：{ratio:.1%} 的字符无法映射到 Unicode",
        )

    return QualityReport(True, ratio, cpp, share)
