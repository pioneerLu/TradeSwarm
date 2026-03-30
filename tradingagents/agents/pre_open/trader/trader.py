from __future__ import annotations

from typing import Any, Callable, Dict

from langchain_core.language_models import BaseChatModel

from tradingagents.agents.utils.agentstate.agent_states import AgentState
from tradingagents.agents.utils.prompt_loader import load_prompt_template
from tradingagents.agents.utils.state_helpers import build_curr_situation_from_summaries, get_prompt_context_from_summaries


def create_trader(llm: BaseChatModel, memory: Any) -> Callable[[AgentState], Dict[str, Any]]:
    def trader_node(state: AgentState) -> Dict[str, Any]:
        company_name = state["company_of_interest"]
        research_summary: Dict[str, Any] | None = state.get("research_summary")  # type: ignore[assignment]
        investment_plan = (
            research_summary.get("investment_plan", "")  # type: ignore[union-attr]
            if research_summary is not None
            else state.get("investment_plan", "")
        )

        curr_situation = build_curr_situation_from_summaries(state, include_history=True, max_length=4000)
        past_memories = memory.get_memories(curr_situation, n_matches=2)
        if past_memories:
            past_memory_str = "\n\n".join(rec["recommendation"] for rec in past_memories)
        else:
            past_memory_str = "No past memories found."

        summary_context = get_prompt_context_from_summaries(state)
        system_prompt = load_prompt_template(
            agent_type="trader",
            agent_name="trader",
            context={
                "past_memory_str": past_memory_str,
                **summary_context,
            },
        )

        current_position = state.get("current_position")
        portfolio_state = state.get("portfolio_state")

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
            portfolio_info = (
                f"\nPortfolio state:\n"
                f"- Total value: ${portfolio_state.get('total_value', 0):,.2f}\n"
                f"- Cash: ${portfolio_state.get('cash', 0):,.2f}\n"
                f"- Positions value: ${portfolio_state.get('positions_value', 0):,.2f}\n"
                f"- Total return: {portfolio_state.get('total_return', 0):.2f}%\n"
            )

        from pathlib import Path
        from jinja2 import Template

        user_prompt_path = Path(__file__).parent / "prompt.j2"
        if user_prompt_path.exists():
            with open(user_prompt_path, "r", encoding="utf-8") as f:
                user_template = Template(f.read())
                user_prompt = user_template.render(
                    company_name=company_name,
                    investment_plan=investment_plan,
                    position_info=position_info,
                    portfolio_info=portfolio_info,
                )
        else:
            user_prompt = (
                f"Create a trading plan for {company_name}.\n\n"
                f"Investment plan:\n{investment_plan}\n"
                f"{position_info}{portfolio_info}"
            )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        result = llm.invoke(messages)
        content: str = getattr(result, "content", str(result))

        return {
            "messages": [result],
            "trader_investment_plan": content,
        }

    return trader_node
