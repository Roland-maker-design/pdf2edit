"""按真实桌面平台截一张窗口图（offscreen 平台缺字体，会截成方块）。"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtWidgets import QApplication  # noqa: E402

from pdf2edit.desktop import MainWindow  # noqa: E402


def main() -> None:
    app = QApplication(sys.argv)
    win = MainWindow()
    win.add_files(
        [
            str(ROOT / "fixtures" / "clean_basic.pdf"),
            str(ROOT / "fixtures" / "print_export.pdf"),
            str(ROOT / "fixtures" / "word_export.pdf"),
        ]
    )
    win.show()
    app.processEvents()
    app.processEvents()
    target = ROOT / "docs" / "images" / "ui-window.png"
    win.grab().save(str(target))
    win.close()
    print(f"saved {target}")


if __name__ == "__main__":
    main()
