# -*- coding: utf-8 -*-
"""
按「从后往前」顺序逐个补全 NVDA 的 API 失败报告。

失败日期来源：`api_failures_report.txt` 中 NVDA 相关的行（fundamentals/news）。

用法：
  python rebuild_failed_reports.py
    # 从最新的失败日期（当前为 2026-02-04）起全部补全

  python rebuild_failed_reports.py --from 2026-01-30
    # 从指定日期起补全（跳过更晚的），格式 YYYY-MM-DD

每次只补全一个日期，补全后暂停 INTERVAL_MINUTES 分钟再继续，
以降低 Alpha Vantage 日限 500 次的影响。
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

# NVDA 失败日期，从新到旧（从后往前）
# 来源：api_failures_report.txt 中包含 “NVDA” 且说明 “无法获取/数据获取失败/受限于” 的行。
NVDA_FAILED_DATES = [
    "2026-02-04",
    "2026-01-30",
    "2026-01-27",
    "2026-01-23",
    "2026-01-22",
]

INTERVAL_MINUTES = 5  # 每个日期之间暂停分钟数
PROJECT_ROOT = Path(__file__).parent


def main():
    parser = argparse.ArgumentParser(description="从后往前补全 NVDA API 失败报告")
    parser.add_argument(
        "--from",
        dest="from_date",
        default=None,
        help="从该日期起补全（含），格式 YYYY-MM-DD。例如 --from 2026-02-10",
    )
    args = parser.parse_args()

    dates = NVDA_FAILED_DATES
    if args.from_date:
        try:
            idx = NVDA_FAILED_DATES.index(args.from_date)
            dates = NVDA_FAILED_DATES[idx:]
        except ValueError:
            print(f"未找到日期 {args.from_date}，可用: {NVDA_FAILED_DATES}")
            sys.exit(1)
        print(f"从 {args.from_date} 起补全，共 {len(dates)} 个日期")

    total = len(dates)
    for i, date in enumerate(dates, 1):
        print(f"\n[{i}/{total}] 补全 NVDA {date} ...")
        cmd = [
            sys.executable,
            "build_analyst_dataset.py",
            "--symbol", "NVDA",
            "--dates", date,
            "--only-missing",
            "--db", "memory.db",
            "--use-silicon",
            "--no-export",
        ]
        ret = subprocess.run(cmd, cwd=PROJECT_ROOT)
        if ret.returncode != 0:
            print(f"[WARN] {date} 执行返回码 {ret.returncode}，可能部分失败")
        else:
            print(f"[OK] {date} 完成")

        if i < total:
            wait_sec = INTERVAL_MINUTES * 60
            print(f"等待 {INTERVAL_MINUTES} 分钟后继续下一个日期 ...")
            time.sleep(wait_sec)

    print("\n全部补全完成。可运行 python check_api_failures.py 复查。")


if __name__ == "__main__":
    main()
