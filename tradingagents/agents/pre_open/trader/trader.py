from __future__ import annotations

from typing import Any, Callable, Dict

from langchain_core.language_models import BaseChatModel

from tradingagents.agents.utils.agentstate.agent_states import AgentState
from tradingagents.agents.pre_open.strategy_skills.router import (
    parse_reflection_response,
    render_strategy_skill_rules,
)
from tradingagents.agents.utils.prompt_loader import load_prompt_template, render_pre_open_template
from tradingagents.agents.utils.state_helpers import (
    build_curr_situation_from_summaries,
    format_portfolio_info,
    format_position_info,
    get_prompt_context_from_summaries,
)
from tradingagents.config import get_strategy_skills_config


def _build_user_prompt(
    *,
    company_name: str,
    investment_plan: str,
    position_info: str,
    portfolio_info: str,
) -> str:
    from pathlib import Path
    from jinja2 import Template

    user_prompt_path = Path(__file__).parent / "user_prompt.j2"
    if user_prompt_path.exists():
        with open(user_prompt_path, "r", encoding="utf-8") as f:
            user_template = Template(f.read())
            return user_template.render(
                company_name=company_name,
                investment_plan=investment_plan,
                position_info=position_info,
                portfolio_info=portfolio_info,
            )
    return (
        f"Create a trading plan for {company_name}.\n\n"
        f"Investment plan:\n{investment_plan}\n"
        f"{position_info}{portfolio_info}"
    )


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
        position_info = format_position_info(state.get("current_position"))
        portfolio_info = format_portfolio_info(state.get("portfolio_state"))
        user_prompt = _build_user_prompt(
            company_name=company_name,
            investment_plan=investment_plan,
            position_info=position_info,
            portfolio_info=portfolio_info,
        )

        skill_cfg = get_strategy_skills_config()
        skill_mode = skill_cfg["mode"]
        fallback_mode = skill_cfg["fallback_mode"]
        forced_skill = skill_cfg.get("force_skill")
        reflection_context: Dict[str, Any] = {
            "mode": skill_mode,
            "fallback_mode": fallback_mode,
            "forced_skill": forced_skill,
            "valid": False,
            "market_regime": None,
            "selected_skill": None,
            "regime_confidence": None,
            "regime_evidence": [],
            "raw_response": None,
        }

        if skill_mode == "reflect":
            reflection_prompt = render_pre_open_template(
                "trader/regime_reflection_prompt.j2",
                {
                    "past_memory_str": past_memory_str,
                    "position_info": position_info,
                    "portfolio_info": portfolio_info,
                    "investment_plan": investment_plan,
                    **summary_context,
                },
            )
            reflection_result = llm.invoke(input=reflection_prompt)
            reflection_content: str = getattr(reflection_result, "content", str(reflection_result))
            reflection_context.update(parse_reflection_response(reflection_content))

        skill_render = render_strategy_skill_rules(
            mode=skill_mode,
            fallback_mode=fallback_mode,
            selected_skill=forced_skill or reflection_context.get("selected_skill"),
        )
        strategy_skill_context = {
            "skill_router_mode": skill_mode,
            "skill_router_effective_mode": skill_render["effective_mode"],
            "fallback_mode": fallback_mode,
            "forced_selected_skill": forced_skill,
            "force_skill_applied": bool(forced_skill),
            "reflection_market_regime": reflection_context.get("market_regime"),
            "reflection_selected_skill": reflection_context.get("selected_skill"),
            "reflection_confidence": reflection_context.get("regime_confidence"),
            "reflection_evidence": reflection_context.get("regime_evidence") or [],
            "reflection_valid": bool(reflection_context.get("valid")),
            "included_skill_template": skill_render.get("included_skill_template"),
            "included_skill_templates": skill_render.get("included_skill_templates") or [],
            "strategy_skill_rules_text": skill_render["strategy_skill_rules_text"],
        }

        system_prompt = load_prompt_template(
            agent_type="trader",
            agent_name="trader",
            context={
                "past_memory_str": past_memory_str,
                "strategy_skill_rules_text": skill_render["strategy_skill_rules_text"],
                "strategy_skill_context": strategy_skill_context,
                **summary_context,
            },
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
            "strategy_skill_context": strategy_skill_context,
        }

    return trader_node
