# -*- coding: utf-8 -*-
"""Pre-Open 图调试落盘：逐节点 JSON/TXT + 上游式 full_state 白名单快照。"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

_RE_STEM_SAFE = re.compile(r"[^\w\-.]+")


def dump_file_stem(step: int, namespace: Tuple[str, ...], node_name: str) -> str:
    """生成唯一、安全的落盘文件名主干（不含扩展名）。"""

    def _san(s: str) -> str:
        t = _RE_STEM_SAFE.sub("_", s).strip("_")
        return t or "x"

    ns_part = "__".join(_san(p) for p in namespace) if namespace else "root"
    return f"step_{step:04d}__{ns_part}__{_san(node_name)}"


def stream_graph_updates_with_dump(
    graph: Any,
    initial_state: Dict[str, Any],
    *,
    dump_dir: Optional[Path] = None,
    verbose: bool = False,
    log_prefix: str = "Pre-Open",
    stream_config: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    单次执行编译后的 LangGraph：可选落盘每一步（含子图内部节点）。

    - ``dump_dir`` 非空时：``stream_mode=["updates","values"]`` + ``subgraphs=True``，
      每个 updates 写入 ``step_NNNN__{namespace}__{node}_output.json``。
    - ``final_state`` 仅取根图（``namespace == ()``）的 ``values`` 事件。
    """
    final_state: Optional[Dict[str, Any]] = None
    _cfg = dict(stream_config) if stream_config else None
    if dump_dir is not None:
        dump_dir.mkdir(parents=True, exist_ok=True)
        dump_seq = 0
        for chunk in graph.stream(
            initial_state,
            config=_cfg,
            stream_mode=["updates", "values"],
            subgraphs=True,
        ):
            if not (isinstance(chunk, tuple) and len(chunk) == 3):
                continue
            ns, mode, data = chunk[0], chunk[1], chunk[2]
            if mode == "updates" and isinstance(data, dict):
                for node_name, node_state in data.items():
                    dump_seq += 1
                    stem = dump_file_stem(dump_seq, ns, node_name)
                    if verbose:
                        loc = "root" if not ns else "/".join(ns)
                        print(f"  [{log_prefix}] 完成: {loc} :: {node_name}")
                    save_node_output(node_name, node_state, dump_dir, file_stem=stem)
            elif mode == "values" and len(ns) == 0:
                final_state = data
        return final_state

    if verbose:
        for chunk in graph.stream(
            initial_state,
            config=_cfg,
            stream_mode=["updates", "values"],
            subgraphs=False,
        ):
            if isinstance(chunk, tuple) and len(chunk) == 2:
                mode, data = chunk[0], chunk[1]
                if mode == "updates" and isinstance(data, dict):
                    for node_name in data:
                        print(f"  [{log_prefix}] 完成: {node_name}")
                elif mode == "values":
                    final_state = data
        return final_state

    for state in graph.stream(initial_state, config=_cfg, stream_mode="values"):
        final_state = state
    return final_state


def save_node_output(
    node_name: str,
    state: Dict[str, Any],
    output_dir: Path,
    *,
    file_stem: Optional[str] = None,
) -> None:
    """
    保存单个 LangGraph 节点返回的 state 片段：{stem}_output.json / .txt

    Args:
        file_stem: 若提供则用作文件名主干，否则使用 ``node_name``。
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = file_stem if file_stem else node_name

    json_file = output_dir / f"{stem}_output.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2, default=str)

    txt_file = output_dir / f"{stem}_output.txt"
    with open(txt_file, "w", encoding="utf-8") as f:
        f.write(f"节点: {node_name}\n")
        f.write(f"时间: {date.today().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 80 + "\n\n")

        if "messages" in state:
            messages = state["messages"]
            if messages:
                last_msg = messages[-1]
                if hasattr(last_msg, "content"):
                    f.write("最后一条消息:\n")
                    f.write(str(last_msg.content) + "\n\n")

        if state.get("enabled_analysts"):
            f.write(f"enabled_analysts: {state.get('enabled_analysts')}\n\n")

        if state.get("analyst_summaries"):
            f.write("analyst_summaries:\n")
            f.write(json.dumps(state["analyst_summaries"], ensure_ascii=False, indent=2, default=str) + "\n\n")

        for key in [
            "market_analyst_summary",
            "news_analyst_summary",
            "sentiment_analyst_summary",
            "fundamentals_analyst_summary",
        ]:
            if key in state and state[key]:
                summary = state[key]
                f.write(f"\n{key}:\n")
                if isinstance(summary, dict):
                    if "today_report" in summary:
                        f.write(f"今日报告: {str(summary['today_report'])}\n\n")
                    if "history_report" in summary:
                        f.write(f"历史报告: {str(summary['history_report'])}\n\n")

        if "research_summary" in state and state["research_summary"]:
            f.write("\nresearch_summary:\n")
            f.write("=" * 80 + "\n")
            research_summary = state["research_summary"]
            if isinstance(research_summary, dict):
                if "investment_debate_state" in research_summary:
                    debate_state = research_summary["investment_debate_state"]
                    f.write("\ninvestment_debate_state (完整辩论历史):\n")
                    f.write("-" * 80 + "\n")
                    if isinstance(debate_state, dict):
                        for k, v in debate_state.items():
                            f.write(f"\n{k}:\n")
                            f.write("-" * 40 + "\n")
                            if isinstance(v, str):
                                try:
                                    parsed = json.loads(v)
                                    f.write(json.dumps(parsed, ensure_ascii=False, indent=2) + "\n")
                                except Exception:
                                    f.write(str(v) + "\n")
                            else:
                                f.write(str(v) + "\n")
                for k, v in research_summary.items():
                    if k != "investment_debate_state":
                        f.write(f"\n{k}:\n")
                        f.write("-" * 80 + "\n")
                        if isinstance(v, str):
                            try:
                                parsed = json.loads(v)
                                f.write(json.dumps(parsed, ensure_ascii=False, indent=2) + "\n")
                            except Exception:
                                f.write(str(v) + "\n")
                        else:
                            f.write(str(v) + "\n")

        if "risk_summary" in state and state["risk_summary"]:
            f.write("\nrisk_summary (完整风险辩论历史):\n")
            f.write("=" * 80 + "\n")
            risk_summary = state["risk_summary"]
            if isinstance(risk_summary, dict):
                for k, v in risk_summary.items():
                    f.write(f"\n{k}:\n")
                    f.write("-" * 80 + "\n")
                    if isinstance(v, str):
                        try:
                            parsed = json.loads(v)
                            f.write(json.dumps(parsed, ensure_ascii=False, indent=2) + "\n")
                        except Exception:
                            f.write(str(v) + "\n")
                    else:
                        f.write(str(v) + "\n")

        if "trader_investment_plan" in state and state["trader_investment_plan"]:
            f.write("\ntrader_investment_plan:\n")
            f.write("=" * 80 + "\n")
            trader_output = state["trader_investment_plan"]
            if isinstance(trader_output, str):
                try:
                    parsed = json.loads(trader_output)
                    f.write(json.dumps(parsed, ensure_ascii=False, indent=2) + "\n")
                except Exception:
                    f.write(str(trader_output) + "\n")
            else:
                f.write(str(trader_output) + "\n")

        for key in [
            "research_result",
            "investment_plan",
            "final_trade_decision",
            "trading_strategy",
            "trading_strategy_status",
        ]:
            if key in state and state[key]:
                f.write(f"\n{key}:\n")
                f.write("=" * 80 + "\n")
                value = state[key]
                if isinstance(value, str):
                    try:
                        parsed = json.loads(value)
                        f.write(json.dumps(parsed, ensure_ascii=False, indent=2) + "\n")
                    except Exception:
                        f.write(str(value) + "\n")
                else:
                    f.write(str(value) + "\n")


def _subset_invest_debate(st: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(st, dict):
        return None
    keys = (
        "bull_history",
        "bear_history",
        "history",
        "current_response",
        "judge_decision",
        "count",
    )
    return {k: st.get(k) for k in keys}


def _subset_risk_debate(st: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(st, dict):
        return None
    keys = (
        "risky_history",
        "safe_history",
        "neutral_history",
        "history",
        "latest_speaker",
        "current_risky_response",
        "current_safe_response",
        "current_neutral_response",
        "judge_decision",
        "count",
    )
    return {k: st.get(k) for k in keys}


def build_loggable_full_state(final_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    参考上游 TradingAgentsGraph._log_state：从终态抽取白名单字段，便于 diff / 人读。
    键名适配本仓库 AgentState（非上游逐字相同）。
    """
    rs = final_state.get("research_summary")
    research_block: Optional[Dict[str, Any]] = None
    if isinstance(rs, dict):
        ids = rs.get("investment_debate_state")
        research_block = {
            "investment_debate_state": _subset_invest_debate(ids),
            "investment_plan": rs.get("investment_plan"),
            "raw_response": rs.get("raw_response"),
        }

    risk = final_state.get("risk_summary")
    risk_block: Optional[Dict[str, Any]] = None
    if isinstance(risk, dict):
        rds = risk.get("risk_debate_state")
        risk_block = {
            "risk_debate_state": _subset_risk_debate(rds),
            "final_trade_decision": risk.get("final_trade_decision"),
            "raw_response": risk.get("raw_response"),
        }

    return {
        "company_of_interest": final_state.get("company_of_interest"),
        "trade_date": final_state.get("trade_date"),
        "trading_session": final_state.get("trading_session"),
        "enabled_analysts": final_state.get("enabled_analysts"),
        "experiment_id": final_state.get("experiment_id"),
        "analyst_summaries": final_state.get("analyst_summaries"),
        "market_analyst_summary": final_state.get("market_analyst_summary"),
        "news_analyst_summary": final_state.get("news_analyst_summary"),
        "sentiment_analyst_summary": final_state.get("sentiment_analyst_summary"),
        "fundamentals_analyst_summary": final_state.get("fundamentals_analyst_summary"),
        "research_summary": research_block,
        "investment_plan": final_state.get("investment_plan"),
        "trader_investment_plan": final_state.get("trader_investment_plan"),
        "risk_summary": risk_block,
        "final_trade_decision": final_state.get("final_trade_decision"),
        "current_position": final_state.get("current_position"),
        "portfolio_state": final_state.get("portfolio_state"),
    }


def save_full_state_snapshot(final_state: Dict[str, Any], json_path: Path) -> None:
    """写入 full_state_snapshot.json（白名单终态）。"""
    json_path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_loggable_full_state(final_state)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
