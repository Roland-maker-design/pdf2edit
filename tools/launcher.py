"""PyInstaller 入口：默认启动桌面窗口。

支持 --selftest，用于验证打包后的 exe 里依赖是否齐全：
    pdf2edit.exe --selftest <输入.pdf> <输出目录>
结果写到同目录下的 selftest.log（windowed 模式没有控制台）。
"""

from __future__ import annotations

import sys
from pathlib import Path


def _selftest(pdf: str, outdir: str) -> int:
    log = Path(outdir) / "selftest.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    try:
        from pdf2edit.convert import convert_file

        result = convert_file(Path(pdf), Path(outdir), ["md", "docx", "html", "pptx"])
        lines = [f"ok={result['ok']}", f"reason={result['reason']}"]
        lines += [f"file={p.name} bytes={p.stat().st_size}" for p in result["files"]]
        log.write_text("\n".join(lines), encoding="utf-8")
        return 0 if result["ok"] else 1
    except Exception as exc:  # noqa: BLE001
        log.write_text(f"ERROR {type(exc).__name__}: {exc}", encoding="utf-8")
        return 2


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        idx = sys.argv.index("--selftest")
        raise SystemExit(_selftest(sys.argv[idx + 1], sys.argv[idx + 2]))
    from pdf2edit.desktop import run

    run()
