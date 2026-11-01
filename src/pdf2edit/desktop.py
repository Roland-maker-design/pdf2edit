"""Windows 桌面窗口（PySide6）。

- 拖入 PDF，选格式，点按钮，结果直接出现在输出目录
- 转换在后台线程跑，界面不会卡死
- 全部本地处理，不联网
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .convert import FORMAT_LABELS, SUPPORTED_FORMATS, collect_pdfs, convert_many


class DropArea(QFrame):
    """接收拖拽的区域：PDF 和文件夹都收。"""

    filesDropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setObjectName("dropArea")
        self.setMinimumHeight(120)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        self.title = QLabel("把 PDF 或整个文件夹拖到这里")
        self.title.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setPointSize(13)
        font.setBold(True)
        self.title.setFont(font)

        self.hint = QLabel("或者点击下方「选择文件」；支持一次选多个")
        self.hint.setAlignment(Qt.AlignCenter)
        self.hint.setObjectName("hint")

        layout.addWidget(self.title)
        layout.addWidget(self.hint)

    def dragEnterEvent(self, event):  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setProperty("hover", True)
            self.style().unpolish(self)
            self.style().polish(self)

    def dragLeaveEvent(self, event):  # noqa: N802
        self.setProperty("hover", False)
        self.style().unpolish(self)
        self.style().polish(self)

    def dropEvent(self, event):  # noqa: N802
        self.setProperty("hover", False)
        self.style().unpolish(self)
        self.style().polish(self)
        # 文件夹也放行，筛 PDF 的事交给 collect_pdfs，一处判断
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if paths:
            self.filesDropped.emit(paths)
            event.acceptProposedAction()


class ConvertWorker(QThread):
    finished_with_results = Signal(list)
    progress = Signal(int, int, str)

    def __init__(self, files: list[Path], formats: list[str], outdir: Path):
        super().__init__()
        self._files = files
        self._formats = formats
        self._outdir = outdir

    def run(self) -> None:
        def report(index: int, total: int, src: Path, _outcome: dict) -> None:
            self.progress.emit(index, total, Path(src).name)

        results = convert_many(self._files, self._outdir, self._formats, on_progress=report)
        self.finished_with_results.emit(results)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("pdf2edit — 本地 PDF 转换")
        self.resize(780, 760)

        self._files: list[Path] = []
        self._worker: ConvertWorker | None = None

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = QLabel("pdf2edit")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)

        subtitle = QLabel("把 PDF 变成能改的东西 · 全部在本机完成，文件不出这台机器")
        subtitle.setObjectName("hint")

        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.drop = DropArea()
        self.drop.filesDropped.connect(self.add_files)
        layout.addWidget(self.drop)

        pick = QPushButton("选择文件…")
        pick.clicked.connect(self.pick_files)
        clear = QPushButton("清空")
        clear.clicked.connect(self.clear_files)
        row = QHBoxLayout()
        row.addWidget(pick)
        row.addWidget(clear)
        row.addStretch(1)
        layout.addLayout(row)

        self.file_list = QListWidget()
        self.file_list.setMaximumHeight(110)
        layout.addWidget(self.file_list)

        formats_row = QHBoxLayout()
        formats_label = QLabel("输出格式：")
        formats_row.addWidget(formats_label)
        self.format_boxes: dict[str, QCheckBox] = {}
        for fmt in SUPPORTED_FORMATS:
            box = QCheckBox(FORMAT_LABELS[fmt])
            box.setChecked(fmt in ("md", "docx"))
            self.format_boxes[fmt] = box
            formats_row.addWidget(box)
        formats_row.addStretch(1)
        layout.addLayout(formats_row)

        out_row = QHBoxLayout()
        self.out_edit = QLineEdit(str(Path.home() / "Documents" / "pdf2edit"))
        browse = QPushButton("更改输出目录…")
        browse.clicked.connect(self.pick_outdir)
        out_row.addWidget(QLabel("输出到："))
        out_row.addWidget(self.out_edit, 1)
        out_row.addWidget(browse)
        layout.addLayout(out_row)

        self.convert_btn = QPushButton("开始转换")
        self.convert_btn.setObjectName("primaryBtn")
        self.convert_btn.setMinimumHeight(42)
        self.convert_btn.clicked.connect(self.start_convert)
        layout.addWidget(self.convert_btn)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setTextVisible(True)
        layout.addWidget(self.progress)

        self.results = QListWidget()
        self.results.setMinimumHeight(150)
        layout.addWidget(self.results, 1)

        bottom = QHBoxLayout()
        self.status = QLabel("就绪")
        self.status.setObjectName("hint")
        open_dir = QPushButton("打开输出文件夹")
        open_dir.clicked.connect(self.open_outdir)
        bottom.addWidget(self.status, 1)
        bottom.addWidget(open_dir)
        layout.addLayout(bottom)

        self.setStyleSheet(_STYLE)

    # ---------- 文件 ----------

    def add_files(self, paths: list[str]) -> None:
        before = len(self._files)
        self._files = collect_pdfs([*self._files, *(Path(p) for p in paths)])
        added = len(self._files) - before
        if not self._files:
            self.status.setText("这里没有 PDF 文件")
            return
        self.file_list.clear()
        for path in self._files:
            self.file_list.addItem(path.name)
        text = f"已选择 {len(self._files)} 个文件"
        if added and before:
            text += f"（新增 {added}）"
        self.status.setText(text)

    def pick_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "选择 PDF", "", "PDF 文件 (*.pdf)")
        if paths:
            self.add_files(paths)

    def clear_files(self) -> None:
        self._files.clear()
        self.file_list.clear()
        self.results.clear()
        self.status.setText("就绪")

    def pick_outdir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择输出目录", self.out_edit.text())
        if path:
            self.out_edit.setText(path)

    def open_outdir(self) -> None:
        outdir = Path(self.out_edit.text())
        outdir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(outdir)))

    # ---------- 转换 ----------

    def start_convert(self) -> None:
        if not self._files:
            self.status.setText("还没有选择文件")
            return
        formats = [f for f, box in self.format_boxes.items() if box.isChecked()]
        if not formats:
            self.status.setText("至少选一种输出格式")
            return

        self.convert_btn.setEnabled(False)
        self.convert_btn.setText("转换中…")
        self.results.clear()
        self.status.setText("正在转换")
        self.progress.setRange(0, len(self._files))
        self.progress.setValue(0)
        self.progress.setFormat("%v / %m")
        self.progress.setVisible(True)

        self._worker = ConvertWorker(list(self._files), formats, Path(self.out_edit.text()))
        self._worker.progress.connect(self.on_progress)
        self._worker.finished_with_results.connect(self.show_results)
        self._worker.start()

    def on_progress(self, index: int, total: int, name: str) -> None:
        self.progress.setValue(index)
        self.status.setText(f"正在转换 {index}/{total}：{name}")

    def show_results(self, results: list) -> None:
        self.convert_btn.setEnabled(True)
        self.convert_btn.setText("开始转换")
        self.progress.setVisible(False)

        ok_count = 0
        partial_count = 0
        fail_count = 0
        for r in results:
            name = r.get("src", Path("?")).name
            if r["ok"]:
                ok_count += 1
                names = "、".join(f.name for f in r["files"])
                text = f"✓ {name} → {names}"
                if r["reason"]:
                    partial_count += 1
                    text += f"（{r['reason']}）"
            else:
                fail_count += 1
                text = f"✗ {name} — {r['reason']}"
            self.results.addItem(text)

        parts = [f"成功 {ok_count}"]
        if partial_count:
            parts.append(f"部分跳过 {partial_count}")
        parts.append(f"失败 {fail_count}")
        self.status.setText("完成：" + " · ".join(parts))


_STYLE = """
#dropArea {
    border: 2px dashed #9aa0a6;
    border-radius: 10px;
    background: palette(base);
}
#dropArea[hover="true"] {
    border-color: #3b82f6;
    background: #3b82f61a;
}
#hint { color: #8a8f98; }
QListWidget { border: 1px solid #d0d3d8; border-radius: 8px; padding: 4px; }
QPushButton {
    padding: 7px 16px;
    border: 1px solid #c8ccd2;
    border-radius: 6px;
    background: palette(button);
    color: palette(button-text);
}
QPushButton:hover { background: palette(midlight); }
QPushButton:disabled { color: #9aa0a6; }
#primaryBtn {
    border: none;
    background: #3b82f6;
    color: #ffffff;
    font-weight: 600;
    font-size: 15px;
}
#primaryBtn:hover { background: #2f6fdd; }
#primaryBtn:disabled { background: #7fa8ef; }
QLineEdit { padding: 6px 9px; border: 1px solid #c8ccd2; border-radius: 6px; }
QCheckBox { spacing: 6px; }
"""


def render_shot(path: str) -> None:
    """离屏渲染一张界面截图，用于验证外观。"""
    app = QApplication.instance() or QApplication(sys.argv)
    win = MainWindow()
    win.show()
    app.processEvents()
    win.grab().save(path)
    win.close()


def run() -> None:
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

