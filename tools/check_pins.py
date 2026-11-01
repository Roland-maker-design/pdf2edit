"""核对 requirements*.txt 里锁的版本和本机实际装的版本是否一致。"""

import importlib.metadata as md
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

bad = []
for req in ("requirements.txt", "requirements-dev.txt"):
    print(f"== {req} ==")
    for line in (ROOT / req).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-r"):
            continue
        name, _, version = line.partition("==")
        try:
            have = md.version(name)
        except md.PackageNotFoundError:
            print(f"  {name:14} 未安装")
            bad.append(f"{name} 未安装")
            continue
        mark = "ok" if have == version else "不一致"
        print(f"  {name:14} 锁 {version:10} 本机 {have:10} {mark}")
        if have != version:
            bad.append(f"{name}: 本机 {have} != 锁定 {version}")

print("结论：", "全部对得上" if not bad else "有问题 -> " + "; ".join(bad))
sys.exit(1 if bad else 0)
