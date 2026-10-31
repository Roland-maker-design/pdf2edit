"""压测矩阵：把所有样本跑过所有输出格式，输出一张状态表。

    python tools/stress_matrix.py [--dir fixtures] [--json out/matrix.json]

状态含义：
  ok      正常产出
  skip    该格式不适用（例如无表格转 Excel），已说明原因
  reject  被质量闸门拒绝（预期行为，不是失败）
  ERR     抛出异常——这是真正需要修的问题
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pdf2edit.convert import SUPPORTED_FORMATS, convert_file  # noqa: E402

SYMBOL = {"ok": "ok", "skip": "skip", "reject": "rej", "ERR": "ERR"}


def run_one(pdf: Path, fmt: str, outdir: Path) -> dict:
    started = time.perf_counter()
    try:
        result = convert_file(pdf, outdir, [fmt])
        elapsed = time.perf_counter() - started
        if result["ok"]:
            size = sum(p.stat().st_size for p in result["files"])
            return {"status": "ok", "secs": elapsed, "bytes": size, "reason": result["reason"]}
        reason = result["reason"]
        if "跳过" in reason or "没有检测到表格" in reason:
            return {"status": "skip", "secs": elapsed, "bytes": 0, "reason": reason}
        return {"status": "reject", "secs": elapsed, "bytes": 0, "reason": reason}
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "ERR",
            "secs": time.perf_counter() - started,
            "bytes": 0,
            "reason": f"{type(exc).__name__}: {exc}",
            "trace": traceback.format_exc(limit=3),
        }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="fixtures")
    ap.add_argument("--json", default="out/stress_matrix.json")
    ap.add_argument("--formats", nargs="*", default=SUPPORTED_FORMATS)
    args = ap.parse_args(argv)

    base = ROOT / args.dir
    pdfs = sorted(base.glob("*.pdf")) + sorted((base / "edge").glob("*.pdf"))
    if not pdfs:
        print("没有找到样本")
        return 2

    outdir = ROOT / "out" / "stress"
    report: dict[str, dict] = {}
    errors = 0

    header = f"{'样本':<28}" + "".join(f"{f:>7}" for f in args.formats)
    print(header)
    print("-" * len(header))

    for pdf in pdfs:
        name = pdf.stem
        row = {}
        cells = []
        for fmt in args.formats:
            outcome = run_one(pdf, fmt, outdir / name / fmt)
            row[fmt] = outcome
            if outcome["status"] == "ERR":
                errors += 1
            cells.append(f"{SYMBOL[outcome['status']]:>7}")
        report[str(pdf.relative_to(ROOT))] = row
        print(f"{name:<28}" + "".join(cells))

    out_json = ROOT / args.json
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print()
    print(f"样本 {len(pdfs)} 个 × 格式 {len(args.formats)} 种 = {len(pdfs) * len(args.formats)} 组")
    print(f"异常(ERR) {errors} 组；明细已写入 {out_json.relative_to(ROOT)}")

    if errors:
        print("\n需要修的问题：")
        for path, row in report.items():
            for fmt, outcome in row.items():
                if outcome["status"] == "ERR":
                    print(f"  - {Path(path).stem} [{fmt}] {outcome['reason']}")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
