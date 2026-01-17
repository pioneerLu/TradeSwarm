from __future__ import annotations

from typing import Any, Dict

from tradingagents.agents.utils.agent_states import (
    AgentState,
    AnalystMemorySummary,
    RiskDebateState,
    RiskSummary,
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


def create_risk_manager(llm: Any, memory: Any):
    """创建 Risk Manager LangGraph 节点工厂。

    - 输入：全局 AgentState（包含四个 analyst_summary 和 research_summary）
    - 内部：从 risk_summary 中读取/维护 risk_debate_state
    - 输出：更新 risk_summary 和顶层 final_trade_decision 字段
    """

    def risk_manager_node(state: AgentState) -> Dict[str, Any]:
        """Risk Manager 节点，实现最终风险评估与交易决策。"""
        company_name = state["company_of_interest"]

        # 1. 读取上一轮辩论状态（封装在 risk_summary 内）
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

        # 2. 从四个 Analyst 的 MemorySummary 中构造当前情境
        curr_situation = _build_curr_situation_from_summaries(state)
        past_memories = memory.get_memories(curr_situation, n_matches=2)

        past_memory_str = ""
        for rec in past_memories:
            past_memory_str += rec.get("recommendation", "") + "\n\n"

        # 3. 读取 research_summary 中的 investment_plan
        research_summary: Dict[str, Any] | None = state.get("research_summary")  # type: ignore[assignment]
        trader_plan = (
            research_summary.get("investment_plan", "")  # type: ignore[union-attr]
            if research_summary is not None
            else state.get("investment_plan", "")
        )

        prompt = f"""As the Risk Management Judge and Debate Facilitator, your goal is to evaluate the debate between three risk analysts—Risky, Neutral, and Safe/Conservative—and determine the best course of action for the trader. Your decision must result in a clear recommendation: Buy, Sell, or Hold. Choose Hold only if strongly justified by specific arguments, not as a fallback when all sides seem valid. Strive for clarity and decisiveness.

Guidelines for Decision-Making:
1. **Summarize Key Arguments**: Extract the strongest points from each analyst, focusing on relevance to the context.
2. **Provide Rationale**: Support your recommendation with direct quotes and counterarguments from the debate.
3. **Refine the Trader's Plan**: Start with the trader's original plan, **{trader_plan}**, and adjust it based on the analysts' insights.
4. **Learn from Past Mistakes**: Use lessons from **{past_memory_str}** to address prior misjudgments and improve the decision you are making now to make sure you don't make a wrong BUY/SELL/HOLD call that loses money.

Deliverables:
- A clear and actionable recommendation: Buy, Sell, or Hold.
- Detailed reasoning anchored in the debate and past reflections.

---

**Analysts Debate History:**  
{history}

---

Focus on actionable insights and continuous improvement. Build on past lessons, critically evaluate all perspectives, and ensure each decision advances better outcomes."""

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
    print("开始测试 risk_manager_node")
    print("=" * 80)
    
    print("\n[1/4] 初始化 Memory...")
    config = {
        "backend_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "embedding_model": "text-embedding-v4",
    }
    memory = FinancialSituationMemory(name="test_risk_manager", config=config)
    
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
    
    print("\n[3/4] 创建 risk_manager_node...")
    risk_manager_node = create_risk_manager(llm, memory)
    print("✓ risk_manager_node 创建完成")
    
    print("\n[4/4] 准备测试用的 AgentState 并调用...")
    demo_summary: AnalystMemorySummary = {
        "today_report": "市场整体呈现上涨趋势，银行板块表现稳健。技术指标显示向上动能，成交量支撑良好。",
        "history_report": "Demo history report.",
    }

    agentstate: AgentState = {
        "company_of_interest": "000001",
        "trade_date": "2024-12-07",
        "trade_timestamp": "2024-12-07 10:00:00",
        "market_analyst_summary": demo_summary,
        "news_analyst_summary": {
            "today_report": "近期新闻显示，平安银行在零售业务转型方面取得积极进展。分析师基于强劲的资产质量改善预期，上调了目标价。",
            "history_report": "Demo history report.",
        },
        "sentiment_analyst_summary": {
            "today_report": "社交媒体情绪对平安银行整体偏正面，投资者对银行数字化转型和零售业务增长持乐观态度。",
            "history_report": "Demo history report.",
        },
        "fundamentals_analyst_summary": {
            "today_report": "平安银行财务基本面保持稳健，营收持续增长。资产质量持续改善，不良贷款率下降，资本充足率保持在合理水平。",
            "history_report": "Demo history report.",
        },
        "research_summary": {
            "investment_plan": "分析零售业务转型进展和资产质量改善趋势。监控市场情绪变化，适时调整仓位。",
        },
        "risk_summary": None,  # type: ignore[assignment]
        "investment_plan": None,
        "trader_investment_plan": None,
        "final_trade_decision": None,
        "messages": [],
    }
    
    print("-" * 80)
    try:
        result = risk_manager_node(agentstate)
        
        print("\n" + "=" * 80)
        print("测试结果:")
        print("=" * 80)
        
        print("\n【Final Trade Decision】")
        print("-" * 80)
        print(result.get("final_trade_decision", "N/A"))
        
        print("\n【Risk Summary】")
        print("-" * 80)
        summary: RiskSummary = result.get("risk_summary", {})  # type: ignore[assignment]
        risk_state = summary.get("risk_debate_state", {})
        print(f"Judge Decision: {risk_state.get('judge_decision', 'N/A')[:300]}...")
        print(f"\nCount: {risk_state.get('count', 'N/A')}")
        print(f"\nLatest Speaker: {risk_state.get('latest_speaker', 'N/A')}")
        print(f"\nHistory: {risk_state.get('history', 'N/A')[:200]}...")
        
        print("\n" + "=" * 80)
        print("✓ 测试完成！")
        print("=" * 80)
        
    except Exception as e:  # pragma: no cover - 手工调试用
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback

        traceback.print_exc()
