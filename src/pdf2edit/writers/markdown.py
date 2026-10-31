"""Markdown 输出。"""

from __future__ import annotations

from ..ir import Block, Document


def _render_block(block: Block) -> str:
    if block.kind == "heading":
        level = max(1, min(6, block.level or 1))
        return "#" * level + " " + block.text
    if block.kind == "list_item":
        return "- " + block.text.lstrip("•·●○▪◦‣–—* ").strip()
    if block.kind == "table":
        return "<!-- 表格输出将在 P1 实现 -->\n" + block.text
    return block.text


def render(doc: Document) -> str:
    chunks: list[str] = []
    prev_kind: str | None = None
    for block in doc.blocks:
        body = _render_block(block)
        if not body:
            continue
        if chunks:
            # 连续列表项之间用单换行，块之间空一行
            chunks.append("\n" if (block.kind == "list_item" and prev_kind == "list_item") else "\n\n")
        chunks.append(body)
        prev_kind = block.kind
    return "".join(chunks).strip() + "\n"
