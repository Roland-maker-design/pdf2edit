# pdf2edit

把来源正规的电子版 PDF，转成**可编辑的活内容**。本地、离线、开源。

不做扫描件，不做"看起来一样"，只做"**真的能改**"。

## 支持

| 输出 | 状态 | 说明 |
|---|---|---|
| Markdown | ✅ 可用 | 结构优先，适合喂给 AI |
| Word (docx) | ✅ 可用 | 流式，全部用 Word 内置样式（改一次样式全篇生效） |
| HTML | ✅ 可用 | 语义标签 + 干净 CSS，自带深色模式 |
| PowerPoint (pptx) | ✅ 可用 | 按原版面摆文本框，原生可编辑 |
| Excel (xlsx) | 计划 | 先做表格识别 |

## 不支持

- 扫描件、照片拍的 PDF
- 伪电子版（扫描图 + 坏 OCR 文本层）
- 图片输出（截图就能做）
- 保版式（绝对定位文本框，等于把截图装进 Word）

## 用法

```bash
python -m pdf2edit 输入.pdf                 # 默认输出 Markdown
python -m pdf2edit 输入.pdf --to docx -o 输出.docx
python tools/probe_pdf.py 输入.pdf          # 先体检，看这份能不能转
```

文字层不可信的文件会被明确拒绝并说明原因，不会硬转出乱码。

## 目录

```
docs/specs/     设计文档
src/            源码
tests/          测试
fixtures/       测试样本（含真实来源：Word 导出、浏览器打印）
tools/          辅助脚本
```

## 开发

```bash
python -m pip install pymupdf fonttools python-docx pytest
python -m pytest tests -q
```

## 验证过什么

- 合成样本：标题 / 段落 / 列表 / 页码
- 浏览器打印（Edge headless）：无符号列表、表格
- Word 导出：H1/H2 只差 1pt、项目符号独立成段、表格基线差 2.5pt
- 往返闭环：PDF → docx → Word 导回 PDF → 再转 Markdown，结构一致

## 许可证

AGPL-3.0 —— 因为依赖 PyMuPDF（AGPL）。
