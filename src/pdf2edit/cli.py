"""命令行入口。

    python -m pdf2edit <pdf>                    # 单份，转 Markdown 到源文件旁边
    python -m pdf2edit <pdf> --to docx -o 输出.docx
    python -m pdf2edit a.pdf b.pdf 某个文件夹/ --to md docx -o 输出目录
    python -m pdf2edit --ui [--port 8765]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .convert import collect_pdfs, convert_many, convert_to_paths

_EXT = {"md": ".md", "docx": ".docx", "html": ".html", "pptx": ".pptx", "xlsx": ".xlsx"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="pdf2edit", description="把电子版 PDF 转成可编辑格式")
    ap.add_argument("pdfs", nargs="*", help="输入 PDF，可以给多个，也可以给文件夹")
    ap.add_argument(
        "--to",
        default=["md"],
        nargs="+",
        choices=list(_EXT),
        help="目标格式，可以给多个（默认 md）",
    )
    ap.add_argument(
        "-o",
        "--out",
        help="单份单格式时是输出文件名；批量时是输出目录",
    )
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

    if not args.pdfs:
        ap.print_help()
        return 2

    formats = list(dict.fromkeys(args.to))
    srcs = collect_pdfs([Path(p) for p in args.pdfs])
    if not srcs:
        print("这里没有 PDF 文件", file=sys.stderr)
        return 2

    single = len(srcs) == 1 and len(formats) == 1
    if single:
        src = srcs[0]
        target = Path(args.out) if args.out else src.with_suffix(_EXT[formats[0]])
        if target.is_dir():
            target = target / f"{src.stem}{_EXT[formats[0]]}"
        outcome = convert_to_paths(src, {formats[0]: target})
        results = [outcome]
        if outcome["ok"]:
            print(f"已生成 {outcome['files'][0]}")
            if outcome["reason"]:
                print(f"  {outcome['reason']}")
        else:
            print(f"拒绝转换 {src.name}：{outcome['reason']}", file=sys.stderr)
        return 0 if outcome["ok"] else 1

    outdir = Path(args.out) if args.out else Path.cwd() / "pdf2edit-out"
    print(f"共 {len(srcs)} 个文件，输出到 {outdir}（格式：{', '.join(formats)}）")

    def report(index: int, total: int, src: Path, _outcome: dict) -> None:
        print(f"  [{index}/{total}] {Path(src).name}")

    results = convert_many(srcs, outdir, formats, on_progress=report)

    ok = sum(1 for r in results if r["ok"])
    failed = [r for r in results if not r["ok"]]
    print(f"完成：成功 {ok} · 失败 {len(failed)}")
    for r in failed:
        print(f"  ✗ {Path(r['src']).name} — {r['reason']}", file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

