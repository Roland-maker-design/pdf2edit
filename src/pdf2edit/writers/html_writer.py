"""HTML 输出：语义标签 + 干净 CSS。

不做"像素级还原"的绝对定位版——那是截图思维。
这里输出的每个标签都承载结构含义，贴进任何网站都该是干净的。
"""

from __future__ import annotations

from html import escape

from ..ir import Block, Document

_CSS = """\
:root { color-scheme: light dark; }
body {
  max-width: 46rem; margin: 2rem auto; padding: 0 1.2rem;
  font-family: "Microsoft YaHei", "PingFang SC", system-ui, sans-serif;
  line-height: 1.75; font-size: 16px;
}
h1, h2, h3, h4, h5, h6 { line-height: 1.3; margin: 1.6em 0 0.6em; }
h1 { font-size: 1.9em; border-bottom: 1px solid #8883; padding-bottom: 0.3em; }
h2 { font-size: 1.45em; }
p { margin: 0.9em 0; }
ul { margin: 0.8em 0; padding-left: 1.6em; }
li { margin: 0.25em 0; }
table { border-collapse: collapse; margin: 1.2em 0; width: 100%; }
th, td { border: 1px solid #8884; padding: 0.45em 0.7em; text-align: left; }
th { background: #8881; font-weight: 600; }
"""


def _table_html(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    norm = [r + [""] * (width - len(r)) for r in rows]
    head, body = norm[0], norm[1:]

    out = ["<table>", "<thead>", "<tr>" + "".join(f"<th>{escape(c)}</th>" for c in head) + "</tr>", "</thead>"]
    if body:
        out.append("<tbody>")
        for row in body:
            out.append("<tr>" + "".join(f"<td>{escape(c)}</td>" for c in row) + "</tr>")
        out.append("</tbody>")
    out.append("</table>")
    return "\n".join(out)


def _block_html(block: Block) -> str:
    if block.kind == "heading":
        level = max(1, min(6, block.level or 1))
        return f"<h{level}>{escape(block.text)}</h{level}>"
    if block.kind == "table":
        return _table_html(block.rows or [])
    if block.kind == "list_item":
        return escape(block.text.lstrip("•·●○▪◦‣–—* ").strip())
    return f"<p>{escape(block.text)}</p>"


def render(ir: Document, title: str | None = None) -> str:
    parts: list[str] = []
    list_buf: list[str] = []

    def flush_list() -> None:
        if not list_buf:
            return
        items = "\n".join(f"  <li>{t}</li>" for t in list_buf)
        parts.append(f"<ul>\n{items}\n</ul>")
        list_buf.clear()

    for block in ir.blocks:
        if block.kind == "list_item":
            list_buf.append(_block_html(block))
            continue
        flush_list()
        html = _block_html(block)
        if html:
            parts.append(html)
    flush_list()

    if title is None:
        first_heading = next((b.text for b in ir.blocks if b.kind == "heading"), None)
        title = first_heading or (ir.source.stem if ir.source else "document")

    body = "\n".join(parts)
    return (
        "<!DOCTYPE html>\n"
        '<html lang="zh-CN">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"  <title>{escape(title)}</title>\n"
        "  <style>\n"
        + "".join(f"    {line}\n" for line in _CSS.splitlines())
        + "  </style>\n"
        "</head>\n"
        "<body>\n"
        f"{body}\n"
        "</body>\n"
        "</html>\n"
    )
