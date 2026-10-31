"""输出层：每个 writer 只消费 IR，互不依赖。"""

from . import docx_writer, html_writer, markdown, pptx_writer, xlsx_writer

__all__ = ["docx_writer", "html_writer", "markdown", "pptx_writer", "xlsx_writer"]
