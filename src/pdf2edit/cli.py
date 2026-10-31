"""命令行入口。

    python -m pdf2edit <pdf> --to md|docx|html|pptx|xlsx [-o 输出路径]
    python -m pdf2edit --ui [--port 8765]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pymupdf

from .quality import assess
from .structure import build_document
from .writers import docx_writer, html_writer, markdown, pptx_writer, xlsx_writer

_EXT = {"md": ".md", "docx": ".docx", "html": ".html", "pptx": ".pptx", "xlsx": ".xlsx"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="pdf2edit", description="把电子版 PDF 转成可编辑格式")
    ap.add_argument("pdf", nargs="?", help="输入 PDF 路径")
    ap.add_argument("--to", default="md", choices=list(_EXT), help="目标格式")
    ap.add_argument("-o", "--out", help="输出文件路径（默认与输入同名）")
    ap.add_argument("--ui", action="store_true", help="启动本地网页界面")
    ap.add_argument("--window", action="store_true", help="启动桌面窗口界面")
    ap.add_argument("--port", type=int, default=8765, help="网页界面端口")
    ap.add_argument("--host", default="127.0.0.1", help="监听地址（默认只监听本机）")
    args = ap.parse_args(argv)

    if args.window:
        from .desktop import run as run_desktop

        run_desktop()
        return 0

    if args.ui:
        from .ui import run

        run(host=args.host, port=args.port)
        return 0

    if not args.pdf:
        ap.print_help()
        return 2

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
    elif args.to == "xlsx":
        try:
            xlsx_writer.render(ir, out)
        except ValueError as exc:
            print(f"拒绝转换：{exc}", file=sys.stderr)
            return 1
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
