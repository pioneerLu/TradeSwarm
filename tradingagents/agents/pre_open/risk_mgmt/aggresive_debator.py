from __future__ import annotations

from typing import Any, Callable, Dict

from langchain_core.language_models import BaseChatModel

from tradingagents.agents.utils.agentstate.agent_states import AgentState, RiskDebateState, RiskSummary
from tradingagents.agents.utils.prompt_loader import load_prompt_template
from tradingagents.agents.utils.state_helpers import get_prompt_context_from_summaries


def create_risky_debator(llm: BaseChatModel) -> Callable[[AgentState], Dict[str, Any]]:
    def risky_node(state: AgentState) -> dict:
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
        risky_history = prev_debate.get("risky_history", "")
        safe_history = prev_debate.get("safe_history", "")
        neutral_history = prev_debate.get("neutral_history", "")
        current_safe_response = prev_debate.get("current_safe_response", "")
        current_neutral_response = prev_debate.get("current_neutral_response", "")
        count = prev_debate.get("count", 0)

        round_number = (count // 3) + 1
        is_first_round = count < 3
        summary_context = get_prompt_context_from_summaries(state)

        research_summary: Dict[str, Any] | None = state.get("research_summary")  # type: ignore[assignment]
        trader_decision = (
            research_summary.get("investment_plan", "")  # type: ignore[union-attr]
            if research_summary is not None
            else state.get("investment_plan", "") or state.get("trader_investment_plan", "")
        )

        prompt = load_prompt_template(
            agent_type="risk_mgmt",
            agent_name="aggresive_debator",
            context={
                **summary_context,
                "trader_decision": trader_decision,
                "history": history,
                "current_safe_response": current_safe_response,
                "current_neutral_response": current_neutral_response,
                "round_number": round_number,
                "is_first_round": is_first_round,
                "safe_history": safe_history,
                "neutral_history": neutral_history,
            },
        )

        response = llm.invoke(prompt)
        content: str = getattr(response, "content", str(response))
        argument = f"Risky Analyst: {content}"

        new_risk_debate_state: RiskDebateState = {
            "history": history + "\n" + argument,
            "risky_history": risky_history + "\n" + argument,
            "safe_history": prev_debate.get("safe_history", ""),
            "neutral_history": prev_debate.get("neutral_history", ""),
            "latest_speaker": "Risky",
            "current_risky_response": argument,
            "current_safe_response": prev_debate.get("current_safe_response", ""),
            "current_neutral_response": prev_debate.get("current_neutral_response", ""),
            "judge_decision": prev_debate.get("judge_decision", ""),
            "count": prev_debate.get("count", 0) + 1,
        }

        new_summary: RiskSummary = {
            "risk_debate_state": new_risk_debate_state,
        }
        if prev_summary is not None:
            new_summary["final_trade_decision"] = prev_summary.get("final_trade_decision", "")
            new_summary["raw_response"] = prev_summary.get("raw_response", "")

        return {"risk_summary": new_summary}

    return risky_node
