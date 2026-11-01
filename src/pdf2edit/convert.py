"""共享转换流水线：命令行、网页 UI、桌面窗口都走这一份。

这里是唯一的"文件进 → 结果出"入口，避免三处 UI 各自复制逻辑。
"""

from __future__ import annotations

from pathlib import Path

import pymupdf

from .quality import assess
from .structure import build_document
from .writers import docx_writer, html_writer, markdown, pptx_writer, xlsx_writer

SUPPORTED_FORMATS = ["md", "docx", "html", "pptx", "xlsx"]
FORMAT_LABELS = {
    "md": "Markdown",
    "docx": "Word",
    "html": "HTML",
    "pptx": "PowerPoint",
    "xlsx": "Excel",
}


def _write(fmt: str, ir, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "docx":
        docx_writer.render(ir, out)
    elif fmt == "pptx":
        pptx_writer.render(ir, out)
    elif fmt == "xlsx":
        xlsx_writer.render(ir, out)
    elif fmt == "html":
        out.write_text(html_writer.render(ir), encoding="utf-8")
    elif fmt == "md":
        out.write_text(markdown.render(ir), encoding="utf-8")
    else:
        raise ValueError(f"不支持的格式：{fmt}")


def collect_pdfs(paths) -> list[Path]:
    """把「文件 + 文件夹」的混合输入展开成一份 PDF 清单。

    文件夹只取当前一层，不递归——避免手滑拖了整个盘。重复项按真实路径去重。
    """
    seen: set[str] = set()
    found: list[Path] = []
    for entry in paths:
        path = Path(entry)
        if path.is_dir():
            candidates = sorted(
                p for p in path.iterdir() if p.is_file() and p.suffix.lower() == ".pdf"
            )
        elif path.is_file() and path.suffix.lower() == ".pdf":
            candidates = [path]
        else:
            continue
        for candidate in candidates:
            key = str(candidate.resolve()).lower()
            if key in seen:
                continue
            seen.add(key)
            found.append(candidate)
    return found


def unique_name(name: str, used: set[str]) -> str:
    """在 used 里没被占用的前提下返回 name，否则依次试 name (2)、name (3)。

    选中的名字会记进 used。比较时忽略大小写——Windows 上
    Report.pdf 和 report.pdf 会落到同一个文件。
    """
    stem = Path(name).stem
    suffix = Path(name).suffix
    candidate = name
    counter = 2
    while candidate.lower() in used:
        candidate = f"{stem} ({counter}){suffix}"
        counter += 1
    used.add(candidate.lower())
    return candidate


def plan_outputs(srcs, outdir, formats) -> list[tuple[Path, dict[str, Path]]]:
    """决定每份 PDF 的每种格式写到哪个文件。

    只有同时「多份文件 × 多种格式」才按文件建子文件夹，
    否则平铺——单个文件转两三种格式时冒出个文件夹反而碍事。
    同名文件（不同目录里都叫 report.pdf）按 report (2) 递增区分。

    返回和输入一一对应的列表，而不是以路径为键的字典：
    同一个文件传两次时字典会把两条并成一条。
    """
    outdir = Path(outdir)
    nested = len(srcs) > 1 and len(formats) > 1
    used: set[str] = set()
    plan: list[tuple[Path, dict[str, Path]]] = []
    for entry in srcs:
        src = Path(entry)
        name = unique_name(src.stem, used)
        folder = outdir / name if nested else outdir
        plan.append((src, {fmt: folder / f"{name}.{fmt}" for fmt in formats}))
    return plan


def convert_to_paths(src: Path, targets: dict[str, Path]) -> dict:
    """转换单个文件到指定的那几个输出路径。"""
    src = Path(src)

    try:
        doc = pymupdf.open(str(src))
    except Exception:  # noqa: BLE001 - 非 PDF / 损坏文件要给友好提示而不是抛栈
        return {"ok": False, "reason": "这不是一个有效的 PDF 文件", "files": []}

    if doc.page_count == 0:
        return {"ok": False, "reason": "PDF 里没有页面", "files": []}

    report = assess(doc)
    if not report.ok:
        return {"ok": False, "reason": report.reason, "files": []}

    try:
        ir = build_document(src)
    except ValueError as exc:
        return {"ok": False, "reason": str(exc), "files": []}

    produced: list[Path] = []
    skipped: list[str] = []
    for fmt, out in targets.items():
        try:
            _write(fmt, ir, Path(out))
            produced.append(Path(out))
        except ValueError as exc:
            skipped.append(f"{FORMAT_LABELS.get(fmt, fmt)} 已跳过：{exc}")

    suspicious = sum(1 for b in ir.blocks if b.kind == "warning")
    if suspicious:
        skipped.append(f"另有 {suspicious} 处结构可疑，已在输出里标注")

    return {
        "ok": bool(produced),
        "reason": "；".join(skipped),
        "files": produced,
        "warnings": suspicious,
    }


def convert_file(src: Path, outdir: Path, formats: list[str]) -> dict:
    """转换单个文件。

    返回 {"ok": bool, "reason": str, "files": list[Path]}。
    被质量闸门拒绝时 ok=False 且 reason 说明原因；
    部分格式被跳过（例如无表格转 Excel）时 ok 仍为 True，原因放在 reason。
    """
    src = Path(src)
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    return convert_to_paths(src, {fmt: outdir / f"{src.stem}.{fmt}" for fmt in formats})


def convert_many(srcs, outdir, formats, on_progress=None) -> list[dict]:
    """逐份转换一个清单，一份失败不影响其他。

    on_progress(序号, 总数, 源文件, 该份结果) 在每份转完后调用一次，
    界面靠它逐行刷新，而不是等整批跑完才动。
    """
    srcs = [Path(s) for s in srcs]
    Path(outdir).mkdir(parents=True, exist_ok=True)
    plan = plan_outputs(srcs, outdir, formats)

    results: list[dict] = []
    total = len(srcs)
    for index, (src, targets) in enumerate(plan, start=1):
        try:
            outcome = convert_to_paths(src, targets)
        except Exception as exc:  # noqa: BLE001 - 单个文件失败不该中断整批
            outcome = {"ok": False, "reason": f"处理失败：{exc}", "files": []}
        outcome["src"] = src
        results.append(outcome)
        if on_progress is not None:
            on_progress(index, total, src, outcome)
    return results


