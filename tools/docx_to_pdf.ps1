param(
    [Parameter(Mandatory = $true)][string]$Docx,
    [Parameter(Mandatory = $true)][string]$Pdf
)
# 只做一件事：打开 docx，导出 PDF，关闭。不建文档、不建表格，避免 COM 卡死。
$ErrorActionPreference = 'Stop'
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    $doc = $word.Documents.Open($Docx, $false, $true)   # ConfirmConversions=false, ReadOnly=true
    $doc.ExportAsFixedFormat($Pdf, 17)                  # 17 = wdExportFormatPDF
    $doc.Close(0)
    "exported: $Pdf"
}
finally {
    $word.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
}
