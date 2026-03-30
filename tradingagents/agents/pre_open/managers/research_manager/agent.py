from __future__ import annotations

from typing import Any, Callable, Dict

from langchain_core.language_models import BaseChatModel

from tradingagents.agents.utils.agentstate.agent_states import AgentState, InvestDebateState, ResearchSummary
from tradingagents.agents.utils.prompt_loader import load_prompt_template
from tradingagents.agents.utils.state_helpers import build_curr_situation_from_summaries, get_prompt_context_from_summaries


def create_research_manager(llm: BaseChatModel, memory: Any) -> Callable[[AgentState], Dict[str, Any]]:
    def research_manager_node(state: AgentState) -> Dict[str, Any]:
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
        curr_situation = build_curr_situation_from_summaries(state, include_history=True, max_length=4000)
        past_memories = memory.get_memories(curr_situation, n_matches=2)
        past_memory_str = ""
        for rec in past_memories:
            past_memory_str += rec.get("recommendation", "") + "\n\n"

        summary_context = get_prompt_context_from_summaries(state)
        prompt = load_prompt_template(
            agent_type="managers",
            agent_name="research_manager",
            context={
                **summary_context,
                "past_memory_str": past_memory_str,
                "history": history,
            },
        )

        response = llm.invoke(prompt)
        content: str = getattr(response, "content", str(response))

        new_investment_debate_state: InvestDebateState = {
            "judge_decision": content,
            "history": prev_debate.get("history", ""),
            "bear_history": prev_debate.get("bear_history", ""),
            "bull_history": prev_debate.get("bull_history", ""),
            "current_response": content,
            "count": prev_debate.get("count", 0) + 1,
        }

        new_summary: ResearchSummary = {
            "investment_debate_state": new_investment_debate_state,
            "investment_plan": content,
            "raw_response": content,
        }
        return {
            "research_summary": new_summary,
            "investment_plan": content,
        }

    return research_manager_node
