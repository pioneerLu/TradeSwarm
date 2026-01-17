from __future__ import annotations

from typing import Any, Dict

from tradingagents.agents.utils.agent_states import (
    AgentState,
    AnalystMemorySummary,
    InvestDebateState,
    ResearchSummary,
)


def _build_curr_situation_from_summaries(state: AgentState) -> str:
    """从四个 Analyst 的 MemorySummary 中构造当前情境描述。"""
    market_summary: AnalystMemorySummary = state["market_analyst_summary"]
    news_summary: AnalystMemorySummary = state["news_analyst_summary"]
    sentiment_summary: AnalystMemorySummary = state["sentiment_analyst_summary"]
    fundamentals_summary: AnalystMemorySummary = state["fundamentals_analyst_summary"]

    market_report = market_summary["today_report"]
    news_report = news_summary["today_report"]
    sentiment_report = sentiment_summary["today_report"]
    fundamentals_report = fundamentals_summary["today_report"]

    return (
        f"{market_report}\n\n"
        f"{sentiment_report}\n\n"
        f"{news_report}\n\n"
        f"{fundamentals_report}"
    )


def create_research_manager(llm: Any, memory: Any):
    """创建 Research Manager LangGraph 节点工厂。

    - 输入：全局 AgentState（包含四个 analyst_summary）
    - 内部：从 research_summary 中读取/维护 investment_debate_state
    - 输出：更新 research_summary 和顶层 investment_plan 字段
    """

    def research_manager_node(state: AgentState) -> Dict[str, Any]:
        """Research Manager 节点，实现最终投资结论与计划生成。"""
        # 1. 读取上一轮辩论状态（封装在 research_summary 内）
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

        # 2. 从四个 Analyst 的 MemorySummary 中构造当前情境
        curr_situation = _build_curr_situation_from_summaries(state)
        past_memories = memory.get_memories(curr_situation, n_matches=2)

        past_memory_str = ""
        for rec in past_memories:
            past_memory_str += rec.get("recommendation", "") + "\n\n"

        prompt = f"""As the portfolio manager and debate facilitator, your role is to critically evaluate this round of debate and make a definitive decision: align with the bear analyst, the bull analyst, or choose Hold only if it is strongly justified based on the arguments presented.

Summarize the key points from both sides concisely, focusing on the most compelling evidence or reasoning. Your recommendation—Buy, Sell, or Hold—must be clear and actionable. Avoid defaulting to Hold simply because both sides have valid points; commit to a stance grounded in the debate's strongest arguments.

Additionally, develop a detailed investment plan for the trader. This should include:

Your Recommendation: A decisive stance supported by the most convincing arguments.
Rationale: An explanation of why these arguments lead to your conclusion.
Strategic Actions: Concrete steps for implementing the recommendation.
Take into account your past mistakes on similar situations. Use these insights to refine your decision-making and ensure you are learning and improving. Present your analysis conversationally, as if speaking naturally, without special formatting. 

Here are your past reflections on mistakes:
\"{past_memory_str}\"

Here is the debate:
Debate History:
{history}"""
        
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


if __name__ == "__main__":
    # 保留原有的测试逻辑，但适配新的 AgentState 结构，便于后续回归验证。
    import os

    from dotenv import load_dotenv
    from langchain_openai import ChatOpenAI
    from openai import OpenAI

    from tradingagents.agents.utils.memory import FinancialSituationMemory
    
    load_dotenv()
    
    client = OpenAI(
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    
    print("=" * 80)
    print("开始测试 research_manager_node")
    print("=" * 80)
    
    print("\n[1/4] 初始化 Memory...")
    config = {
        "backend_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "embedding_model": "text-embedding-v4",
    }
    memory = FinancialSituationMemory(name="test_research_manager", config=config)
    
    test_memories = [
        (
            "银行板块呈现上涨趋势，基本面强劲，市场情绪积极",
            "Previous mistake: 对银行股过于乐观，未充分考虑市场波动性。应该更加谨慎并分散投资组合。",
        ),
        (
            "市场信号混杂，新闻面积极但基本面存在担忧",
            "Previous mistake: 当明确的看涨信号出现时，默认选择持有。应该基于强劲的基本面采取果断行动。",
        ),
    ]
    memory.add_situations(test_memories)
    print("✓ Memory 初始化完成，已添加测试记忆")
    
    print("\n[2/4] 初始化 LLM...")
    llm = ChatOpenAI(
        model="qwen-plus",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key=os.getenv("DASHSCOPE_API_KEY"),
    )
    print("✓ LLM 初始化完成")
    
    print("\n[3/4] 创建 research_manager_node...")
    research_manager_node = create_research_manager(llm, memory)
    print("✓ research_manager_node 创建完成")
    
    print("\n[4/4] 准备测试用的 AgentState 并调用...")
    demo_summary: AnalystMemorySummary = {
        "today_report": "Demo today report.",
        "history_report": "Demo history report.",
    }

    agentstate: AgentState = {
        "company_of_interest": "000001",
        "trade_date": "2024-12-07",
        "trade_timestamp": "2024-12-07 10:00:00",
        "market_analyst_summary": demo_summary,
        "news_analyst_summary": demo_summary,
        "sentiment_analyst_summary": demo_summary,
        "fundamentals_analyst_summary": demo_summary,
        "research_summary": None,  # type: ignore[assignment]
        "risk_summary": None,  # type: ignore[assignment]
        "investment_plan": None,
        "trader_investment_plan": None,
        "final_trade_decision": None,
        "messages": [],
    }

    print("-" * 80)
    try:
        result = research_manager_node(agentstate)
        
        print("\n" + "=" * 80)
        print("测试结果:")
        print("=" * 80)
        
        print("\n【Investment Plan】")
        print("-" * 80)
        print(result.get("investment_plan", "N/A"))
        
        print("\n【Research Summary】")
        print("-" * 80)
        summary: ResearchSummary = result.get("research_summary", {})  # type: ignore[assignment]
        debate_state = summary.get("investment_debate_state", {})
        print(
            f"Judge Decision: {debate_state.get('judge_decision', 'N/A')[:300]}..."
        )
        print(f"\nCount: {debate_state.get('count', 'N/A')}")
        print(f"\nHistory: {debate_state.get('history', 'N/A')[:200]}...")
        
        print("\n" + "=" * 80)
        print("✓ 测试完成！")
        print("=" * 80)
        
    except Exception as e:  # pragma: no cover - 手工调试用
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback

        traceback.print_exc()