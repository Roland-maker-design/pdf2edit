"""提取层：把 PDF 变成带几何信息的行序列。

只负责"取出来、量准尺寸"，不做任何语义判断。
"""

from __future__ import annotations

from dataclasses import dataclass

import pymupdf


@dataclass
class Line:
    text: str                            # 去掉首尾空白，供分类/合并使用
    bbox: tuple[float, float, float, float]
    size: float
    font: str
    bold: bool
    page: int
    page_height: float
    page_width: float
    raw: str = ""                        # 原始文本，保留行首缩进（代码块需要）


def extract_lines(doc: pymupdf.Document) -> list[Line]:
    lines: list[Line] = []
    for pno, page in enumerate(doc, start=1):
        data = page.get_text("dict")
        for block in data.get("blocks", []):
            if block.get("type") != 0:      # 0 = 文本块
                continue
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                if not spans:
                    continue
                text = "".join(s.get("text", "") for s in spans)
                if not text.strip():
                    continue
                size = max(s.get("size", 0.0) for s in spans)
                font = spans[0].get("font", "")
                bold = any(
                    ("Bold" in s.get("font", "")) or (s.get("flags", 0) & 16)
                    for s in spans
                )
                lines.append(
                    Line(
                        text=text.strip(),
                        bbox=tuple(line["bbox"]),  # type: ignore[arg-type]
                        size=size,
                        font=font,
                        bold=bold,
                        page=pno,
                        page_height=page.rect.height,
                        page_width=page.rect.width,
                        raw=text.rstrip("\n"),
                    )
                )
    return lines
