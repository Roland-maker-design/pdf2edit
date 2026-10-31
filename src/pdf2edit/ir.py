"""中间表示（IR）：解析层与输出层之间的唯一契约。

语义是主体，几何是可选附件：
- md / html / docx 只消费语义，完全不看坐标
- pptx 这类"原生就是绝对定位"的格式才需要 bbox
所以几何字段一律可选，缺失时 writer 必须能退化处理。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

Kind = Literal["heading", "paragraph", "list_item", "table", "code", "warning"]

BBox = tuple[float, float, float, float]


@dataclass
class Block:
    """一个语义块。"""

    kind: Kind
    text: str = ""
    level: int = 0                        # 仅 heading 使用，1 起
    rows: list[list[str]] | None = None    # 仅 table 使用
    page: int = 0                          # 1 起的页码

    # --- 以下为可选几何信息，仅供需要绝对定位的 writer 使用 ---
    bbox: BBox | None = None
    page_size: tuple[float, float] | None = None   # (宽, 高)，单位 pt
    size: float = 0.0                              # 字号，单位 pt


@dataclass
class Document:
    blocks: list[Block] = field(default_factory=list)
    source: Path | None = None

    def add(self, block: Block) -> None:
        self.blocks.append(block)

    def text(self) -> str:
        return "\n".join(b.text for b in self.blocks)
