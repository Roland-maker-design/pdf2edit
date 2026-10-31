"""pdf2edit —— 电子版 PDF 转可编辑格式。"""

from .ir import Block, Document
from .quality import QualityReport, assess
from .structure import build_document

__all__ = ["Block", "Document", "QualityReport", "assess", "build_document"]
__version__ = "0.1.0"
