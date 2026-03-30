from __future__ import annotations

from typing import Any, Callable, Dict

from langchain_core.language_models import BaseChatModel

from tradingagents.agents.utils.agentstate.agent_states import AgentState, RiskDebateState, RiskSummary
from tradingagents.agents.utils.prompt_loader import load_prompt_template
from tradingagents.agents.utils.state_helpers import build_curr_situation_from_summaries, get_prompt_context_from_summaries


def create_risk_manager(llm: BaseChatModel, memory: Any) -> Callable[[AgentState], Dict[str, Any]]:
    def risk_manager_node(state: AgentState) -> Dict[str, Any]:
        prev_summary: RiskSummary | None = state.get("risk_summary")  # type: ignore[assignment]
        prev_debate: RiskDebateState = (
            prev_summary.get("risk_debate_state")  # type: ignore[union-attr]
            if prev_summary is not None
            else {
                "risky_history": "",
                "safe_history": "",
                "neutral_history": "",
                "history": "",
                "latest_speaker": "",
                "current_risky_response": "",
                "current_safe_response": "",
                "current_neutral_response": "",
                "judge_decision": "",
                "count": 0,
            }
        )

        history = prev_debate.get("history", "")
        curr_situation = build_curr_situation_from_summaries(state, include_history=True, max_length=4000)
        past_memories = memory.get_memories(curr_situation, n_matches=2)
        past_memory_str = ""
        for rec in past_memories:
            past_memory_str += rec.get("recommendation", "") + "\n\n"

        summary_context = get_prompt_context_from_summaries(state)
        research_summary: Dict[str, Any] | None = state.get("research_summary")  # type: ignore[assignment]
        trader_plan = state.get("trader_investment_plan") or (
            research_summary.get("investment_plan", "")  # type: ignore[union-attr]
            if research_summary is not None
            else state.get("investment_plan", "")
        )

        current_position = state.get("current_position")
        portfolio_state = state.get("portfolio_state")

        position_info = ""
        if current_position:
            shares = current_position.get("shares") or 0.0
            entry_price = current_position.get("entry_price") or 0.0
            entry_date = current_position.get("entry_date") or ""
            current_price = current_position.get("current_price") or 0.0
            pnl = current_position.get("pnl") or 0.0
            pnl_pct = current_position.get("pnl_pct") or 0.0
            sl_raw = current_position.get("stop_loss_price")
            sl_str = f"${sl_raw:.2f}" if sl_raw is not None else "Not set"
            tp_raw = current_position.get("take_profit_price")
            tp_str = f"${tp_raw:.2f}" if tp_raw is not None else "Not set"
            position_info = (
                f"\nCurrent position:\n"
                f"- Shares: {shares:.0f}\n"
                f"- Entry price: ${entry_price:.2f}\n"
                f"- Entry date: {entry_date}\n"
                f"- Current price: ${current_price:.2f}\n"
                f"- PnL: ${pnl:.2f}\n"
                f"- PnL %: {pnl_pct:.2f}%\n"
                f"- Stop loss: {sl_str}\n"
                f"- Take profit: {tp_str}\n"
            )
        else:
            position_info = "\nCurrent position: none\n"

        portfolio_info = ""
        if portfolio_state:
            total_value = portfolio_state.get("total_value") or 0.0
            cash = portfolio_state.get("cash") or 0.0
            positions_value = portfolio_state.get("positions_value") or 0.0
            total_return = portfolio_state.get("total_return") or 0.0
            portfolio_info = (
                f"\nPortfolio state:\n"
                f"- Total value: ${total_value:,.2f}\n"
                f"- Cash: ${cash:,.2f}\n"
                f"- Positions value: ${positions_value:,.2f}\n"
                f"- Total return: {total_return:.2f}%\n"
            )

        prompt = load_prompt_template(
            agent_type="managers",
            agent_name="risk_manager",
            context={
                **summary_context,
                "past_memory_str": past_memory_str,
                "trader_plan": trader_plan,
                "history": history,
                "position_info": position_info,
                "portfolio_info": portfolio_info,
            },
        )

        response = llm.invoke(input=prompt)
        content: str = getattr(response, "content", str(response))

        new_risk_debate_state: RiskDebateState = {
            "judge_decision": content,
            "history": prev_debate.get("history", ""),
            "risky_history": prev_debate.get("risky_history", ""),
            "safe_history": prev_debate.get("safe_history", ""),
            "neutral_history": prev_debate.get("neutral_history", ""),
            "latest_speaker": "Judge",
            "current_risky_response": prev_debate.get("current_risky_response", ""),
            "current_safe_response": prev_debate.get("current_safe_response", ""),
            "current_neutral_response": prev_debate.get("current_neutral_response", ""),
            "count": prev_debate.get("count", 0) + 1,
        }

        new_summary: RiskSummary = {
            "risk_debate_state": new_risk_debate_state,
            "final_trade_decision": content,
            "raw_response": content,
        }
        return {
            "risk_summary": new_summary,
            "final_trade_decision": content,
        }

    return risk_manager_node
