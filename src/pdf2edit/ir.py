"""中间表示（IR）：解析层与输出层之间的唯一契约。

设计原则：只承载语义，不承载坐标布局。坐标是结构重建的中间手段，
不进 IR（见设计文档「布局是手段，不是目的」）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

Kind = Literal["heading", "paragraph", "list_item", "table"]


@dataclass
class Block:
    """一个语义块。"""

    kind: Kind
    text: str = ""
    level: int = 0                      # 仅 heading 使用，1 起
    rows: list[list[str]] | None = None  # 仅 table 使用（P1）
    page: int = 0                       # 1 起的页码


@dataclass
class Document:
    blocks: list[Block] = field(default_factory=list)
    source: Path | None = None

    def add(self, block: Block) -> None:
        self.blocks.append(block)

    def text(self) -> str:
        return "\n".join(b.text for b in self.blocks)
