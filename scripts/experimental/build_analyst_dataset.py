# -*- coding: utf-8 -*-
"""
构建 Analyst 数据集

分类：数据构建（见 README 三）
- 为离线测试提供 analyst_reports：在指定日期范围内运行 4 类 Analyst，将报告写入 memory.db。

功能：
1. 按自然日或「最近 N 个交易日」取交易日
2. 对每个交易日运行 Analyst（默认 4 类；可用 --types 仅构建 market / news 等）
3. 将报告写入数据库（默认 memory.db），并可选导出为 JSON

数据源（交易日历与行情）：
- 来自 tradingagents.core.data.loader.load_stock_data → yfinance → Yahoo Finance。
- 获取交易日历时会拉取 SPY 的 OHLCV，用其交易日 index 作为日历；该请求需走代理（否则易被限速）。

新闻 / 舆情类 Analyst（news、sentiment）使用的 `get_news`、`get_global_news`（与主图、数据集构建共用实现）：
- **主源**：Alpha Vantage（NEWS_SENTIMENT 等）。
- **备选**：若配置 `POLARIS_TOKEN` 或 `POLARIS_API_KEY`（可选 `POLARIS_BASE_URL`），则在 AV 无数据或异常时自动 fallback 至 [The Polaris Report](https://thepolarisreport.com/docs)；返回行形状与 AV 一致（见 `datasources/polaris_av_news_adapter.py`）。
- Polaris HTTP 与 yfinance 相同：依赖 `HTTP_PROXY`/`HTTPS_PROXY` 或本脚本开头的 `ensure_data_fetch_proxy()`（`PROXY_HOST`+`PROXY_PORT`）。

代理说明：
- 本脚本内**所有数据拉取**（交易日历、Analyst 内 yfinance 等）尽量走代理：
  在 .env 中设置 PROXY_HOST + PROXY_PORT（会自动 USE_PROXY=true 并写入 HTTP_PROXY），
  或已设置 HTTP_PROXY/HTTPS_PROXY；详见 `ensure_data_fetch_proxy()`。
- **LLM API（Silicon Flow）不使用代理**：创建 LLM 前会 `clear_proxy_env_for_llm()`，
  LLM 使用 httpx trust_env=False；创建完成后再次 `ensure_data_fetch_proxy()` 供后续 Analyst 工具使用。

LLM：仅 Silicon Flow，见 .env 的 `Silicon_API_KEY`、`base_url_silicon`（可选）、`SILICON_MODEL`；
多 key 见 `create_silicon_llm`（逗号分隔 / 列表）。

LLM 限速故障转移（仅本脚本）：若同时配置下列环境变量，则在主线路失败时自动改用备用 OpenAI 兼容端点
（由 LangChain ``with_fallbacks`` 实现，常见于 429 / 超时 / 连接错误）：
  - LLM_FALLBACK_API_KEY
  - LLM_FALLBACK_BASE_URL（如另一兼容网关的 /v1 地址）
  - LLM_FALLBACK_MODEL（必填，如 qwen-plus 或 Silicon 模型名）
  可选：LLM_FALLBACK_TEMPERATURE（默认 0.1）
"""

import json
import os
import sys
import sqlite3
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, List, Optional, Tuple

# 全部 Analyst 类型（顺序固定：market 无 Alpha Vantage 限流，其余按 AV 工具链）
ALL_ANALYST_TYPES: Tuple[str, ...] = ("market", "news", "fundamentals", "sentiment")

# Alpha Vantage 限流：news/fundamentals/sentiment 调用后等待，避免 5次/分钟
_AV_RATE_DELAY = 13

# API 调用失败时报告中的典型表述，含任一则视为失败，不写入 DB
_API_FAILURE_KEYWORDS = [
    "未能获取",
    "API 失效",
    "API服务全面限频",
    "API访问中断",
    "API访问限制",  # 如「由于API访问限制」
    "API密钥耗尽",
    "密钥耗尽",
    "Rate limited",
    "数据获取失败",
    "数据获取暂时不可用",  # 数据源暂时不可用时的表述
    "暂时不可用",  # 如「数据获取暂时不可用」（可能分写）
    "无法获取",  # 如「无法获取任何实时财务」
]

# 添加项目根目录到路径，并优先加载 .env（保证 Silicon_API_KEY 等可用）
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

try:
    from dotenv import load_dotenv
    env_path = REPO_ROOT / ".env"
    load_dotenv(env_path)
    if not env_path.exists():
        print(f"[WARN] .env 不存在: {env_path}")
except ImportError:
    pass

from tradingagents.llm_env_compat import parse_silicon_api_keys
from tradingagents.agents.utils.memory_db_helper import MemoryDBHelper
from tradingagents.core.data_adapter import DataAdapter
from tradingagents.agents.analysts.market_analyst.agent import create_market_analyst
from tradingagents.agents.analysts.news_analyst.agent import create_news_analyst
from tradingagents.agents.analysts.fundamentals_analyst.agent import create_fundamentals_analyst
from tradingagents.agents.analysts.social_media_analyst.agent import create_social_media_analyst


def ensure_data_fetch_proxy() -> None:
    """
    为本脚本内所有数据拉取（交易日历、Analyst 内 yfinance 等）设置代理环境变量。

    - 若 .env 中配置了 PROXY_HOST + PROXY_PORT，则强制视为需要代理（等同 USE_PROXY=true）。
    - 调用与 DataAdapter 相同的 setup_proxy，保证 yfinance/requests 走代理。
    """
    from tradingagents.core.data.loader import setup_proxy

    host = (os.getenv("PROXY_HOST") or "").strip()
    port = (os.getenv("PROXY_PORT") or "").strip()
    use_flag = os.getenv("USE_PROXY", "false").lower() == "true"

    if host and port:
        os.environ["USE_PROXY"] = "true"
        setup_proxy()
        print("[PROXY] 数据获取：已根据 PROXY_HOST/PROXY_PORT 启用 HTTP(S)_PROXY")
    elif os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY"):
        os.environ["USE_PROXY"] = "true"
        print("[PROXY] 数据获取：使用当前环境变量中的 HTTP(S)_PROXY")
    elif use_flag:
        url = setup_proxy()
        if url:
            print("[PROXY] 数据获取：已根据 USE_PROXY=true 启用代理")
        else:
            print(
                "[WARN] USE_PROXY=true 但未配置 PROXY_HOST/PROXY_PORT，"
                "无法设置代理，yfinance 可能限流"
            )
    else:
        print(
            "[WARN] 数据获取未配置代理：建议设置 USE_PROXY=true 与 PROXY_HOST/PROXY_PORT，"
            "否则 yfinance 易触发 Rate limit"
        )


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return float(str(raw).strip())
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return int(str(raw).strip())
    except ValueError:
        return default


def clear_proxy_env_for_llm() -> None:
    """创建 LLM 前清除代理相关环境变量，避免 Silicon/DashScope 等 API 误走代理。"""
    for key in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "http_proxy",
        "https_proxy",
        "ALL_PROXY",
        "all_proxy",
    ):
        os.environ.pop(key, None)


def _build_exceptions_for_fallback() -> Tuple[type, ...]:
    """构建用于 with_fallbacks 的异常类型集合。"""
    try:
        import openai

        exc_list: List[type] = [
            openai.RateLimitError,
            openai.APITimeoutError,
            openai.APIConnectionError,
        ]
        internal = getattr(openai, "InternalServerError", None)
        auth = getattr(openai, "AuthenticationError", None)
        permission = getattr(openai, "PermissionDeniedError", None)
        if internal is not None:
            exc_list.append(internal)
        # 某个 key 失效时可自动切到下一个 key
        if auth is not None:
            exc_list.append(auth)
        if permission is not None:
            exc_list.append(permission)
        return tuple(exc_list)
    except Exception:
        return (Exception,)


def create_silicon_llm():
    """
    使用 .env 中 Silicon_API_KEY / SILICON_API_KEY 创建 LLM（不走代理）。

    支持单 key 或多 key（列表/逗号分隔）；多 key 时自动故障转移。
    """
    raw_keys = os.getenv("Silicon_API_KEY") or os.getenv("SILICON_API_KEY") or ""
    keys = parse_silicon_api_keys(raw_keys)
    base_url = (
        os.getenv("base_url_silicon")
        or os.getenv("BASE_URL_SILICON")
        or "https://api.siliconflow.cn/v1"
    ).strip().strip('"\'')
    model = os.getenv("SILICON_MODEL", "deepseek-ai/DeepSeek-V3.2")
    if not keys:
        raise ValueError(
            "未找到 Silicon API Key，请设置 Silicon_API_KEY（支持单 key、逗号分隔或列表）"
        )

    primary = _create_openai_compatible_llm(keys[0], base_url, model, temperature=0.1)
    if len(keys) <= 1:
        return primary
    if not hasattr(primary, "with_fallbacks"):
        print("[WARN] 当前 LLM 不支持 with_fallbacks，Silicon 多 key 将仅使用首个 key")
        return primary

    fallbacks = [
        _create_openai_compatible_llm(k, base_url, model, temperature=0.1)
        for k in keys[1:]
    ]
    exc_types = _build_exceptions_for_fallback()
    print(f"[LLM] Silicon 检测到 {len(keys)} 个 key，已启用多 key 故障转移")
    try:
        return primary.with_fallbacks(fallbacks, exceptions_to_handle=exc_types)
    except TypeError:
        return primary.with_fallbacks(fallbacks)


def _create_openai_compatible_llm(
    api_key: str,
    base_url: str,
    model: str,
    *,
    temperature: float = 0.1,
) -> Any:
    """创建直连、不走代理的 ChatOpenAI（OpenAI 兼容协议）。"""
    import httpx
    from langchain_openai import ChatOpenAI

    clear_proxy_env_for_llm()
    # 连接阶段单独限时，避免「网络不通/代理异常」时长时间卡住无输出
    connect_s = _env_float("LLM_HTTP_CONNECT_TIMEOUT", 15.0)
    read_s = _env_float("LLM_HTTP_READ_TIMEOUT", 120.0)
    write_s = _env_float("LLM_HTTP_WRITE_TIMEOUT", 120.0)
    pool_s = _env_float("LLM_HTTP_POOL_TIMEOUT", 10.0)
    max_retries = max(0, _env_int("LLM_MAX_RETRIES", 0))

    http_client = httpx.Client(
        verify=True,
        trust_env=False,
        proxy=None,
        timeout=httpx.Timeout(
            connect=connect_s,
            read=read_s,
            write=write_s,
            pool=pool_s,
        ),
    )
    kwargs = dict(
        api_key=api_key.strip().strip('"\''),
        base_url=base_url.strip().strip('"\''),
        model=model.strip(),
        temperature=temperature,
        http_client=http_client,
        max_retries=max_retries,
    )
    try:
        return ChatOpenAI(**kwargs)
    except TypeError:
        kwargs.pop("max_retries", None)
        return ChatOpenAI(**kwargs)


def create_fallback_llm_from_env() -> Optional[Any]:
    """
    从环境变量读取备用 LLM；未完整配置时返回 None。

    需要：LLM_FALLBACK_API_KEY、LLM_FALLBACK_BASE_URL、LLM_FALLBACK_MODEL
    """
    api_key = (os.getenv("LLM_FALLBACK_API_KEY") or "").strip().strip('"\'')
    base_url = (os.getenv("LLM_FALLBACK_BASE_URL") or "").strip().strip('"\'')
    model = (os.getenv("LLM_FALLBACK_MODEL") or "").strip().strip('"\'')
    if not api_key or not base_url or not model:
        return None
    temp_s = os.getenv("LLM_FALLBACK_TEMPERATURE", "0.1").strip()
    try:
        temperature = float(temp_s)
    except ValueError:
        temperature = 0.1
    return _create_openai_compatible_llm(api_key, base_url, model, temperature=temperature)


def wrap_llm_with_fallback_for_build(primary: Any) -> Any:
    """
    若已配置 LLM_FALLBACK_*，将 primary 包装为带故障转移的 Runnable（限速/超时等时切换备用）。
    """
    fallback = create_fallback_llm_from_env()
    if fallback is None:
        return primary
    if not hasattr(primary, "with_fallbacks"):
        print("[WARN] 主 LLM 不支持 with_fallbacks，已忽略 LLM_FALLBACK_* 配置")
        return primary
    # 优先在「限速、超时、连接、服务端 5xx」时切换；避免把所有 APIStatusError 都转移（含 400）
    exc_types = _build_exceptions_for_fallback()

    model_name = (os.getenv("LLM_FALLBACK_MODEL") or "").strip() or "(fallback)"
    print(
        f"[LLM] 已启用故障转移：主线路遇限速/超时/连接或 5xx 时将切换备用（LLM_FALLBACK_MODEL={model_name}）"
    )
    try:
        return primary.with_fallbacks([fallback], exceptions_to_handle=exc_types)
    except TypeError:
        # 旧版 LangChain 可能无 exceptions_to_handle
        return primary.with_fallbacks([fallback])


def get_trading_dates(
    start_date: str,
    end_date: str,
    data_adapter: DataAdapter,
    symbol_for_calendar: str = "SPY",
) -> List[str]:
    """获取 start_date 到 end_date 之间的交易日列表（含两端）。"""
    print(
        f"[数据] 拉取交易日历：{symbol_for_calendar} {start_date}~{end_date}（yfinance，可能较慢）...",
        flush=True,
    )
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
    return _api_failure_skip_reason(content) is not None


def _api_failure_skip_reason(content: str) -> Optional[str]:
    """若应 SKIP 则返回原因短语（便于调试），否则 None。"""
    if not content or not content.strip():
        return "空报告"
    for kw in _API_FAILURE_KEYWORDS:
        if kw in content:
            return f"关键词: {kw!r}"
    # Market Analyst 等可能输出 JSON，data_points_analyzed 为 0 表示未获取到实际数据
    if '"data_points_analyzed": 0' in content or "'data_points_analyzed': 0" in content:
        return "data_points_analyzed: 0"
    if "data_limitation_note" in content and ("API" in content or "限制" in content):
        return "data_limitation_note + API/限制"
    return None


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


def parse_analyst_types_arg(types_str: Optional[str]) -> Tuple[str, ...]:
    """
    解析 --types 参数。未指定或空则返回全部 4 类；否则为逗号分隔的去重列表，顺序与 ALL_ANALYST_TYPES 一致。
    """
    if not types_str or not types_str.strip():
        return ALL_ANALYST_TYPES
    requested = [p.strip().lower() for p in types_str.split(",") if p.strip()]
    if not requested:
        return ALL_ANALYST_TYPES
    valid = set(ALL_ANALYST_TYPES)
    for p in requested:
        if p not in valid:
            raise ValueError(
                f"未知的 analyst 类型: {p}，可选: {', '.join(ALL_ANALYST_TYPES)}"
            )
    # 按 ALL_ANALYST_TYPES 顺序排列，去重
    seen = set()
    ordered: List[str] = []
    for t in ALL_ANALYST_TYPES:
        if t in requested and t not in seen:
            seen.add(t)
            ordered.append(t)
    return tuple(ordered)


def run_analysts_for_date(
    symbol: str,
    trade_date: str,
    llm,
    db_helper: MemoryDBHelper,
    only_missing: bool = False,
    types_filter: Optional[Tuple[str, ...]] = None,
) -> Tuple[int, int]:
    """
    对指定 (symbol, trade_date) 运行 Analyst 并写入 DB。
    types_filter: 仅运行这些类型；None 表示全部 4 类。
    only_missing=True 时，仅运行「无报告或报告为 API 失败」的类型，节省 API/LLM 调用。
    返回 (成功保存条数, 本次计划运行条数)。
    """
    analysts_config = [
        ("market", "market_report", False),
        ("news", "news_report", True),
        ("fundamentals", "fundamentals_report", True),
        ("sentiment", "sentiment_report", True),
    ]
    if types_filter:
        allowed = set(types_filter)
        analysts_config = [x for x in analysts_config if x[0] in allowed]

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
            return 0, 0
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
            print(f"  [限流] 等待 {_AV_RATE_DELAY}s 后运行 {analyst_type}...", flush=True)
            time.sleep(_AV_RATE_DELAY)
        try:
            read_to = _env_float("LLM_HTTP_READ_TIMEOUT", 120.0)
            print(
                f"  [LLM] 开始 {analyst_type} @ {trade_date}（读超时约 {read_to:.0f}s，见 LLM_HTTP_READ_TIMEOUT）...",
                flush=True,
            )
            initial_state = {
                "company_of_interest": symbol,
                "trade_date": trade_date,
                report_key: "",
                "messages": [],
            }
            result = analyst_func(initial_state)
            print(f"  [LLM] 完成 {analyst_type} @ {trade_date}", flush=True)
            report_content = result.get(report_key, "")
            if not report_content:
                for msg in reversed(result.get("messages", [])):
                    if hasattr(msg, "content") and msg.content:
                        report_content = msg.content
                        break
            if report_content:
                skip_reason = _api_failure_skip_reason(report_content)
                if skip_reason is not None:
                    print(
                        f"  [SKIP] {analyst_type} 报告含 API 失败表述，不写入 — {skip_reason}"
                    )
                elif db_helper.insert_report_or_update(
                    analyst_type=analyst_type,
                    symbol=symbol,
                    trade_date=trade_date,
                    report_content=report_content,
                ):
                    success_count += 1
        except Exception as e:
            print(f"  [LLM] 结束 {analyst_type} @ {trade_date}（异常）", flush=True)
            print(f"  [ERROR] {analyst_type} @ {trade_date}: {e}")
        if uses_av:
            prev_used_av = True
    return success_count, len(to_run)


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
    parser.add_argument("--start", type=str, default=None, help="开始日期 YYYY-MM-DD；指定后与 --end 共同确定区间，忽略 --days")
    parser.add_argument("--end", type=str, default="2025-03-01", help="结束日期 YYYY-MM-DD")
    parser.add_argument("--days", type=int, default=0, help="从结束日期往前推的自然日（仅当未指定 --start 且未指定 --trading-days 时有效）")
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
        "--export-only",
        action="store_true",
        help="仅按当前 DB 重新导出 JSON（去重），不运行 Analyst；需配合 --end、--trading-days 等确定日期范围",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="若当日「本次 --types 所选类型」的报告均已存在则跳过该日（适合断点续传；未指定 --types 时等价于 4/4 均已存在）",
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
    parser.add_argument(
        "--types",
        type=str,
        default=None,
        metavar="TYPES",
        help="仅构建指定类型，逗号分隔：market,news,fundamentals,sentiment；默认全部。例：--types market 或 --types market,news",
    )
    parser.add_argument(
        "--llm-read-timeout",
        type=float,
        default=None,
        metavar="SEC",
        help="覆盖 LLM HTTP 读超时（秒）；等价于环境变量 LLM_HTTP_READ_TIMEOUT，默认 120",
    )
    args = parser.parse_args()

    try:
        types_to_build = parse_analyst_types_arg(args.types)
    except ValueError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    if args.export_only:
        end_date = args.end
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        if args.start:
            start_date = args.start
        elif args.trading_days and args.trading_days > 0:
            start_dt = end_dt - timedelta(days=60)
            start_date = start_dt.strftime("%Y-%m-%d")
        else:
            days = args.days if args.days > 0 else 7
            start_dt = end_dt - timedelta(days=days)
            start_date = start_dt.strftime("%Y-%m-%d")
        out_path = args.output or f"analyst_dataset_{args.symbol}_{start_date}_{end_date}_temp.json"
        export_dataset_json(args.db, start_date, end_date, args.symbol, out_path)
        return

    # 数据阶段：统一启用代理（PROXY_HOST+PORT 或 USE_PROXY）；LLM 阶段会临时清除后再恢复
    ensure_data_fetch_proxy()

    if args.dates:
        # 使用 --dates 指定日期，直接构建（适用于补全失败报告等场景）
        trading_dates = [d.strip() for d in args.dates.split(",") if d.strip()]
        if not trading_dates:
            print("[ERROR] --dates 为空或格式有误")
            sys.exit(1)
        start_date = trading_dates[0]
        end_date_export = trading_dates[-1]
        print(f"[构建数据集] 标的={args.symbol}, 指定日期={len(trading_dates)} 天, 数据库={args.db}")
        print(f"[类型] {', '.join(types_to_build)}")
        print(f"[交易日] {trading_dates}")
    else:
        end_date = args.end
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        if args.start:
            # --start + --end 确定区间，获取区间内全部交易日
            start_date_for_fetch = args.start
            print(f"[构建数据集] 标的={args.symbol}, 区间={args.start}~{end_date}, 数据库={args.db}")
            print(f"[类型] {', '.join(types_to_build)}")
        elif args.trading_days is not None and args.trading_days > 0:
            # 取最近 N 个交易日：先拉足够长的区间再截取最后 N 天
            window_start = (end_dt - timedelta(days=60)).strftime("%Y-%m-%d")
            start_date_for_fetch = window_start
            print(f"[构建数据集] 标的={args.symbol}, 结束日={end_date}, 数据库={args.db}")
            print(f"[类型] {', '.join(types_to_build)}")
        else:
            days = args.days if args.days > 0 else 7
            start_dt = end_dt - timedelta(days=days)
            start_date_for_fetch = start_dt.strftime("%Y-%m-%d")
            print(f"[构建数据集] 标的={args.symbol}, 结束日={end_date}, 数据库={args.db}")
            print(f"[类型] {', '.join(types_to_build)}")

        # 1. 获取交易日历（拉取 SPY 数据，走 loader.load_stock_data → yfinance）
        data_adapter = DataAdapter(use_cache=True)
        trading_dates = get_trading_dates(start_date_for_fetch, end_date, data_adapter)
        if not trading_dates:
            print("[ERROR] 该日期范围内无交易日。")
            sys.exit(1)
        if args.start:
            # 使用 --start 时不再按 trading_days 截断，保留区间内全部交易日
            pass
        elif args.trading_days is not None and args.trading_days > 0:
            trading_dates = trading_dates[-args.trading_days:]
            if len(trading_dates) < args.trading_days:
                print(f"[WARN] 仅得到 {len(trading_dates)} 个交易日（请求 {args.trading_days} 个）")
        start_date = trading_dates[0]
        end_date_export = trading_dates[-1]
        print(f"[交易日] 共 {len(trading_dates)} 天: {trading_dates}")

    if args.llm_read_timeout is not None:
        os.environ["LLM_HTTP_READ_TIMEOUT"] = str(args.llm_read_timeout)

    # 2. 创建 LLM：先清除代理环境变量，确保 LLM API 直连（不走代理）
    clear_proxy_env_for_llm()
    print("[LLM] Silicon Flow（Silicon_API_KEY / base_url_silicon），直连、无代理")
    llm = create_silicon_llm()
    llm = wrap_llm_with_fallback_for_build(llm)
    # 3. Analyst 内数据拉取（yfinance 等）再次启用代理
    ensure_data_fetch_proxy()

    db_helper = MemoryDBHelper(args.db)

    total_ok = 0
    skipped = 0
    n_types = len(types_to_build)
    for i, trade_date in enumerate(trading_dates, 1):
        if args.skip_existing:
            existing = sum(
                1 for at in types_to_build
                if db_helper.query_today_report(at, args.symbol, trade_date)
            )
            if n_types > 0 and existing >= n_types:
                print(f"\n[{i}/{len(trading_dates)}] {trade_date} ... [SKIP] {n_types}/{n_types}（所选类型）已存在")
                skipped += 1
                continue
        print(f"\n[{i}/{len(trading_dates)}] {trade_date} ...")
        n, planned = run_analysts_for_date(
            args.symbol, trade_date, llm, db_helper,
            only_missing=args.only_missing,
            types_filter=types_to_build if n_types < len(ALL_ANALYST_TYPES) else None,
        )
        total_ok += n
        if planned > 0:
            print(f"  保存 {n}/{planned} 条报告。")
        else:
            print(f"  保存 {n} 条报告（本次无需运行：仅 missing 时已全部有效）。")
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
