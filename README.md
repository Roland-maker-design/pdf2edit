# pdf2edit

把来源正规的电子版 PDF，转成**可编辑的活内容**。本地、离线、开源。

不做扫描件，不做"看起来一样"，只做"**真的能改**"。

## 支持

| 输出 | 状态 | 说明 |
|---|---|---|
| Markdown | 开发中 | 结构优先，适合喂给 AI |
| Word (docx) | 计划 | 流式，真段落真样式 |
| HTML | 计划 | 语义标签 + 干净 CSS |
| PowerPoint (pptx) | 计划 | 文本框化，可编辑 |
| Excel (xlsx) | 计划 | 先做表格识别 |

## 不支持

- 扫描件、照片拍的 PDF
- 伪电子版（扫描图 + 坏 OCR 文本层）
- 图片输出（截图就能做）
- 保版式（绝对定位文本框，等于把截图装进 Word）

## 目录

```
docs/specs/     设计文档
src/            源码
tests/          测试
fixtures/       测试样本
tools/          辅助脚本
```

## 开发

```bash
python -m pip install pymupdf fonttools
python tools/probe_pdf.py <某个.pdf>    # 先体检，看这份能不能转
```

## 许可证

AGPL-3.0 —— 因为依赖 PyMuPDF（AGPL）与 pandoc（GPL）。
