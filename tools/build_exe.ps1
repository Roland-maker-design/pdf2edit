# 构建单文件 exe（双击即可运行，不需要装 Python）
# 用法：pwsh -File tools/build_exe.ps1   或   powershell -File tools/build_exe.ps1

$ErrorActionPreference = 'Stop'
Push-Location (Join-Path $PSScriptRoot '..')

$root = (Get-Location).Path
$env:PYTHONPATH = Join-Path $root 'src'

python -m PyInstaller --noconfirm --clean --onefile --windowed `
    --name pdf2edit `
    --paths src `
    --collect-all pymupdf `
    --exclude-module PySide6.QtWebEngineCore `
    --exclude-module PySide6.QtWebEngineWidgets `
    --exclude-module PySide6.QtQuick `
    --exclude-module PySide6.QtMultimedia `
    --exclude-module PySide6.Qt3DCore `
    --exclude-module PySide6.QtCharts `
    --exclude-module PySide6.QtDataVisualization `
    --exclude-module PySide6.QtPdf `
    --exclude-module pytest `
    tools/launcher.py

$exe = Join-Path $root 'dist\pdf2edit.exe'
if (-not (Test-Path $exe)) { throw "构建失败：找不到 $exe" }

$mb = [math]::Round((Get-Item $exe).Length / 1MB, 1)
Write-Host "构建完成：$exe（$mb MB）"

# 自检：用真实样本跑一次，确认打包进去的依赖都可用
$out = Join-Path $root 'out\selftest'
Remove-Item $out -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $out | Out-Null
$proc = Start-Process -FilePath $exe -ArgumentList '--selftest', (Join-Path $root 'fixtures\word_export.pdf'), $out -PassThru -Wait
if ($proc.ExitCode -ne 0) { throw "自检失败（退出码 $($proc.ExitCode)）" }
Write-Host "自检通过："
Get-Content (Join-Path $out 'selftest.log') -Encoding UTF8 | Write-Host

Pop-Location
