# 用真的 Word 生成一份 PDF，模拟"正常来源"的典型形态。
# 目的：验证结构重建在真实导出件上的表现，而不是在合成件上自嗨。

$ErrorActionPreference = 'Stop'
$outDir = 'E:\YourHome\pdf2edit\fixtures'
$docx = Join-Path $outDir 'word_export.docx'
$pdf = Join-Path $outDir 'word_export.pdf'

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0

# 内置样式常量，与界面语言无关
$S_NORMAL = -1
$S_H1 = -2
$S_H2 = -3
$S_BULLET = -48

try {
    $doc = $word.Documents.Add()

    $p = $doc.Paragraphs.Add()
    $p.Range.Text = '第一章 绪论'
    $p.Range.Style = $S_H1

    $p = $doc.Paragraphs.Add()
    $p.Range.Text = '本节介绍研究背景与意义，用于验证标题层级识别是否可靠。'
    $p.Range.Style = $S_NORMAL

    $p = $doc.Paragraphs.Add()
    $p.Range.Text = '对于中文正文，Word 往往把一个自然段写成一行，也可能因为排版被折成多行。'
    $p.Range.Style = $S_NORMAL

    $p = $doc.Paragraphs.Add()
    $p.Range.Text = '1.1 研究背景'
    $p.Range.Style = $S_H2

    $p = $doc.Paragraphs.Add()
    $p.Range.Text = '国内外学者对该问题已有大量研究，主要集中在三个方面。'
    $p.Range.Style = $S_NORMAL

    foreach ($item in @('第一，理论基础尚不完善。', '第二，实证数据相对匮乏。', '第三，方法体系有待统一。')) {
        $p = $doc.Paragraphs.Add()
        $p.Range.Text = $item
        $p.Range.Style = $S_BULLET
    }

    $p = $doc.Paragraphs.Add()
    $p.Range.Text = '1.2 主要表格'
    $p.Range.Style = $S_H2

    $tbl = $doc.Tables.Add($doc.Paragraphs.Add().Range, 3, 3)
    $tbl.Borders.Enable = $true
    $data = @(
        @('指标', '2024', '2025'),
        @('样本量', '1200', '1580'),
        @('准确率', '91.2%', '93.7%')
    )
    for ($r = 1; $r -le 3; $r++) {
        for ($c = 1; $c -le 3; $c++) {
            $tbl.Cell($r, $c).Range.Text = $data[$r - 1][$c - 1]
        }
    }

    $doc.SaveAs2($docx, 16)
    $doc.ExportAsFixedFormat($pdf, 17)
    $doc.Close(0)
    "OK: $pdf"
} finally {
    $word.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
}
