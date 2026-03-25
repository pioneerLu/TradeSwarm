# -*- coding: utf-8 -*-
"""
检查 memory.db 中因 API 限制未能成功获取数据的报告。

- 按 symbol 区分标的，输出中带 symbol；报告可用于人工按日期调用 `build_analyst_dataset --dates ... --only-missing` 补全。
- 「受限于」仅在与 API/数据/访问 等词同时出现时计为失败，减少误报。

用法:
  python check_api_failures.py                    # 全部标的
  python check_api_failures.py --symbol NVDA     # 仅 NVDA
  python check_api_failures.py --db path/to/memory.db
"""
import argparse
import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# 明确表示 API/数据获取失败的表述
KEYWORDS_STRONG = [
    "未能获取",
    "API 失效",
    "API服务全面限频",
    "限频",
    "访问中断",
    "API访问中断",
    "API访问限制",
    "数据源限制",
    "API密钥耗尽",
    "密钥耗尽",
    "Rate limited",
    "数据获取失败",
    "数据获取暂时不可用",
    "暂时不可用",
    "无法获取",
    "无法提供",  # 如「本报告无法提供...的详细财务指标」
]

# 弱关键词：仅当内容中同时出现 API/数据/访问 等词时才计为失败，避免「受限于篇幅」等误报
KEYWORD_WEAK = "受限于"
WEAK_REQUIRED_SUBSTRINGS = ("API", "数据", "访问", "数据源", "限频")


def _is_api_failure(content: str) -> tuple[bool, str]:
    """若内容疑似 API 失败则返回 (True, 命中的关键词)，否则 (False, '')。"""
    if not (content or content.strip()):
        return False, ""
    for kw in KEYWORDS_STRONG:
        if kw in content:
            return True, kw
    if KEYWORD_WEAK in content:
        for sub in WEAK_REQUIRED_SUBSTRINGS:
            if sub in content:
                return True, KEYWORD_WEAK
    # Market Analyst 等输出 JSON，data_points_analyzed 为 0 表示未获取实际数据
    if '"data_points_analyzed": 0' in content or "'data_points_analyzed': 0" in content:
        return True, "data_points_analyzed:0"
    if "data_limitation_note" in content and ("API" in content or "限制" in content):
        return True, "data_limitation_note"
    return False, ""


def main():
    parser = argparse.ArgumentParser(description="检查 memory.db 中可能受 API 限制影响的报告")
    parser.add_argument("--symbol", type=str, default=None, help="仅检查该标的，如 NVDA")
    parser.add_argument("--db", type=str, default="memory.db", help="数据库路径")
    args = parser.parse_args()
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"数据库不存在: {db_path}")
        return

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    sql = (
        "SELECT trade_date, analyst_type, symbol, report_content FROM analyst_reports"
    )
    params = []
    if args.symbol:
        sql += " WHERE symbol = ?"
        params.append(args.symbol.strip().upper())
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()

    found = []
    for date, atype, symbol, content in rows:
        if not content:
            continue
        ok, kw = _is_api_failure(content)
        if ok:
            found.append((date, atype, symbol or "", kw, content[:300]))

    # 去重：同一 (date, atype, symbol) 只保留一条，按 symbol、date、atype 排序
    seen = set()
    unique = []
    for item in sorted(found, key=lambda x: (x[2], x[0], x[1])):
        key = (item[0], item[1], item[2])
        if key not in seen:
            seen.add(key)
            unique.append(item)

    symbol_note = f"（仅 {args.symbol}）" if args.symbol else ""
    lines = [f"共发现 {len(unique)} 条可能受 API 限制影响的报告{symbol_note}:\n"]
    for date, atype, symbol, kw, content in unique:
        sn = content.replace("\n", " ").strip()[:150]
        lines.append(f"  {date} | {symbol} | {atype} | 关键词: {kw}")
        lines.append(f"    {sn}...")
        lines.append("")

    out = "\n".join(lines)
    report_path = REPO_ROOT / "api_failures_report.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(out)
    print(f"共 {len(unique)} 条报告可能受 API 限制影响，详情已写入 {report_path}")


if __name__ == "__main__":
    main()
