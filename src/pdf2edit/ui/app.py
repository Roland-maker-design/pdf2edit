"""本地网页 UI。

原则：
- 只监听 127.0.0.1，文件不出本机
- 转换走和命令行完全相同的那条流水线（不复制逻辑）
- 被质量闸门拒绝的文件要原样把理由显示出来，不假装成功
"""

from __future__ import annotations

import shutil
import tempfile
import uuid
from pathlib import Path

from flask import Flask, render_template, request, send_from_directory, url_for

from ..quality import assess
from ..structure import build_document
from ..writers import docx_writer, html_writer, markdown, pptx_writer, xlsx_writer

from ..convert import FORMAT_LABELS, convert_file, unique_name

FORMATS = FORMAT_LABELS


def _convert_one(src: Path, formats: list[str], jobdir: Path) -> dict:
    """把共享流水线的结果转成模板需要的形状。"""
    outcome = convert_file(src, jobdir, formats)
    return {
        "ok": outcome["ok"],
        "reason": outcome["reason"],
        "files": [{"fmt": p.suffix.lstrip("."), "name": p.name} for p in outcome["files"]],
    }


def create_app(workdir: Path | None = None) -> Flask:
    base = Path(workdir or tempfile.mkdtemp(prefix="pdf2edit-ui-"))
    base.mkdir(parents=True, exist_ok=True)

    app = Flask(
        __name__,
        template_folder=str(Path(__file__).parent / "templates"),
    )
    app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024

    @app.get("/")
    def index():
        return render_template("index.html", formats=FORMATS, results=None)

    @app.post("/convert")
    def convert():
        uploads = [f for f in request.files.getlist("files") if f and f.filename]
        formats = request.form.getlist("formats") or ["md"]

        if not uploads:
            return render_template("index.html", formats=FORMATS, results=[], error="没有选择文件")

        job = uuid.uuid4().hex[:10]
        jobdir = base / job
        jobdir.mkdir(parents=True, exist_ok=True)

        results = []
        saved: set[str] = set()
        for upload in uploads:
            # 两个文件同名时不能覆盖：report.pdf → report (2).pdf
            safe_name = unique_name(Path(upload.filename).name, saved)
            src = jobdir / safe_name
            upload.save(src)
            try:
                outcome = _convert_one(src, formats, jobdir)
            except Exception as exc:  # noqa: BLE001 - 单个文件失败不该拖垮整批
                outcome = {"ok": False, "reason": f"处理失败：{exc}", "files": []}
            outcome["name"] = safe_name
            outcome["job"] = job
            results.append(outcome)

        return render_template("index.html", formats=FORMATS, results=results, error=None)

    @app.get("/download/<job>/<path:name>")
    def download(job: str, name: str):
        return send_from_directory(base / job, name, as_attachment=True)

    return app


def run(host: str = "127.0.0.1", port: int = 8765) -> None:
    app = create_app()
    print(f"打开浏览器访问 http://{host}:{port}")
    print("所有转换都在本机完成，文件不会上传到任何服务器。")
    app.run(host=host, port=port, debug=False)
