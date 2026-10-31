"""Markdown 输出。"""

from __future__ import annotations

from ..ir import Block, Document


def _render_table(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    norm = [r + [""] * (width - len(r)) for r in rows]
    header = norm[0]
    body = norm[1:]
    lines = ["| " + " | ".join(header) + " |",
             "| " + " | ".join("---" for _ in header) + " |"]
    for r in body:
        lines.append("| " + " | ".join(r) + " |")
    return "\n".join(lines)


def _render_block(block: Block) -> str:
    if block.kind == "heading":
        level = max(1, min(6, block.level or 1))
        return "#" * level + " " + block.text
    if block.kind == "list_item":
        return "- " + block.text.lstrip("•·●○▪◦‣–—* ").strip()
    if block.kind == "code":
        return f"```\n{block.text}\n```"
    if block.kind == "warning":
        return f"> ⚠️ {block.text}"
    if block.kind == "table":
        return _render_table(block.rows or [])
    return block.text


def render(doc: Document) -> str:
    chunks: list[str] = []
    prev_kind: str | None = None
    for block in doc.blocks:
        body = _render_block(block)
        if not body:
            continue
        if chunks:
            chunks.append("\n" if (block.kind == "list_item" and prev_kind == "list_item") else "\n\n")
        chunks.append(body)
        prev_kind = block.kind
    return "".join(chunks).strip() + "\n"
