#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
信号导出脚本（方案 A：Agent 输出信号 → QuantConnect 执行）

分类：数据构建 / 离线测试（见 README）
- 运行 Analyst（或从 DB 读）→ Pre-Open Graph → 信号解析
- 输出结构化信号 JSON 到 qc_signals/，供 QuantConnect 算法读取执行
- 方案 2a（分析工具）：`--export-mode rating` 不注入 Portfolio、不调用 `resolve_signal`，仅写出
  `research_manager.decision` 与 `risk_manager` 的 `fine_rating` / `final_decision` / `risk_level`（见 `ratings.json`）

使用流程：
1. 确保 memory.db 中有所需日期的 analyst_reports（可用 build_analyst_dataset 构建）
2. 可选：预先运行 run_history_maintainer_batch 生成 analyst_summaries
3. 运行本脚本导出信号
4. 将 qc_signals/ 目录内容复制到 QuantConnect 项目，运行回测

说明：
- **默认 --use-db-reports-only**：不现场调用四个 Analyst 写库；Pre-Open 图（Summary→Research→Trader→Risk）**仍会多次调用 LLM**。
- **记忆（DatabaseMemory）**：仅从 DB 表 cycle_reflections 读周期反思，且当前固定 weekly；若无记录则 get_memories 为空，属正常。
- **推荐**以此脚本为「从 Summary 跑全图并导出」的唯一 CLI；单日可用 --dates。
- **人工评判 / 调试**：`--graph-dump DIR` 在每个交易日写入 `DIR/{symbol}_{trade_date}/`（LangGraph `subgraphs=True`，子图内每一步落盘为 `step_NNNN__{命名空间}__{节点}_output.json/.txt`，另含 `full_state_snapshot.json` 与 `final_state_*`）。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from tradingagents.graph.trading_graph import create_trading_graph
from tradingagents.graph.utils import load_llm_from_config
from tradingagents.agents.utils.memory_db_helper import MemoryDBHelper
from tradingagents.agents.utils.agentstate.agent_states import AgentState
from tradingagents.core.data_adapter import DataAdapter
from tradingagents.agents.market_open.signal_resolver import resolve_signal
from tradingagents.agents.utils.json_parser import extract_json_from_text
from tradingagents.core.portfolio_simulator import PortfolioSimulator
from tradingagents.agents.analysts.market_analyst.agent import create_market_analyst
from tradingagents.agents.analysts.news_analyst.agent import create_news_analyst
from tradingagents.agents.analysts.fundamentals_analyst.agent import create_fundamentals_analyst
from tradingagents.agents.analysts.social_media_analyst.agent import create_social_media_analyst
from tradingagents.graph.node_dump import (
    save_full_state_snapshot,
    save_node_output,
    stream_graph_updates_with_dump,
)


class DatabaseMemory:
    """
    从 memory.db 的 cycle_reflections 注入「周期反思」式记忆（供图中需要 memory 的节点使用）。

    - 仅查询 **weekly** 周期；若表为空或无匹配 symbol，get_memories 返回 []，不影响主流程。
    - 与 analyst_reports / analyst_summaries 无关；后者由 Summary 节点经 MemoryDBHelper 读取。
    """

    def __init__(self, db_path: str, symbol: str, limit: int = 5):
        self.db_helper = MemoryDBHelper(db_path)
        self.symbol = symbol
        self.limit = limit

    def get_memories(self, current_situation: str, n_matches: int = 3) -> List[Dict[str, Any]]:
        try:
            reflections = self.db_helper.query_cycle_reflections_by_symbol(
                symbol=self.symbol,
                cycle_type="weekly",
                limit=max(self.limit, n_matches),
            )
            if not reflections:
                return []
            memories = []
            for r in reflections[:n_matches]:
                parts = []
                if r.get("key_insights"):
                    parts.append(f"关键洞察：{r['key_insights']}")
                if r.get("error_patterns"):
                    parts.append(f"错误模式：{r['error_patterns']}")
                if r.get("success_patterns"):
                    parts.append(f"成功模式：{r['success_patterns']}")
                if r.get("strategy_conditions"):
                    parts.append(f"策略适用条件：{r['strategy_conditions']}")
                recommendation = "\n".join(parts) if parts else "无结构化反思内容。"
                memories.append({
                    "matched_situation": f"周期 {r.get('cycle_start_date', '')} ~ {r.get('cycle_end_date', '')}",
                    "recommendation": recommendation,
                    "similarity_score": 0.8,
                })
            return memories
        except Exception as e:
            print(f"[WARN] 从 cycle_reflections 读取记忆失败: {e}")
            return []

    def close(self) -> None:
        self.db_helper.close()


def get_trading_dates(start_date: str, end_date: str, data_adapter: DataAdapter) -> List[str]:
    """获取交易日历"""
    df = data_adapter.load_stock_data_until("SPY", end_date, start_date=start_date)
    if df is None or len(df) == 0:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        dates = []
        current = start
        while current <= end:
            if current.weekday() < 5:
                dates.append(current.strftime("%Y-%m-%d"))
            current += timedelta(days=1)
        return dates
    trading_dates = [
        date.strftime("%Y-%m-%d")
        for date in df.index
        if start_date <= date.strftime("%Y-%m-%d") <= end_date
    ]
    return sorted(trading_dates)


def _validate_signal(signal: Dict[str, Any]) -> Dict[str, Any]:
    """对解析后的信号做最小约束，避免无效字段进入回测。"""
    action = str(signal.get("action", "HOLD")).upper()
    if action not in {"BUY", "SELL", "HOLD"}:
        action = "HOLD"

    try:
        target_pct = float(signal.get("target_pct", 0.0))
    except Exception:
        target_pct = 0.0
    target_pct = max(0.0, min(1.0, target_pct))

    entry_type = str(signal.get("entry_type", "MKT_OPEN")).upper()
    if entry_type not in {"MKT_OPEN", "LIMIT", "STOP"}:
        entry_type = "MKT_OPEN"

    entry_price = signal.get("entry_price")
    try:
        entry_price = float(entry_price) if entry_price is not None else None
    except Exception:
        entry_price = None

    # LIMIT/STOP 必须有有效价格，否则降级为 MKT_OPEN
    if entry_type in {"LIMIT", "STOP"} and (entry_price is None or entry_price <= 0):
        entry_type = "MKT_OPEN"
        entry_price = None

    normalized = dict(signal)
    normalized["action"] = action
    normalized["target_pct"] = 0.0 if action == "SELL" else target_pct
    normalized["entry_type"] = entry_type
    normalized["entry_price"] = entry_price
    return normalized


def extract_rating_record(
    final_state: Dict[str, Any],
    trade_date: str,
    symbol: str,
) -> Dict[str, Any]:
    """
    方案 2a：完整跑图后仅抽取评级相关字段（不生成可执行信号）。
    """
    rs = final_state.get("research_summary")
    rp = ""
    if isinstance(rs, dict):
        rp = (rs.get("investment_plan") or "").strip()
    rj = extract_json_from_text(rp) if rp else None

    risk = final_state.get("risk_summary")
    fd = ""
    if isinstance(risk, dict):
        fd = (risk.get("final_trade_decision") or "").strip()
    kj = extract_json_from_text(fd) if fd else None

    return {
        "date": trade_date,
        "symbol": symbol,
        "export_mode": "rating",
        "research_decision": (rj or {}).get("decision") if rj else None,
        "fine_rating": (kj or {}).get("fine_rating") if kj else None,
        "final_decision": (kj or {}).get("final_decision") if kj else None,
        "risk_level": (kj or {}).get("risk_level") if kj else None,
    }


def run_signal_export(
    symbol: str,
    start_date: str,
    end_date: str,
    db_path: str = "memory.db",
    output_dir: str = "qc_signals",
    use_db_reports_only: bool = True,
    verbose: bool = False,
    export_mode: str = "backtest",
    simulate_portfolio: bool = False,
    initial_cash: float = 100_000.0,
    trading_dates_override: Optional[List[str]] = None,
    graph_dump_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    导出信号或评级 JSON。

    Args:
        symbol: 股票代码
        start_date / end_date: 日期范围（用于元数据；若传入 trading_dates_override，导出文件内起止日为该列表 min/max）
        db_path: 数据库路径
        output_dir: 输出目录（默认 qc_signals）
        use_db_reports_only: True（默认）时 **不现场跑四个 Analyst 写库**，仅当日内报告已在 analyst_reports 中；
            Pre-Open 全图仍会调用 LLM。False 时对每个交易日现场跑四分析师并 insert_report，再跑全图。
        verbose: 打印 Pre-Open 各节点进度
        export_mode: ``backtest`` 时走 resolve_signal，写 ``signals.json``；``rating`` 为方案 2a，写 ``ratings.json``
        simulate_portfolio: 仅 ``backtest`` 有效；多日循环用轻量模拟仓注入 Trader/Risk，并与 resolve 的 is_holding 对齐
        initial_cash: 模拟仓初始现金
        trading_dates_override: 若提供，仅处理这些交易日（已排序去重），忽略由 start/end 推算的日历
        graph_dump_dir: 若提供，每个交易日写入 ``{graph_dump_dir}/{symbol}_{trade_date}/``：逐节点输出 + ``full_state_snapshot.json``
    """
    if export_mode not in ("backtest", "rating"):
        raise ValueError("export_mode 须为 backtest 或 rating")

    print(f"\n{'='*80}")
    if export_mode == "rating":
        print(f"评级导出（方案 2a：无 Portfolio，不生成可执行信号）")
    else:
        print(f"信号导出（QuantConnect 方案 A）")
    print(f"{'='*80}")
    if trading_dates_override:
        _dmin = min(trading_dates_override)
        _dmax = max(trading_dates_override)
        print(f"股票: {symbol}  交易日: --dates 共 {len(trading_dates_override)} 天 ({_dmin} ~ {_dmax})")
    else:
        print(f"股票: {symbol}  日期: {start_date} ~ {end_date}")
    print(f"数据库: {db_path}  输出: {output_dir}")
    print(
        f"Analyst: {'仅 DB 已有报告（不现场跑四分析师）' if use_db_reports_only else '每个交易日现场跑四分析师写库'}"
    )
    print(f"模式: {export_mode}" + (f"  模拟仓: {'开' if simulate_portfolio else '关'}" if export_mode == "backtest" else ""))

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    _cfg = str(REPO_ROOT / "config" / "config.yaml")
    llm = load_llm_from_config(_cfg)
    data_adapter = DataAdapter(use_cache=True)
    trading_dates_resolver = lambda end, n: data_adapter.get_last_n_trading_days(end, n)
    db_helper = MemoryDBHelper(db_path, trading_dates_resolver=trading_dates_resolver)
    memory = DatabaseMemory(db_path=db_path, symbol=symbol)

    if trading_dates_override:
        trading_dates = sorted(set(trading_dates_override))
    else:
        trading_dates = get_trading_dates(start_date, end_date, data_adapter)
    if not trading_dates:
        print("[ERROR] 未找到交易日")
        memory.close()
        db_helper.close()
        return {}

    print(f"[INFO] 共 {len(trading_dates)} 个交易日")

    all_signals: Dict[str, Dict[str, Any]] = {}
    is_holding = False
    sim: Optional[PortfolioSimulator] = None
    if export_mode == "backtest" and simulate_portfolio:
        sim = PortfolioSimulator(symbol=symbol, initial_cash=float(initial_cash))

    for i, trade_date in enumerate(trading_dates, 1):
        print(f"\n[{i}/{len(trading_dates)}] {trade_date}")

        # Analyst 报告
        analyst_types = ("market", "news", "fundamentals", "sentiment")
        if use_db_reports_only:
            missing = []
            for at in analyst_types:
                c = db_helper.query_today_report(at, symbol, trade_date)
                if not c or not c.strip():
                    missing.append(at)
            if missing:
                print(f"  [WARN] 缺少报告: {missing}，跳过")
                if export_mode == "rating":
                    all_signals[trade_date] = {
                        "date": trade_date,
                        "symbol": symbol,
                        "export_mode": "rating",
                        "research_decision": None,
                        "fine_rating": None,
                        "final_decision": None,
                        "risk_level": None,
                        "reason": f"缺少报告: {missing}",
                    }
                else:
                    all_signals[trade_date] = {"action": "HOLD", "reason": f"缺少报告: {missing}"}
                continue
        else:
            analysts = [
                ("market", create_market_analyst(llm), "market_report"),
                ("news", create_news_analyst(llm), "news_report"),
                ("fundamentals", create_fundamentals_analyst(llm), "fundamentals_report"),
                ("sentiment", create_social_media_analyst(llm), "sentiment_report"),
            ]
            for analyst_type, analyst_func, report_key in analysts:
                try:
                    initial_state: AgentState = {
                        "company_of_interest": symbol,
                        "trade_date": trade_date,
                        report_key: "",
                        "messages": [],
                    }
                    result = analyst_func(initial_state)
                    report_content = result.get(report_key) or ""
                    if not report_content and result.get("messages"):
                        for msg in reversed(result.get("messages", [])):
                            if hasattr(msg, "content") and msg.content:
                                report_content = msg.content
                                break
                    if report_content:
                        db_helper.insert_report(analyst_type, symbol, trade_date, report_content)
                except Exception as e:
                    print(f"  [ERROR] {analyst_type} Analyst 失败: {e}")
                    all_signals[trade_date] = {"action": "HOLD", "reason": str(e)}
                    continue

        # Pre-Open Graph
        try:
            graph = create_trading_graph(llm, memory, db_helper)
            mark_price = data_adapter.get_price(symbol, trade_date, "close")
            cp: Optional[Dict[str, Any]] = None
            ps: Optional[Dict[str, Any]] = None
            if export_mode == "backtest" and sim is not None:
                cp, ps = sim.to_agent_fields(trade_date, mark_price)
                is_holding = sim.is_holding(mark_price)
            elif export_mode == "rating":
                cp, ps = None, None

            initial_state: AgentState = {
                "company_of_interest": symbol,
                "trade_date": trade_date,
                "trading_session": "pre_open",
                "messages": [],
                "current_position": cp,
                "portfolio_state": ps,
            }
            final_state = None
            day_dump: Optional[Path] = None
            if graph_dump_dir:
                day_dump = Path(graph_dump_dir) / f"{symbol}_{trade_date}"
                day_dump.mkdir(parents=True, exist_ok=True)

            final_state = stream_graph_updates_with_dump(
                graph,
                initial_state,
                dump_dir=day_dump,
                verbose=verbose,
                log_prefix="Pre-Open",
            )

            if day_dump is not None and final_state:
                save_full_state_snapshot(final_state, day_dump / "full_state_snapshot.json")
                save_node_output("final_state", final_state, day_dump)
                print(f"  [DUMP] Pre-Open 输出已写入 {day_dump.resolve()}")

            if not final_state:
                all_signals[trade_date] = {"action": "HOLD", "reason": "Pre-Open 未返回状态"}
                continue

            # 合并 pre_open 到 state
            final_state["risk_summary"] = final_state.get("risk_summary")
            final_state["trader_investment_plan"] = final_state.get("trader_investment_plan")

            if export_mode == "rating":
                rec = extract_rating_record(final_state, trade_date, symbol)
                all_signals[trade_date] = rec
                rd = rec.get("research_decision") or "?"
                fd = rec.get("final_decision") or "?"
                fr = rec.get("fine_rating") or "-"
                print(f"  [OK] rating research={rd} risk={fd} fine={fr}")
                continue

            # 可执行信号（backtest）
            signal = resolve_signal(final_state, is_holding, data_adapter)
            signal = _validate_signal(signal)
            signal["date"] = trade_date
            signal["symbol"] = symbol
            all_signals[trade_date] = signal

            if sim is not None:
                ed = signal.get("execution_date")
                if ed:
                    ep = data_adapter.get_price(symbol, str(ed), "open")
                    sim.apply_fill(
                        str(signal.get("action", "HOLD")),
                        float(signal.get("target_pct") or 0.0),
                        ep,
                    )
                    if signal.get("action") == "BUY":
                        sim.set_entry_date_after_buy(str(ed))
            else:
                if signal.get("action") == "BUY":
                    is_holding = True
                elif signal.get("action") == "SELL":
                    is_holding = False

            print(f"  [OK] {signal.get('action', 'HOLD')} - {signal.get('reason', '')[:50]}")

        except Exception as e:
            print(f"  [ERROR] {e}")
            import traceback
            traceback.print_exc()
            if export_mode == "rating":
                all_signals[trade_date] = {
                    "date": trade_date,
                    "symbol": symbol,
                    "export_mode": "rating",
                    "research_decision": None,
                    "fine_rating": None,
                    "final_decision": None,
                    "risk_level": None,
                    "reason": str(e),
                }
            else:
                all_signals[trade_date] = {"action": "HOLD", "reason": str(e), "date": trade_date, "symbol": symbol}

    meta_start = trading_dates[0]
    meta_end = trading_dates[-1]

    if export_mode == "rating":
        merged = {
            "symbol": symbol,
            "export_mode": "rating",
            "start_date": meta_start,
            "end_date": meta_end,
            "by_date": all_signals,
        }
        out_file = output_path / "ratings.json"
    else:
        by_execution_date = {}
        for ad, sig in all_signals.items():
            ed = sig.get("execution_date")
            if ed:
                by_execution_date[str(ed)] = sig

        merged = {
            "symbol": symbol,
            "export_mode": "backtest",
            "start_date": meta_start,
            "end_date": meta_end,
            "signals": all_signals,
            "by_execution_date": by_execution_date,
        }
        out_file = output_path / "signals.json"

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n[OK] 已写入 {out_file.absolute()}")

    memory.close()
    db_helper.close()

    return merged


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(
        description="导出 QuantConnect 信号（Pre-Open 全图 + resolve_signal / 评级模式）"
    )
    parser.add_argument("--symbol", type=str, default="NVDA")
    parser.add_argument("--start", type=str, default="2025-01-01")
    parser.add_argument("--end", type=str, default="2025-03-01")
    parser.add_argument(
        "--dates",
        type=str,
        default=None,
        metavar="D1,D2,...",
        help="逗号分隔交易日 (YYYY-MM-DD)；指定后仅处理这些日期，不再按 --start/--end 向 SPY 推算日历",
    )
    parser.add_argument("--db", type=str, default="memory.db")
    parser.add_argument("--output", type=str, default="qc_signals")
    parser.add_argument(
        "--use-db-reports-only",
        action="store_true",
        default=True,
        help="默认开启：不现场跑四分析师，要求 analyst_reports 已有当日四类报告；Pre-Open 仍调用 LLM",
    )
    parser.add_argument(
        "--no-db-reports-only",
        action="store_false",
        dest="use_db_reports_only",
        help="关闭上一项：每个交易日现场调用四分析师写库后再跑 Pre-Open",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument(
        "--export-mode",
        choices=("backtest", "rating"),
        default="backtest",
        help="backtest: resolve_signal + signals.json；rating: 方案2a，仅 ratings.json",
    )
    parser.add_argument(
        "--simulate-portfolio",
        action="store_true",
        help="backtest 模式下用轻量模拟仓注入 current_position/portfolio_state（多日）",
    )
    parser.add_argument("--initial-cash", type=float, default=100_000.0, help="模拟仓初始现金")
    parser.add_argument(
        "--graph-dump",
        type=str,
        default=None,
        metavar="DIR",
        help="将每日 Pre-Open 逐节点输出与 full_state_snapshot.json 写入 DIR/{symbol}_{trade_date}/",
    )
    args = parser.parse_args()

    dates_override = None
    if args.dates:
        dates_override = sorted({d.strip() for d in args.dates.split(",") if d.strip()})
        if not dates_override:
            parser.error("--dates 解析后为空，请传入逗号分隔的 YYYY-MM-DD")

    run_signal_export(
        symbol=args.symbol,
        start_date=args.start,
        end_date=args.end,
        db_path=args.db,
        output_dir=args.output,
        use_db_reports_only=args.use_db_reports_only,
        verbose=args.verbose,
        export_mode=args.export_mode,
        simulate_portfolio=args.simulate_portfolio,
        initial_cash=args.initial_cash,
        trading_dates_override=dates_override,
        graph_dump_dir=args.graph_dump,
    )


if __name__ == "__main__":
    main()
