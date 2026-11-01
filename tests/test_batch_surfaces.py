"""批量功能在三个入口上的行为：桌面窗口、命令行。"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

CLEAN = ROOT / "fixtures" / "clean_basic.pdf"

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def sample_pdf() -> Path:
    if not CLEAN.exists():
        subprocess.run(
            [sys.executable, str(ROOT / "fixtures" / "generate_clean.py")], check=True
        )
    return CLEAN


@pytest.fixture(scope="module")
def qt_app():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_window_accepts_a_dropped_folder(qt_app, sample_pdf: Path, tmp_path: Path) -> None:
    from pdf2edit.desktop import MainWindow

    folder = tmp_path / "收件箱"
    folder.mkdir()
    shutil.copy(sample_pdf, folder / "one.pdf")
    shutil.copy(sample_pdf, folder / "two.pdf")
    (folder / "note.txt").write_text("x", encoding="utf-8")

    win = MainWindow()
    try:
        win.add_files([str(folder)])
        assert [p.name for p in win._files] == ["one.pdf", "two.pdf"]
    finally:
        win.close()


def test_worker_reports_progress_per_file(
    qt_app, sample_pdf: Path, tmp_path: Path
) -> None:
    from pdf2edit.desktop import ConvertWorker

    seen: list[tuple[int, int, str]] = []
    worker = ConvertWorker([sample_pdf, sample_pdf], ["md"], tmp_path / "out")
    worker.progress.connect(lambda i, total, name: seen.append((i, total, name)))
    worker.run()

    assert seen == [(1, 2, CLEAN.name), (2, 2, CLEAN.name)]


def test_cli_converts_every_given_file(sample_pdf: Path, tmp_path: Path) -> None:
    shutil.copy(sample_pdf, tmp_path / "one.pdf")
    shutil.copy(sample_pdf, tmp_path / "two.pdf")
    outdir = tmp_path / "out"

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pdf2edit",
            str(tmp_path / "one.pdf"),
            str(tmp_path / "two.pdf"),
            "--to",
            "md",
            "-o",
            str(outdir),
        ],
        cwd=str(ROOT),
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert proc.returncode == 0, proc.stderr
    assert (outdir / "one.md").exists()
    assert (outdir / "two.md").exists()


def test_web_ui_keeps_both_when_uploads_share_a_name(
    sample_pdf: Path, tmp_path: Path
) -> None:
    from pdf2edit.ui.app import create_app

    pdf_bytes = sample_pdf.read_bytes()
    client = create_app(tmp_path).test_client()

    resp = client.post(
        "/convert",
        data={
            "formats": ["md"],
            "files": [
                (io.BytesIO(pdf_bytes), "report.pdf"),
                (io.BytesIO(pdf_bytes), "report.pdf"),
            ],
        },
        content_type="multipart/form-data",
    )

    assert resp.status_code == 200
    assert len(list(tmp_path.rglob("*.md"))) == 2


def test_cli_survives_console_that_cannot_print_chinese(
    sample_pdf: Path, tmp_path: Path
) -> None:
    """英文系统的控制台用 cp1252，打印中文不能把整个命令搞崩。

    CI 上的 Windows runner 就是这种情况：本地中文系统用 cp936，一直没暴露。
    """
    shutil.copy(sample_pdf, tmp_path / "one.pdf")
    shutil.copy(sample_pdf, tmp_path / "two.pdf")
    outdir = tmp_path / "out"

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pdf2edit",
            str(tmp_path / "one.pdf"),
            str(tmp_path / "two.pdf"),
            "--to",
            "md",
            "-o",
            str(outdir),
        ],
        cwd=str(ROOT),
        env={
            **os.environ,
            "PYTHONPATH": str(ROOT / "src"),
            "PYTHONIOENCODING": "cp1252",
        },
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert proc.returncode == 0, proc.stderr
    assert (outdir / "one.md").exists()
    assert (outdir / "two.md").exists()
