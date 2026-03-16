# -*- coding: utf-8 -*-
"""
构建 Analyst 数据集

功能：
1. 在指定日期范围内，按自然日或「最近 N 个交易日」取交易日
2. 对每个交易日运行 4 类 Analyst（market, news, fundamentals, sentiment）
3. 将报告写入数据库（默认 memory.db），并导出为临时 JSON 便于检查

数据源（交易日历与行情）：
- 来自 tradingagents.core.data.loader.load_stock_data → yfinance → Yahoo Finance。
- 获取交易日历时会拉取 SPY 的 OHLCV，用其交易日 index 作为日历；该请求需走代理（否则易被限速）。

代理说明：
- 数据获取需挂代理时，在 .env 中设置：
  USE_PROXY=true, PROXY_HOST=..., PROXY_PORT=...
  或直接设置 HTTP_PROXY/HTTPS_PROXY（脚本会在获取数据前据此启用代理）。
- LLM 运行不能使用代理；脚本会在创建 LLM 前临时清除代理环境变量，
  创建 LLM 后再恢复，以便 Analyst 内部的数据拉取仍可走代理。

LLM 可选：默认使用 config + DASHSCOPE_API_KEY；加 --use-silicon 时使用
.env 中 Silicon_API_KEY 与 base_url_silicon（Silicon Flow）。
"""

import json
import os
import sys
import sqlite3
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import List

# Alpha Vantage 限流：news/fundamentals/sentiment 调用后等待，避免 5次/分钟
_AV_RATE_DELAY = 13

# API 调用失败时报告中的典型表述，含任一则视为失败，不写入 DB
_API_FAILURE_KEYWORDS = [
    "未能获取",
    "API 失效",
    "API服务全面限频",
    "API访问中断",
    "API密钥耗尽",
    "密钥耗尽",
    "Rate limited",
    "数据获取失败",
    "无法获取",  # 如「无法获取任何实时财务」
]

# 添加项目根目录到路径，并优先加载 .env（保证 DASHSCOPE_API_KEY 等可用）
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from dotenv import load_dotenv
    env_path = project_root / ".env"
    load_dotenv(env_path)
    if not env_path.exists():
        print(f"[WARN] .env 不存在: {env_path}")
except ImportError:
    pass

from tradingagents.graph.utils import load_llm_from_config
from tradingagents.agents.utils.memory_db_helper import MemoryDBHelper
from tradingagents.core.data_adapter import DataAdapter
from tradingagents.agents.analysts.market_analyst.agent import create_market_analyst
from tradingagents.agents.analysts.news_analyst.agent import create_news_analyst
from tradingagents.agents.analysts.fundamentals_analyst.agent import create_fundamentals_analyst
from tradingagents.agents.analysts.social_media_analyst.agent import create_social_media_analyst


def create_silicon_llm():
    """使用 .env 中 Silicon_API_KEY、base_url_silicon 创建 LLM（不走代理）。"""
    import httpx
    from langchain_openai import ChatOpenAI
    api_key = (os.getenv("Silicon_API_KEY") or os.getenv("SILICON_API_KEY") or "").strip().strip('"\'')
    base_url = (os.getenv("base_url_silicon") or os.getenv("BASE_URL_SILICON") or "https://api.siliconflow.cn/v1").strip().strip('"\'')
    if not api_key:
        raise ValueError("未找到 Silicon API Key，请设置环境变量 Silicon_API_KEY")
    # LLM 不走代理
    if "HTTP_PROXY" in os.environ:
        del os.environ["HTTP_PROXY"]
    if "HTTPS_PROXY" in os.environ:
        del os.environ["HTTPS_PROXY"]
    http_client = httpx.Client(verify=True, trust_env=False, proxy=None, timeout=httpx.Timeout(60.0))
    return ChatOpenAI(
        api_key=api_key,
        base_url=base_url,
        model=os.getenv("SILICON_MODEL", "deepseek-ai/DeepSeek-V3.2"),
        temperature=0.1,
        http_client=http_client,
    )


def get_trading_dates(
    start_date: str,
    end_date: str,
    data_adapter: DataAdapter,
    symbol_for_calendar: str = "SPY",
) -> List[str]:
    """获取 start_date 到 end_date 之间的交易日列表（含两端）。"""
    df = data_adapter.load_stock_data_until(symbol_for_calendar, end_date, start_date=start_date)
    if df is None or len(df) == 0:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        dates = []
        current = start
        while current <= end:
            if current.weekday() < 5:
                dates.append(current.strftime("%Y-%m-%d"))
            current += timedelta(days=1)
        return sorted(dates)
    trading_dates = [
        d.strftime("%Y-%m-%d")
        for d in df.index
        if start_date <= d.strftime("%Y-%m-%d") <= end_date
    ]
    return sorted(trading_dates)


def _is_api_failure_report(content: str) -> bool:
    """检测报告内容是否包含 API 失败表述，若是则不写入 DB。"""
    if not content or not content.strip():
        return True
    for kw in _API_FAILURE_KEYWORDS:
        if kw in content:
            return True
    return False


def _need_rebuild(
    db_helper: MemoryDBHelper,
    symbol: str,
    trade_date: str,
    analyst_type: str,
) -> bool:
    """
    检查该类型报告是否需要重建：无报告或报告为 API 失败则需重建。
    """
    content = db_helper.query_today_report(analyst_type, symbol, trade_date)
    if not content:
        return True  # 无报告，需构建
    if _is_api_failure_report(content):
        return True  # 失败报告，需重建
    return False  # 已有有效报告，可跳过


def run_analysts_for_date(
    symbol: str,
    trade_date: str,
    llm,
    db_helper: MemoryDBHelper,
    only_missing: bool = False,
) -> int:
    """
    对指定 (symbol, trade_date) 运行 4 个 Analyst 并写入 DB。
    only_missing=True 时，仅运行「无报告或报告为 API 失败」的类型，节省 API/LLM 调用。
    返回成功保存的报告数量。
    """
    analysts_config = [
        ("market", "market_report", False),
        ("news", "news_report", True),
        ("fundamentals", "fundamentals_report", True),
        ("sentiment", "sentiment_report", True),
    ]

    # 若 only_missing，先筛选出需要运行的
    if only_missing:
        to_run = [
            (t, k, av)
            for t, k, av in analysts_config
            if _need_rebuild(db_helper, symbol, trade_date, t)
        ]
        skipped = len(analysts_config) - len(to_run)
        if skipped > 0:
            print(f"  [跳过] {skipped} 类已有有效报告")
        if not to_run:
            return 0
    else:
        to_run = analysts_config

    market_analyst = create_market_analyst(llm)
    news_analyst = create_news_analyst(llm)
    fundamentals_analyst = create_fundamentals_analyst(llm)
    social_media_analyst = create_social_media_analyst(llm)
    analyst_factory = {
        "market": market_analyst,
        "news": news_analyst,
        "fundamentals": fundamentals_analyst,
        "sentiment": social_media_analyst,
    }

    success_count = 0
    prev_used_av = False
    for analyst_type, report_key, uses_av in to_run:
        analyst_func = analyst_factory[analyst_type]
        if uses_av and prev_used_av:
            print(f"  [限流] 等待 {_AV_RATE_DELAY}s 后运行 {analyst_type}...")
            time.sleep(_AV_RATE_DELAY)
        try:
            initial_state = {
                "company_of_interest": symbol,
                "trade_date": trade_date,
                report_key: "",
                "messages": [],
            }
            result = analyst_func(initial_state)
            report_content = result.get(report_key, "")
            if not report_content:
                for msg in reversed(result.get("messages", [])):
                    if hasattr(msg, "content") and msg.content:
                        report_content = msg.content
                        break
            if report_content:
                if _is_api_failure_report(report_content):
                    print(f"  [SKIP] {analyst_type} 报告含 API 失败表述，不写入")
                elif db_helper.insert_report_or_update(
                    analyst_type=analyst_type,
                    symbol=symbol,
                    trade_date=trade_date,
                    report_content=report_content,
                ):
                    success_count += 1
        except Exception as e:
            print(f"  [ERROR] {analyst_type} @ {trade_date}: {e}")
        if uses_av:
            prev_used_av = True
    return success_count


def export_dataset_json(
    db_path: str,
    start_date: str,
    end_date: str,
    symbol: str,
    output_path: str,
) -> None:
    """将 analyst_reports 表中指定日期范围、标的的数据导出为 JSON。"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, analyst_type, symbol, trade_date, report_content, created_at
        FROM analyst_reports
        WHERE symbol = ? AND trade_date >= ? AND trade_date <= ?
        ORDER BY trade_date ASC, analyst_type ASC
        """,
        (symbol, start_date, end_date),
    )
    rows = cursor.fetchall()
    conn.close()

    # 按 (symbol, trade_date, analyst_type) 去重，保留 id 最大（最新）的一条
    seen = {}
    for row in rows:
        key = (row["symbol"], row["trade_date"], row["analyst_type"])
        if key not in seen or row["id"] > seen[key]["id"]:
            seen[key] = {k: row[k] for k in row.keys()}
    reports = [
        {
            "id": r["id"],
            "analyst_type": r["analyst_type"],
            "symbol": r["symbol"],
            "trade_date": r["trade_date"],
            "report_content": r["report_content"],
            "created_at": r["created_at"],
        }
        for r in seen.values()
    ]
    reports.sort(key=lambda x: (x["trade_date"], x["analyst_type"]))
    meta = {
        "symbol": symbol,
        "start_date": start_date,
        "end_date": end_date,
        "total_reports": len(reports),
        "generated_at": datetime.now().isoformat(),
    }
    out = {"meta": meta, "reports": reports}
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"[导出] 已写入 {output_path}，共 {len(reports)} 条报告。")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="构建 Analyst 数据集（写入 memory.db + 导出临时 JSON）")
    parser.add_argument("--end", type=str, default="2026-02-13", help="结束日期 YYYY-MM-DD")
    parser.add_argument("--days", type=int, default=0, help="从结束日期往前推的自然日（仅当未指定 --trading-days 时有效）")
    parser.add_argument(
        "--trading-days",
        type=int,
        default=None,
        metavar="N",
        help="取最近 N 个交易日（含结束日）；指定后忽略 --days",
    )
    parser.add_argument("--symbol", type=str, default="NVDA", help="股票代码")
    parser.add_argument("--db", type=str, default="memory.db", help="数据库路径")
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help="临时 JSON 输出路径，默认: analyst_dataset_<symbol>_<start>_<end>_temp.json",
    )
    parser.add_argument("--no-export", action="store_true", help="不导出 JSON，仅写入数据库")
    parser.add_argument(
        "--use-silicon",
        action="store_true",
        help="使用 .env 中 Silicon_API_KEY 与 base_url_silicon 作为 LLM（否则使用 DASHSCOPE_API_KEY）",
    )
    parser.add_argument(
        "--export-only",
        action="store_true",
        help="仅按当前 DB 重新导出 JSON（去重），不运行 Analyst；需配合 --end、--trading-days 等确定日期范围",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="若当日 4 类 Analyst 报告均已存在则跳过，仅构建缺失的日期（适合断点续传）",
    )
    parser.add_argument(
        "--dates",
        type=str,
        default=None,
        metavar="DATE1,DATE2,...",
        help="指定构建的日期（逗号分隔），如 2026-02-12,2026-02-10。指定后忽略 --end、--trading-days、--days",
    )
    parser.add_argument(
        "--only-missing",
        action="store_true",
        help="先检测再运行：仅构建「无报告或报告含 API 失败」的类型，跳过已有有效报告的，节省 API/LLM",
    )
    args = parser.parse_args()

    if args.export_only:
        end_date = args.end
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        if args.trading_days and args.trading_days > 0:
            start_dt = end_dt - timedelta(days=60)
            start_date = start_dt.strftime("%Y-%m-%d")
        else:
            days = args.days if args.days > 0 else 7
            start_dt = end_dt - timedelta(days=days)
            start_date = start_dt.strftime("%Y-%m-%d")
        out_path = args.output or f"analyst_dataset_{args.symbol}_{start_date}_{end_date}_temp.json"
        export_dataset_json(args.db, start_date, end_date, args.symbol, out_path)
        return

    # 保存当前代理设置，供 LLM 创建后恢复（Analyst 内数据拉取用）
    old_http_proxy = os.environ.get("HTTP_PROXY")
    old_https_proxy = os.environ.get("HTTPS_PROXY")

    # 数据源为 yfinance（Yahoo Finance），需挂代理时请设 USE_PROXY 或 HTTP_PROXY
    if os.getenv("PROXY_HOST") or os.getenv("HTTP_PROXY"):
        os.environ.setdefault("USE_PROXY", "true")

    if args.dates:
        # 使用 --dates 指定日期，直接构建（适用于补全失败报告等场景）
        trading_dates = [d.strip() for d in args.dates.split(",") if d.strip()]
        if not trading_dates:
            print("[ERROR] --dates 为空或格式有误")
            sys.exit(1)
        start_date = trading_dates[0]
        end_date_export = trading_dates[-1]
        print(f"[构建数据集] 标的={args.symbol}, 指定日期={len(trading_dates)} 天, 数据库={args.db}")
        print(f"[交易日] {trading_dates}")
    else:
        end_date = args.end
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        if args.trading_days is not None and args.trading_days > 0:
            # 取最近 N 个交易日：先拉足够长的区间再截取最后 N 天
            window_start = (end_dt - timedelta(days=60)).strftime("%Y-%m-%d")
            start_date_for_fetch = window_start
        else:
            days = args.days if args.days > 0 else 7
            start_dt = end_dt - timedelta(days=days)
            start_date_for_fetch = start_dt.strftime("%Y-%m-%d")

        print(f"[构建数据集] 标的={args.symbol}, 结束日={end_date}, 数据库={args.db}")

        # 1. 获取交易日历（拉取 SPY 数据，走 loader.load_stock_data → yfinance）
        data_adapter = DataAdapter(use_cache=True)
        trading_dates = get_trading_dates(start_date_for_fetch, end_date, data_adapter)
        if not trading_dates:
            print("[ERROR] 该日期范围内无交易日。")
            sys.exit(1)
        if args.trading_days is not None and args.trading_days > 0:
            trading_dates = trading_dates[-args.trading_days:]
            if len(trading_dates) < args.trading_days:
                print(f"[WARN] 仅得到 {len(trading_dates)} 个交易日（请求 {args.trading_days} 个）")
        start_date = trading_dates[0]
        end_date_export = trading_dates[-1]
        print(f"[交易日] 共 {len(trading_dates)} 天: {trading_dates}")

    # 2. 创建 LLM（会临时清除代理环境变量，确保 LLM 不走代理）
    if args.use_silicon:
        print("[LLM] 使用 Silicon Flow（Silicon_API_KEY / base_url_silicon）")
        llm = create_silicon_llm()
    else:
        if not os.getenv("DASHSCOPE_API_KEY"):
            print("[WARN] 未检测到 DASHSCOPE_API_KEY，请确认 .env 中存在 DASHSCOPE_API_KEY=... 或使用 --use-silicon")
        llm = load_llm_from_config()
    # 3. 恢复代理环境变量，以便 Analyst 内部的数据拉取（如有）仍可走代理
    if old_http_proxy is not None:
        os.environ["HTTP_PROXY"] = old_http_proxy
    if old_https_proxy is not None:
        os.environ["HTTPS_PROXY"] = old_https_proxy

    db_helper = MemoryDBHelper(args.db)

    analyst_types = ("market", "news", "fundamentals", "sentiment")
    total_ok = 0
    skipped = 0
    for i, trade_date in enumerate(trading_dates, 1):
        if args.skip_existing:
            existing = sum(
                1 for at in analyst_types
                if db_helper.query_today_report(at, args.symbol, trade_date)
            )
            if existing >= 4:
                print(f"\n[{i}/{len(trading_dates)}] {trade_date} ... [SKIP] 4/4 已存在")
                skipped += 1
                continue
        print(f"\n[{i}/{len(trading_dates)}] {trade_date} ...")
        n = run_analysts_for_date(
            args.symbol, trade_date, llm, db_helper,
            only_missing=args.only_missing,
        )
        total_ok += n
        print(f"  保存 {n}/4 条报告。")
    db_helper.close()

    print(f"\n[完成] 共保存 {total_ok} 条 Analyst 报告到 {args.db}。")
    if args.skip_existing and skipped > 0:
        print(f"  跳过 {skipped} 个已完整构建的日期。")

    if not args.no_export:
        out_path = args.output
        if not out_path:
            out_path = f"analyst_dataset_{args.symbol}_{start_date}_{end_date_export}_temp.json"
        export_dataset_json(args.db, start_date, end_date_export, args.symbol, out_path)


if __name__ == "__main__":
    main()
