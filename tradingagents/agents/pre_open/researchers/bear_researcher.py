from __future__ import annotations

from typing import Any, Callable, Dict

from langchain_core.language_models import BaseChatModel

from tradingagents.agents.utils.agentstate.agent_states import AgentState, InvestDebateState, ResearchSummary
from tradingagents.agents.utils.prompt_loader import load_prompt_template
from tradingagents.agents.utils.state_helpers import format_position_context, get_prompt_context_from_summaries


def create_bear_researcher(llm: BaseChatModel, memory: Any) -> Callable[[AgentState], Dict[str, Any]]:
    def bear_node(state: AgentState) -> dict:
        prev_summary: ResearchSummary | None = state.get("research_summary")  # type: ignore[assignment]
        prev_debate: InvestDebateState = (
            prev_summary.get("investment_debate_state")  # type: ignore[union-attr]
            if prev_summary is not None
            else {
                "bull_history": "",
                "bear_history": "",
                "history": "",
                "current_response": "",
                "judge_decision": "",
                "count": 0,
            }
        )

        history = prev_debate.get("history", "")
        bear_history = prev_debate.get("bear_history", "")
        bull_history = prev_debate.get("bull_history", "")
        current_response = prev_debate.get("current_response", "")
        count = prev_debate.get("count", 0)

        round_number = (count // 2) + 1
        is_first_round = count < 2
        summary_context = get_prompt_context_from_summaries(state)

        prompt = load_prompt_template(
            agent_type="researchers",
            agent_name="bear_researcher",
            context={
                **summary_context,
                "history": history,
                "current_response": current_response,
                "round_number": round_number,
                "is_first_round": is_first_round,
                "bull_history": bull_history,
                "position_context": format_position_context(state),
            },
        )

        response = llm.invoke(prompt)
        content: str = getattr(response, "content", str(response))
        argument = f"Bear Analyst: {content}"

        new_investment_debate_state: InvestDebateState = {
            "history": history + "\n" + argument,
            "bear_history": bear_history + "\n" + argument,
            "bull_history": prev_debate.get("bull_history", ""),
            "current_response": argument,
            "judge_decision": prev_debate.get("judge_decision", ""),
            "count": prev_debate.get("count", 0) + 1,
        }

        new_summary: ResearchSummary = {
            "investment_debate_state": new_investment_debate_state,
        }
        if prev_summary is not None:
            new_summary["investment_plan"] = prev_summary.get("investment_plan", "")
            new_summary["raw_response"] = prev_summary.get("raw_response", "")

        return {"research_summary": new_summary}

    return bear_node
