# -*- coding: utf-8 -*-
"""
查看 memory.db 中 Analyst 报告内容

用法：
  python view_report.py                          # 交互式选择
  python view_report.py 2026-02-04               # 指定日期，输出 4 类报告
  python view_report.py 2026-02-04 market        # 指定日期和 analyst 类型
  python view_report.py --list                    # 列出 NVDA 可用日期
"""
import argparse
import sqlite3
import sys

DB = "memory.db"
SYMBOL = "NVDA"
ANALYST_TYPES = ("market", "news", "fundamentals", "sentiment")


def list_dates(db: str, symbol: str) -> list[str]:
    conn = sqlite3.connect(db)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT DISTINCT trade_date FROM analyst_reports WHERE symbol=? ORDER BY trade_date",
        (symbol,),
    )
    dates = [r[0] for r in cursor.fetchall()]
    conn.close()
    return dates


def get_report(db: str, symbol: str, trade_date: str, analyst_type: str) -> str | None:
    conn = sqlite3.connect(db)
    cursor = conn.cursor()
    cursor.execute(
        """SELECT report_content FROM analyst_reports
           WHERE symbol=? AND trade_date=? AND analyst_type=?
           ORDER BY id DESC LIMIT 1""",
        (symbol, trade_date, analyst_type),
    )
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def main():
    parser = argparse.ArgumentParser(description="查看 Analyst 报告内容")
    parser.add_argument("trade_date", nargs="?", help="交易日期 YYYY-MM-DD")
    parser.add_argument(
        "analyst_type",
        nargs="?",
        choices=ANALYST_TYPES,
        help="Analyst 类型: market/news/fundamentals/sentiment",
    )
    parser.add_argument("--list", action="store_true", help="列出可用日期")
    parser.add_argument("--db", default=DB, help="数据库路径")
    parser.add_argument("--symbol", default=SYMBOL, help="股票代码")
    args = parser.parse_args()

    if args.list:
        dates = list_dates(args.db, args.symbol)
        print(f"NVDA 可用日期 ({len(dates)} 天):")
        for d in dates:
            print(f"  {d}")
        return

    if not args.trade_date:
        print("用法: python view_report.py <日期> [analyst_type]")
        print("  或: python view_report.py --list")
        dates = list_dates(args.db, args.symbol)
        if dates:
            print(f"\n最近 5 个可用日期: {dates[-5:]}")
        return

    trade_date = args.trade_date
    types_to_show = [args.analyst_type] if args.analyst_type else list(ANALYST_TYPES)

    for at in types_to_show:
        content = get_report(args.db, args.symbol, trade_date, at)
        print("\n" + "=" * 80)
        print(f"[{trade_date}] {at.upper()} Analyst")
        print("=" * 80)
        if content:
            print(content)
        else:
            print("(无报告)")


if __name__ == "__main__":
    main()
