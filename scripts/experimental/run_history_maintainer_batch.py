#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
离线批量构建 History Maintainer summaries 脚本。

分类：数据构建（见 README 三）
- 针对已有 analyst_reports 的 memory.db，为指定 symbol/日期区间批量生成 7 日窗口 summary，写入 analyst_summaries 表。
- 不跑交易图；回测前预先跑本脚本可加速「离线测试」且已有 summary 会跳过、不重复调 LLM。
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from tradingagents.graph.utils import load_llm_from_config
from tradingagents.agents.utils.memory_db_helper import MemoryDBHelper
from tradingagents.agents.post_close.history_maintainer import (
    create_history_maintainer_node,
)


def get_symbols_and_dates(db: MemoryDBHelper) -> List[Tuple[str, str]]:
    """
    从 analyst_reports 表中获取 (symbol, trade_date) 去重列表，按日期排序。
    """
    conn = db._get_connection()  # 复用内部连接
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT DISTINCT symbol, trade_date
        FROM analyst_reports
        WHERE report_content IS NOT NULL AND report_content != ''
        ORDER BY trade_date ASC, symbol ASC
        """
    )
    rows = cursor.fetchall()
    cursor.close()
    return [(r[0], r[1]) for r in rows]


def filter_by_range(
    items: List[Tuple[str, str]], start: str | None, end: str | None
) -> List[Tuple[str, str]]:
    """
    按日期区间过滤 (symbol, trade_date) 列表。
    """
    result: List[Tuple[str, str]] = []
    for symbol, trade_date in items:
        if start and trade_date < start:
            continue
        if end and trade_date > end:
            continue
        result.append((symbol, trade_date))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="离线批量构建 History Maintainer summaries"
    )
    parser.add_argument(
        "--db",
        type=str,
        default="memory.db",
        help="memory.db 路径（默认当前目录下 memory.db）",
    )
    parser.add_argument(
        "--start",
        type=str,
        default=None,
        help="开始日期 (YYYY-MM-DD)，留空则从最早有报告的日期开始",
    )
    parser.add_argument(
        "--end",
        type=str,
        default=None,
        help="结束日期 (YYYY-MM-DD)，留空则到最晚有报告的日期",
    )
    parser.add_argument(
        "--symbol",
        type=str,
        default=None,
        help="仅为指定 symbol 构建（留空则对所有 symbol 构建）",
    )
    parser.add_argument(
        "--sleep-ms",
        type=int,
        default=500,
        help="每个交易日处理完成后额外等待的毫秒数，用于避免 LLM API 限速（默认 500ms）",
    )

    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        raise FileNotFoundError(f"数据库不存在: {db_path}")

    print("=" * 80)
    print("离线 History Maintainer 批量构建")
    print("=" * 80)
    print(f"数据库: {db_path}")
    print(f"日期范围: {args.start or '最早'} ~ {args.end or '最晚'}")
    print(f"标的: {args.symbol or '全部'}")

    # 1. 初始化 DB 和 LLM
    with MemoryDBHelper(str(db_path)) as db:
        llm = load_llm_from_config()
        node = create_history_maintainer_node(llm=llm, db_helper=db)

        # 2. 获取已有 analyst_reports 的 (symbol, trade_date)
        all_items = get_symbols_and_dates(db)
        if not all_items:
            print("[WARN] analyst_reports 中没有任何数据，直接退出。")
            return

        # 可选：只保留指定 symbol
        if args.symbol:
            all_items = [(s, d) for (s, d) in all_items if s == args.symbol]
            if not all_items:
                print(f"[WARN] 指定 symbol={args.symbol} 在 analyst_reports 中无记录。")
                return

        # 3. 按日期范围过滤
        items = filter_by_range(all_items, start=args.start, end=args.end)
        if not items:
            print("[WARN] 在指定日期范围内没有任何 analyst_reports 记录。")
            return

        total = len(items)
        print(f"[INFO] 需要处理的 (symbol, date) 组合数量: {total}")

        # 4. 逐个执行 History Maintainer 节点
        for idx, (symbol, trade_date) in enumerate(items, 1):
            print(f"\n[{idx}/{total}] {symbol} @ {trade_date}")

            state = {
                "company_of_interest": symbol,
                "trade_date": trade_date,
                "trading_session": "post_close",
                "messages": [],
                "current_position": None,
                "portfolio_state": None,
            }

            try:
                result = node(state)
                log = result.get("history_maintainer_log", [])
                ok_count = sum(1 for x in log if x.get("status") == "ok")
                skipped_count = sum(1 for x in log if x.get("status") == "skipped")
                error_count = sum(1 for x in log if x.get("status") == "error")
                print(
                    f"  [OK] 完成 History Maintainer: ok={ok_count}, skipped={skipped_count}, error={error_count}"
                )
            except Exception as exc:  # noqa: BLE001
                print(f"  [ERROR] History Maintainer 执行失败: {exc}")

            # 简单节流：每个交易日处理完后等待一小段时间，降低 RPM / TPM
            if args.sleep_ms and args.sleep_ms > 0:
                time.sleep(args.sleep_ms / 1000.0)


if __name__ == "__main__":
    main()

