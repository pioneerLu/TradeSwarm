from __future__ import annotations

from typing import Any, Dict, Callable
from langchain_core.language_models import BaseChatModel
import functools
import time
import json

from tradingagents.agents.utils.agentstate.agent_states import AgentState
from tradingagents.agents.utils.state_helpers import build_curr_situation_from_summaries
from tradingagents.agents.utils.prompt_loader import load_prompt_template


def create_trader(llm: BaseChatModel, memory: Any) -> Callable[[AgentState], Dict[str, Any]]:
    def trader_node(state: AgentState) -> Dict[str, Any]:
        company_name = state["company_of_interest"]
        
        # 读取 research_summary 中的 investment_plan
        research_summary: Dict[str, Any] | None = state.get("research_summary")  # type: ignore[assignment]
        investment_plan = (
            research_summary.get("investment_plan", "")  # type: ignore[union-attr]
            if research_summary is not None
            else state.get("investment_plan", "")
        )
        
        # 从四个 Analyst 的 MemorySummary 中构造当前情境
        curr_situation = build_curr_situation_from_summaries(state)
        past_memories = memory.get_memories(curr_situation, n_matches=2)

        past_memory_str = ""
        if past_memories:
            for i, rec in enumerate(past_memories, 1):
                past_memory_str += rec["recommendation"] + "\n\n"
        else:
            past_memory_str = "No past memories found."

        # 加载并渲染 system prompt 模板
        system_prompt = load_prompt_template(
            agent_type="trader",
            agent_name="trader",
            context={
                "past_memory_str": past_memory_str,
            },
        )
        
        # 加载并渲染 user prompt 模板
        from pathlib import Path
        from jinja2 import Template
        user_prompt_path = Path(__file__).parent / "user_prompt.j2"
        if user_prompt_path.exists():
            with open(user_prompt_path, "r", encoding="utf-8") as f:
                user_template = Template(f.read())
                user_prompt = user_template.render(
                    company_name=company_name,
                    investment_plan=investment_plan,
                )
        else:
            # Fallback
            user_prompt = f"基于分析师团队的全面分析，以下是针对 {company_name} 量身定制的投资计划。该计划融合了当前技术市场趋势、宏观经济指标和社交媒体情绪的洞察。使用此计划作为评估你下一个交易决策的基础。\n\n拟议投资计划：{investment_plan}\n\n利用这些洞察做出明智且具有战略性的决策。"

        messages = [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ]

        result = llm.invoke(messages)
        content: str = getattr(result, "content", str(result))

        return {
            "messages": [result],
            "trader_investment_plan": content,
        }

    return trader_node
