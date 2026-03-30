#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
淇″彿瀵煎嚭鑴氭湰锛堟柟妗?A锛欰gent 杈撳嚭淇″彿 鈫?QuantConnect 鎵ц锛?
鍒嗙被锛氭暟鎹瀯寤?/ 绂荤嚎娴嬭瘯锛堣 README锛?- 杩愯 Analyst锛堟垨浠?DB 璇伙級鈫?Pre-Open Graph 鈫?淇″彿瑙ｆ瀽
- 杈撳嚭缁撴瀯鍖栦俊鍙?JSON 鍒?qc_signals/锛屼緵 QuantConnect 绠楁硶璇诲彇鎵ц
- 鏂规 2a锛堝垎鏋愬伐鍏凤級锛歚--export-mode rating` 涓嶆敞鍏?Portfolio銆佷笉璋冪敤 `resolve_signal`锛屼粎鍐欏嚭
  `research_manager.decision` 涓?`risk_manager` 鐨?`fine_rating` / `final_decision` / `risk_level`锛堣 `ratings.json`锛?
浣跨敤娴佺▼锛?1. 纭繚 memory.db 涓湁鎵€闇€鏃ユ湡鐨?analyst_reports锛堝彲鐢?build_analyst_dataset 鏋勫缓锛?2. 鍙€夛細棰勫厛杩愯 run_history_maintainer_batch 鐢熸垚 analyst_summaries
3. 杩愯鏈剼鏈鍑轰俊鍙?4. 灏?qc_signals/ 鐩綍鍐呭澶嶅埗鍒?QuantConnect 椤圭洰锛岃繍琛屽洖娴?
璇存槑锛?- **榛樿 --use-db-reports-only**锛氫笉鐜板満璋冪敤鍥涗釜 Analyst 鍐欏簱锛汸re-Open 鍥撅紙Summary鈫扲esearch鈫扵rader鈫扲isk锛?*浠嶄細澶氭璋冪敤 LLM**銆?- **璁板繂锛圖atabaseMemory锛?*锛氫粎浠?DB 琛?cycle_reflections 璇诲懆鏈熷弽鎬濓紝涓斿綋鍓嶅浐瀹?weekly锛涜嫢鏃犺褰曞垯 get_memories 涓虹┖锛屽睘姝ｅ父銆?- **鎺ㄨ崘**浠ユ鑴氭湰涓恒€屼粠 Summary 璺戝叏鍥惧苟瀵煎嚭銆嶇殑鍞竴 CLI锛涘崟鏃ュ彲鐢?--dates銆?- **浜哄伐璇勫垽 / 璋冭瘯**锛歚--graph-dump DIR` 鍦ㄦ瘡涓氦鏄撴棩鍐欏叆 `DIR/{symbol}_{trade_date}/`锛圠angGraph `subgraphs=True`锛屽瓙鍥惧唴姣忎竴姝ヨ惤鐩樹负 `step_NNNN__{鍛藉悕绌洪棿}__{鑺傜偣}_output.json/.txt`锛屽彟鍚?`full_state_snapshot.json` 涓?`final_state_*`锛夈€?"""

信号导出脚本（方案 A）：Agent 产出信号 -> QuantConnect 执行。

用途：
- 运行 Analyst（或直接复用 DB 报告）-> Pre-Open Graph -> 信号解析。
- 输出结构化 JSON 到 qc_signals/（或指定输出目录），供 QuantConnect 算法读取执行。
- 在 `--export-mode rating` 下仅导出分析评级，不注入 Portfolio，也不调用 `resolve_signal`。

使用流程：
1. 确保 memory.db 中存在目标日期的 analyst_reports（可用 build_analyst_dataset 预构建）。
2. 可选：先运行 run_history_maintainer_batch 生成 analyst_summaries。
3. 运行本脚本导出 signals.json 或 ratings.json。
4. 将输出目录内容复制到 QuantConnect 项目后执行回测。

说明：
- 默认 `--use-db-reports-only`：不现场运行四个 Analyst，仅使用 DB 报告；Pre-Open 图仍会调用 LLM。
- `DatabaseMemory` 仅从 `cycle_reflections` 读取 weekly 周期反思；无记录时返回空列表，属正常行为。
- 推荐使用本脚本作为“从 Summary 跑全图并导出”的统一 CLI；单日可用 `--dates`。
- `--graph-dump DIR` 会按交易日写入 `DIR/{experiment_id}/{symbol}/{trade_date}/`，包含子图节点输出与完整状态快照。
"""

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
DEFAULT_ENABLED_ANALYSTS = ("market", "news", "sentiment", "fundamentals")


def _get_runtime_dependencies() -> Dict[str, Any]:
    from tradingagents.graph.trading_graph import create_trading_graph
    from tradingagents.graph.utils import load_llm_from_config
    from tradingagents.agents.utils.memory_db_helper import MemoryDBHelper
    from tradingagents.core.data_adapter import DataAdapter
    from tradingagents.dataflows.export.signal_resolver import resolve_signal
    from tradingagents.agents.utils.json_parser import extract_json_from_text
    from tradingagents.core.portfolio_simulator import PortfolioSimulator
    from tradingagents.graph.node_dump import (
        save_full_state_snapshot,
        save_node_output,
        stream_graph_updates_with_dump,
    )

    return {
        "create_trading_graph": create_trading_graph,
        "load_llm_from_config": load_llm_from_config,
        "MemoryDBHelper": MemoryDBHelper,
        "DataAdapter": DataAdapter,
        "resolve_signal": resolve_signal,
        "extract_json_from_text": extract_json_from_text,
        "PortfolioSimulator": PortfolioSimulator,
        "save_full_state_snapshot": save_full_state_snapshot,
        "save_node_output": save_node_output,
        "stream_graph_updates_with_dump": stream_graph_updates_with_dump,
    }


def _get_analyst_factories() -> Dict[str, Any]:
    from tradingagents.agents.analysts.market_analyst.agent import create_market_analyst
    from tradingagents.agents.analysts.news_analyst.agent import create_news_analyst
    from tradingagents.agents.analysts.fundamentals_analyst.agent import create_fundamentals_analyst
    from tradingagents.agents.analysts.social_media_analyst.agent import create_social_media_analyst

    return {
        "market": (create_market_analyst, "market_report"),
        "news": (create_news_analyst, "news_report"),
        "fundamentals": (create_fundamentals_analyst, "fundamentals_report"),
        "sentiment": (create_social_media_analyst, "sentiment_report"),
    }


def _normalize_enabled_analysts(enabled_analysts: Optional[List[str]]) -> List[str]:
    analyst_factories = _get_analyst_factories()
    requested = enabled_analysts or list(DEFAULT_ENABLED_ANALYSTS)
    normalized: List[str] = []
    for analyst_name in requested:
        name = str(analyst_name).strip().lower()
        if name and name in analyst_factories and name not in normalized:
            normalized.append(name)
    return normalized or list(DEFAULT_ENABLED_ANALYSTS)


def _derive_experiment_id(enabled_analysts: List[str], experiment_id: Optional[str]) -> str:
    if experiment_id and str(experiment_id).strip():
        return str(experiment_id).strip()
    enabled = _normalize_enabled_analysts(enabled_analysts)
    if enabled == list(DEFAULT_ENABLED_ANALYSTS):
        return "all_analysts"
    return "_".join(enabled)


def _resolve_output_file(output_dir: str, experiment_id: str, symbol: str, filename: str) -> Path:
    base = Path(output_dir)
    if base.name == "qc_signals":
        base.mkdir(parents=True, exist_ok=True)
        return base / filename
    target_dir = base / experiment_id / symbol
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / filename


def _extract_report_sections(final_state: Dict[str, Any]) -> Dict[str, Any]:
    research_summary = final_state.get("research_summary") or {}
    risk_summary = final_state.get("risk_summary") or {}
    return {
        "analyst_summaries": final_state.get("analyst_summaries") or {},
        "research_summary": research_summary,
        "research_investment_plan": research_summary.get("investment_plan"),
        "trader_investment_plan": final_state.get("trader_investment_plan"),
        "risk_summary": risk_summary,
        "risk_final_trade_decision": risk_summary.get("final_trade_decision"),
    }


def _write_report_artifacts(
    report_output_root: str,
    experiment_id: str,
    symbol: str,
    trade_date: str,
    enabled_analysts: List[str],
    final_state: Dict[str, Any],
    export_mode: str,
    execution_payload: Optional[Dict[str, Any]] = None,
) -> None:
    base_dir = Path(report_output_root) / experiment_id / symbol / trade_date
    base_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "symbol": symbol,
        "trade_date": trade_date,
        "experiment_id": experiment_id,
        "enabled_analysts": enabled_analysts,
        "export_mode": export_mode,
        **_extract_report_sections(final_state),
        "execution_payload": execution_payload,
    }

    with open(base_dir / "report.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=str)

    text = dedent(
        f"""
        Symbol: {symbol}
        Trade Date: {trade_date}
        Experiment ID: {experiment_id}
        Enabled Analysts: {", ".join(enabled_analysts)}
        Export Mode: {export_mode}

        [Research Investment Plan]
        {payload.get("research_investment_plan") or ""}

        [Trader Investment Plan]
        {payload.get("trader_investment_plan") or ""}

        [Risk Final Trade Decision]
        {payload.get("risk_final_trade_decision") or ""}

        [Execution Payload]
        {json.dumps(execution_payload or {}, ensure_ascii=False, indent=2, default=str)}
        """
    ).strip()

    with open(base_dir / "report.txt", "w", encoding="utf-8") as f:
        f.write(text + "\n")


class DatabaseMemory:
    """
    从 memory.db 的 cycle_reflections 注入“周期反思”记忆，供图中 memory 相关节点使用。
    - 仅查询 weekly 周期；若无匹配 symbol 的记录，get_memories 返回 []。
    - 与 analyst_reports / analyst_summaries 解耦，后者由 Summary 节点自行读取。
    """

    def __init__(self, db_path: str, symbol: str, limit: int = 5):
        MemoryDBHelper = _get_runtime_dependencies()["MemoryDBHelper"]
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
                    parts.append(f"Key insights: {r['key_insights']}")
                if r.get("error_patterns"):
                    parts.append(f"Error patterns: {r['error_patterns']}")
                if r.get("success_patterns"):
                    parts.append(f"Success patterns: {r['success_patterns']}")
                if r.get("strategy_conditions"):
                    parts.append(f"Strategy conditions: {r['strategy_conditions']}")
                recommendation = "\n".join(parts) if parts else "No structured reflection available."
                memories.append({
                    "matched_situation": f"Cycle {r.get('cycle_start_date', '')} ~ {r.get('cycle_end_date', '')}",
                    "recommendation": recommendation,
                    "similarity_score": 0.8,
                })
            return memories
        except Exception as e:
            print(f"[WARN] Failed to load reflection memory from cycle_reflections: {e}")
            return []

    def close(self) -> None:
        self.db_helper.close()


def get_trading_dates(start_date: str, end_date: str, data_adapter: DataAdapter) -> List[str]:
    """获取交易日历。"""
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
    """Apply minimal validation to a resolved signal before exporting it."""
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
    """Extract analysis-only rating fields after a full graph run."""

    rs = final_state.get("research_summary")
    rp = ""
    if isinstance(rs, dict):
        rp = (rs.get("investment_plan") or "").strip()
    extract_json_from_text = _get_runtime_dependencies()["extract_json_from_text"]
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
    enabled_analysts: Optional[List[str]] = None,
    experiment_id: Optional[str] = None,
    report_output_root: Optional[str] = None,
    max_research_debate_rounds: Optional[int] = None,
    max_risk_debate_rounds: Optional[int] = None,
) -> Dict[str, Any]:
    """Export ratings or executable backtest signals from prepared analyst data."""

    if export_mode not in ("backtest", "rating"):
        raise ValueError("export_mode must be either backtest or rating")

    print(f"\n{'='*80}")
    if export_mode == "rating":
        print("Rating export mode (analysis only, no executable signal)")
    else:
        print("Signal export mode (QuantConnect backtest)")
    print(f"{'='*80}")







    if trading_dates_override:
        _dmin = min(trading_dates_override)
        _dmax = max(trading_dates_override)
        print(f"Symbol: {symbol}  Dates from --dates: {len(trading_dates_override)} ({_dmin} ~ {_dmax})")
    else:
        print(f"Symbol: {symbol}  Date range: {start_date} ~ {end_date}")
    print(f"Database: {db_path}  Output: {output_dir}")
    print("Analyst source: DB reports only" if use_db_reports_only else "Analyst source: run analysts on demand")


    print(f"Mode: {export_mode}" + (f"  Simulate portfolio: {simulate_portfolio}" if export_mode == "backtest" else ""))

    enabled_analysts = _normalize_enabled_analysts(enabled_analysts)
    experiment_id = _derive_experiment_id(enabled_analysts, experiment_id)
    print(f"Enabled analysts: {enabled_analysts}")
    print(f"Experiment ID: {experiment_id}")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    runtime = _get_runtime_dependencies()
    load_llm_from_config = runtime["load_llm_from_config"]
    DataAdapter = runtime["DataAdapter"]
    MemoryDBHelper = runtime["MemoryDBHelper"]
    PortfolioSimulator = runtime["PortfolioSimulator"]
    create_trading_graph = runtime["create_trading_graph"]
    resolve_signal = runtime["resolve_signal"]
    save_full_state_snapshot = runtime["save_full_state_snapshot"]
    save_node_output = runtime["save_node_output"]
    stream_graph_updates_with_dump = runtime["stream_graph_updates_with_dump"]
    analyst_factories = _get_analyst_factories()

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
        print("[ERROR] No trading dates found")
        memory.close()
        db_helper.close()
        return {}

    print(f"[INFO] Total trading dates: {len(trading_dates)}")

    all_signals: Dict[str, Dict[str, Any]] = {}
    is_holding = False
    sim: Optional[PortfolioSimulator] = None
    if export_mode == "backtest" and simulate_portfolio:
        sim = PortfolioSimulator(symbol=symbol, initial_cash=float(initial_cash))

    for i, trade_date in enumerate(trading_dates, 1):
        print(f"\n[{i}/{len(trading_dates)}] {trade_date}")

        # Analyst 报告
        analyst_types = enabled_analysts
        if use_db_reports_only:
            missing = []
            for at in analyst_types:
                c = db_helper.query_today_report(at, symbol, trade_date)
                if not c or not c.strip():
                    missing.append(at)
            if missing:
                print(f"  [WARN] Missing reports: {missing}; skipping")
                if export_mode == "rating":
                    all_signals[trade_date] = {
                        "date": trade_date,
                        "symbol": symbol,
                        "export_mode": "rating",
                        "research_decision": None,
                        "fine_rating": None,
                        "final_decision": None,
                        "risk_level": None,
                        "reason": f"Missing reports: {missing}",
                    }
                else:
                    all_signals[trade_date] = {"action": "HOLD", "reason": f"Missing reports: {missing}"}
                continue
        else:
            for analyst_type in analyst_types:
                analyst_factory, report_key = analyst_factories[analyst_type]
                try:
                    initial_state: AgentState = {
                        "company_of_interest": symbol,
                        "trade_date": trade_date,
                        report_key: "",
                        "messages": [],
                    }
                    result = analyst_factory(llm)(initial_state)
                    report_content = result.get(report_key) or ""
                    if not report_content and result.get("messages"):
                        for msg in reversed(result.get("messages", [])):
                            if hasattr(msg, "content") and msg.content:
                                report_content = msg.content
                                break
                    if report_content:
                        db_helper.insert_report(analyst_type, symbol, trade_date, report_content)
                except Exception as e:
                    print(f"  [ERROR] {analyst_type} analyst failed: {e}")
                    all_signals[trade_date] = {"action": "HOLD", "reason": str(e)}
                    continue

        # Pre-Open Graph
        try:
            graph = create_trading_graph(
                llm,
                memory,
                db_helper,
                max_research_debate_rounds=max_research_debate_rounds,
                max_risk_debate_rounds=max_risk_debate_rounds,
            )
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
                "enabled_analysts": enabled_analysts,
                "experiment_id": experiment_id,
            }
            final_state = None
            day_dump: Optional[Path] = None
            if graph_dump_dir:
                day_dump = Path(graph_dump_dir) / experiment_id / symbol / trade_date
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
                print(f"  [DUMP] Pre-Open outputs written to {day_dump.resolve()}")

            if not final_state:
                all_signals[trade_date] = {"action": "HOLD", "reason": "Pre-Open graph returned no state"}
                continue

            # 合并 pre_open 阶段状态
            final_state["risk_summary"] = final_state.get("risk_summary")
            final_state["trader_investment_plan"] = final_state.get("trader_investment_plan")

            if export_mode == "rating":
                rec = extract_rating_record(final_state, trade_date, symbol)
                rec["experiment_id"] = experiment_id
                rec["enabled_analysts"] = enabled_analysts
                all_signals[trade_date] = rec
                if report_output_root:
                    _write_report_artifacts(
                        report_output_root=report_output_root,
                        experiment_id=experiment_id,
                        symbol=symbol,
                        trade_date=trade_date,
                        enabled_analysts=enabled_analysts,
                        final_state=final_state,
                        export_mode=export_mode,
                        execution_payload=rec,
                    )
                rd = rec.get("research_decision") or "?"
                fd = rec.get("final_decision") or "?"
                fr = rec.get("fine_rating") or "-"
                print(f"  [OK] rating research={rd} risk={fd} fine={fr}")
                continue

            signal = resolve_signal(final_state, is_holding, data_adapter)
            signal = _validate_signal(signal)
            signal["date"] = trade_date
            signal["symbol"] = symbol
            signal["experiment_id"] = experiment_id
            signal["enabled_analysts"] = enabled_analysts
            all_signals[trade_date] = signal
            if report_output_root:
                _write_report_artifacts(
                    report_output_root=report_output_root,
                    experiment_id=experiment_id,
                    symbol=symbol,
                    trade_date=trade_date,
                    enabled_analysts=enabled_analysts,
                    final_state=final_state,
                    export_mode=export_mode,
                    execution_payload=signal,
                )

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
            "experiment_id": experiment_id,
            "enabled_analysts": enabled_analysts,
            "by_date": all_signals,
        }
        out_file = _resolve_output_file(output_dir, experiment_id, symbol, "ratings.json")
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
            "experiment_id": experiment_id,
            "enabled_analysts": enabled_analysts,
            "signals": all_signals,
            "by_execution_date": by_execution_date,
        }
        out_file = _resolve_output_file(output_dir, experiment_id, symbol, "signals.json")

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n[OK] Wrote output to {out_file.absolute()}")

    memory.close()
    db_helper.close()

    return merged


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(
        description="Export QuantConnect ratings or backtest signals from the pre-open graph.",
    )
    parser.add_argument("--symbol", type=str, default="NVDA")
    parser.add_argument("--start", type=str, default="2025-01-01")
    parser.add_argument("--end", type=str, default="2025-03-01")
    parser.add_argument(
        "--dates",
        type=str,
        default=None,
        metavar="D1,D2,...",
        help="Comma-separated trade dates in YYYY-MM-DD format. When set, --start/--end are ignored for date selection.",
    )
    parser.add_argument("--db", type=str, default="storage/db/memory.db")
    parser.add_argument("--output", type=str, default="storage/signals")
    parser.add_argument(
        "--enabled-analysts",
        type=str,
        default=",".join(DEFAULT_ENABLED_ANALYSTS),
        help="Comma-separated analyst list, e.g. market,news",
    )
    parser.add_argument("--experiment-id", type=str, default=None)
    parser.add_argument("--report-output-root", type=str, default=None)
    parser.add_argument("--max-research-debate-rounds", type=int, default=None)
    parser.add_argument("--max-risk-debate-rounds", type=int, default=None)
    parser.add_argument(
        "--use-db-reports-only",
        action="store_true",
        default=True,
        help="Default behavior: do not run analysts on demand; require reports to already exist in analyst_reports.",
    )
    parser.add_argument(
        "--no-db-reports-only",
        action="store_false",
        dest="use_db_reports_only",
        help="Disable the previous option and run analysts on demand before the pre-open graph.",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument(
        "--export-mode",
        choices=("backtest", "rating"),
        default="backtest",
        help="backtest writes signals.json; rating writes ratings.json only",
    )
    parser.add_argument(
        "--simulate-portfolio",
        action="store_true",
        help="Inject simulated portfolio state in backtest mode for multi-day runs",
    )
    parser.add_argument("--initial-cash", type=float, default=100_000.0, help="Initial cash for portfolio simulation")
    parser.add_argument(
        "--graph-dump",
        type=str,
        default=None,
        metavar="DIR",
        help="Write per-day graph outputs and full_state_snapshot.json under DIR/{experiment_id}/{symbol}/{trade_date}/",
    )
    args = parser.parse_args()

    dates_override = None
    enabled_analysts = [item.strip() for item in args.enabled_analysts.split(",") if item.strip()]
    if args.dates:
        dates_override = sorted({d.strip() for d in args.dates.split(",") if d.strip()})
        if not dates_override:
            parser.error("--dates resolved to an empty list; please provide comma-separated YYYY-MM-DD values")

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
        enabled_analysts=enabled_analysts,
        experiment_id=args.experiment_id,
        report_output_root=args.report_output_root,
        max_research_debate_rounds=args.max_research_debate_rounds,
        max_risk_debate_rounds=args.max_risk_debate_rounds,
    )


if __name__ == "__main__":
    main()

