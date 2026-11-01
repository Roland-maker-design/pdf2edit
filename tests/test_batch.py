"""批量转换的测试：收集文件、规划输出路径、逐份转换。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

CLEAN = ROOT / "fixtures" / "clean_basic.pdf"


@pytest.fixture(scope="session")
def clean_pdf() -> Path:
    if not CLEAN.exists():
        subprocess.run(
            [sys.executable, str(ROOT / "fixtures" / "generate_clean.py")], check=True
        )
    return CLEAN


def _touch(path: Path, data: bytes = b"x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


# ---------- 收集 ----------


def test_collect_pdfs_expands_folder(tmp_path: Path) -> None:
    from pdf2edit.convert import collect_pdfs

    _touch(tmp_path / "a.pdf")
    _touch(tmp_path / "b.pdf")
    _touch(tmp_path / "c.txt")

    got = collect_pdfs([tmp_path])

    assert [p.name for p in got] == ["a.pdf", "b.pdf"]


def test_collect_pdfs_does_not_recurse(tmp_path: Path) -> None:
    from pdf2edit.convert import collect_pdfs

    _touch(tmp_path / "top.pdf")
    _touch(tmp_path / "deeper" / "nested.pdf")

    got = collect_pdfs([tmp_path])

    assert [p.name for p in got] == ["top.pdf"]


def test_collect_pdfs_accepts_uppercase_suffix(tmp_path: Path) -> None:
    from pdf2edit.convert import collect_pdfs

    _touch(tmp_path / "SHOUT.PDF")

    assert [p.name for p in collect_pdfs([tmp_path])] == ["SHOUT.PDF"]


def test_collect_pdfs_mixes_files_and_folders_without_duplicates(tmp_path: Path) -> None:
    from pdf2edit.convert import collect_pdfs

    a = _touch(tmp_path / "a.pdf")
    _touch(tmp_path / "b.pdf")

    got = collect_pdfs([a, tmp_path, a])

    assert [p.name for p in got] == ["a.pdf", "b.pdf"]


def test_collect_pdfs_ignores_missing_path(tmp_path: Path) -> None:
    from pdf2edit.convert import collect_pdfs

    _touch(tmp_path / "a.pdf")

    got = collect_pdfs([tmp_path / "nope.pdf", tmp_path])

    assert [p.name for p in got] == ["a.pdf"]


# ---------- 输出布局 ----------


def test_plan_outputs_keeps_flat_for_one_file(tmp_path: Path) -> None:
    from pdf2edit.convert import plan_outputs

    src = tmp_path / "a.pdf"
    outdir = tmp_path / "out"

    got = plan_outputs([src], outdir, ["md", "docx"])

    assert got == [(src, {"md": outdir / "a.md", "docx": outdir / "a.docx"})]


def test_plan_outputs_keeps_flat_for_many_files_one_format(tmp_path: Path) -> None:
    from pdf2edit.convert import plan_outputs

    a, b = tmp_path / "a.pdf", tmp_path / "b.pdf"
    outdir = tmp_path / "out"

    got = plan_outputs([a, b], outdir, ["md"])

    assert got == [(a, {"md": outdir / "a.md"}), (b, {"md": outdir / "b.md"})]


def test_plan_outputs_uses_subfolder_for_many_files_and_formats(tmp_path: Path) -> None:
    from pdf2edit.convert import plan_outputs

    a, b = tmp_path / "a.pdf", tmp_path / "b.pdf"
    outdir = tmp_path / "out"

    got = plan_outputs([a, b], outdir, ["md", "docx"])

    assert got == [
        (a, {"md": outdir / "a" / "a.md", "docx": outdir / "a" / "a.docx"}),
        (b, {"md": outdir / "b" / "b.md", "docx": outdir / "b" / "b.docx"}),
    ]


def test_plan_outputs_disambiguates_same_stem(tmp_path: Path) -> None:
    from pdf2edit.convert import plan_outputs

    one = tmp_path / "one" / "report.pdf"
    two = tmp_path / "two" / "report.pdf"
    outdir = tmp_path / "out"

    got = plan_outputs([one, two], outdir, ["md"])

    assert got == [
        (one, {"md": outdir / "report.md"}),
        (two, {"md": outdir / "report (2).md"}),
    ]


# ---------- 逐份转换 ----------


def test_convert_many_reports_each_file(clean_pdf: Path, tmp_path: Path) -> None:
    from pdf2edit.convert import convert_many

    srcs = [clean_pdf, clean_pdf]

    results = convert_many(srcs, tmp_path / "out", ["md"])

    assert len(results) == 2
    assert all(r["ok"] for r in results)
    assert results[0]["files"][0].exists()
    assert results[1]["files"][0].exists()
    assert results[0]["files"][0] != results[1]["files"][0]


def test_convert_many_keeps_going_after_bad_file(clean_pdf: Path, tmp_path: Path) -> None:
    from pdf2edit.convert import convert_many

    bogus = _touch(tmp_path / "broken.pdf", b"not a pdf at all")

    results = convert_many([bogus, clean_pdf], tmp_path / "out", ["md"])

    assert results[0]["ok"] is False
    assert results[0]["reason"] == "这不是一个有效的 PDF 文件"
    assert results[1]["ok"] is True


def test_convert_many_calls_progress_per_file(clean_pdf: Path, tmp_path: Path) -> None:
    from pdf2edit.convert import convert_many

    seen: list[tuple[int, int, str]] = []

    convert_many(
        [clean_pdf, clean_pdf],
        tmp_path / "out",
        ["md"],
        on_progress=lambda i, total, src, _result: seen.append((i, total, src.name)),
    )

    assert seen == [(1, 2, "clean_basic.pdf"), (2, 2, "clean_basic.pdf")]
