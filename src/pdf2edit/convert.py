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


def convert_file(src: Path, outdir: Path, formats: list[str]) -> dict:
    """转换单个文件。

    返回 {"ok": bool, "reason": str, "files": list[Path]}。
    被质量闸门拒绝时 ok=False 且 reason 说明原因；
    部分格式被跳过（例如无表格转 Excel）时 ok 仍为 True，原因放在 reason。
    """
    src = Path(src)
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

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
    for fmt in formats:
        out = outdir / f"{src.stem}.{fmt}"
        try:
            _write(fmt, ir, out)
            produced.append(out)
        except ValueError as exc:
            skipped.append(f"{FORMAT_LABELS.get(fmt, fmt)} 已跳过：{exc}")

    return {
        "ok": bool(produced),
        "reason": "；".join(skipped),
        "files": produced,
    }
