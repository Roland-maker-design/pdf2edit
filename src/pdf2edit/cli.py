"""命令行入口：python -m pdf2edit <pdf> --to md|docx|html|pptx [-o 输出路径]"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pymupdf

from .quality import assess
from .structure import build_document
from .writers import docx_writer, html_writer, markdown, pptx_writer

_EXT = {"md": ".md", "docx": ".docx", "html": ".html", "pptx": ".pptx"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="pdf2edit", description="把电子版 PDF 转成可编辑格式")
    ap.add_argument("pdf", help="输入 PDF 路径")
    ap.add_argument("--to", default="md", choices=list(_EXT), help="目标格式")
    ap.add_argument("-o", "--out", help="输出文件路径（默认与输入同名）")
    args = ap.parse_args(argv)

    src = Path(args.pdf)
    if not src.exists():
        print(f"找不到文件: {src}", file=sys.stderr)
        return 2

    doc = pymupdf.open(str(src))
    report = assess(doc)
    if not report.ok:
        print(f"拒绝转换：{report.reason}", file=sys.stderr)
        return 1

    ir = build_document(src)
    out = Path(args.out) if args.out else src.with_suffix(_EXT[args.to])

    if args.to == "docx":
        docx_writer.render(ir, out)
    elif args.to == "pptx":
        pptx_writer.render(ir, out)
    elif args.to == "html":
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html_writer.render(ir), encoding="utf-8")
    else:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(markdown.render(ir), encoding="utf-8")

    print(f"已生成 {out}（{len(ir.blocks)} 个块）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
