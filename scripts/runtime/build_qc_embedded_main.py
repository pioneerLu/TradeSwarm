#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""从 qc_signals/signals.json 生成带 EMBEDDED_SIGNALS 的 main.py（Algorithm Lab 单文件回测）。

Docker 未启动或 lean cloud 受代理影响时：在本机运行本脚本后，将输出的 main.py
整段粘贴到 QuantConnect 网页编辑器即可回测（无需上传 signals.json）。

用法（仓库根目录）：
  conda run -n langchain python scripts/runtime/build_qc_embedded_main.py
  conda run -n langchain python scripts/runtime/build_qc_embedded_main.py --signals path/to/signals.json
"""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEFAULT_SIGNALS = REPO / "qc_signals" / "signals.json"
TEMPLATE = REPO / "quantconnect" / "main.py"
PLACEHOLDER = "EMBEDDED_SIGNALS = {}"


def main() -> None:
    p = argparse.ArgumentParser(description="生成含嵌入式信号的 QC main.py")
    p.add_argument("--signals", type=Path, default=DEFAULT_SIGNALS, help="signals.json 路径")
    p.add_argument(
        "--out",
        type=Path,
        default=REPO / "lean_workspace" / "TradeSwarm" / "main.py",
        help="输出 main.py（默认覆盖 lean_workspace/TradeSwarm/main.py）",
    )
    p.add_argument("--print-path-only", action="store_true", help="仅打印输出路径")
    args = p.parse_args()

    if not args.signals.exists():
        raise SystemExit(f"找不到信号文件: {args.signals}")
    text = TEMPLATE.read_text(encoding="utf-8")
    if PLACEHOLDER not in text:
        raise SystemExit(f"模板中缺少占位行: {PLACEHOLDER}")

    data = json.loads(args.signals.read_text(encoding="utf-8"))
    by_exec = data.get("by_execution_date") or {}
    if not by_exec:
        raise SystemExit("signals.json 中 by_execution_date 为空，无法嵌入")
    payload = json.dumps(by_exec, ensure_ascii=False).encode("utf-8")
    b64 = base64.b64encode(payload).decode("ascii")

    embedded_line = (
        'EMBEDDED_SIGNALS = __import__("json").loads('
        '__import__("base64").b64decode("'
        + b64
        + '").decode("utf-8"))'
    )
    out_text = text.replace(PLACEHOLDER, embedded_line, 1)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(out_text, encoding="utf-8")
    if args.print_path_only:
        print(args.out)
        return
    print(f"[OK] 已写入 {args.out}（嵌入 {len(by_exec)} 个 execution_date）")
    print("网页回测：打开 Algorithm Lab，用该文件内容替换算法后运行。")


if __name__ == "__main__":
    main()
