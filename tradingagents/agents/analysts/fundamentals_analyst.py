from tradingagents.agents.utils.agent_states import AgentState
from langchain.agents import create_agent
from tradingagents.tools.fundamentals_tools import (
    get_company_info,
    get_financial_statements,
    get_financial_indicators,
    get_valuation_indicators,
    get_earnings_data
)


# agentstate def
agentstate = AgentState(
    company_of_interest="000001",
    trade_date="2025-12-11",
    sender="fundamentals_analyst",
    market_report="市场显示积极趋势，科技股表现良好。",
    sentiment_report="社交媒体情绪对平安银行近期表现普遍乐观。",
    news_report="近期新闻显示银行业对平安银行有积极的销售预期。",
    fundamentals_report="平安银行的财务基本面保持强劲，收入持续增长。",
    investment_debate_state={
        "bull_history": "基于强劲品牌忠诚度和生态系统整合的看涨情绪。",
        "bear_history": "对成熟市场饱和的担忧。",
        "history": "初步分析显示平衡的观点，略微偏向看涨。",
        "current_response": "总体情绪积极，消费者需求强劲。",
        "judge_decision": "等待最终评估。",
        "count": 1,
    },
    investment_plan="分析社交媒体趋势并与销售数据关联。",
    trader_investment_plan="监控情绪变化并相应调整仓位。",
    risk_debate_state={
        "risky_history": "由于强劲的市场地位，风险承受能力较高。",
        "safe_history": "考虑到市场波动性，采取保守方法。",
        "neutral_history": "平衡的视角，权衡风险和机会。",
        "history": "风险评估正在进行中，有多个观点。",
        "latest_speaker": "risk_analyst",
        "current_risky_response": "在计算风险的情况下，有高回报的潜力。",
        "current_safe_response": "建议采取谨慎的方法，分散投资组合。",
        "current_neutral_response": "适度的风险策略，定期监控。",
        "judge_decision": "等待最终风险评估。",
        "count": 1,
    },
    final_trade_decision="待定",
    messages=[
        {
            "role": "user",
            "content": "开始对平安银行（000001）进行详细的基本面和估值分析。",
        }
    ],
)


def create_fundamentals_analyst(llm) -> dict:
    def fundamentals_analyst_node(state) -> dict:
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]

        # 工具列表
        tools = [
            get_company_info,
            get_financial_statements,
            get_financial_indicators,
            get_valuation_indicators,
            get_earnings_data,
        ]

        # system prompt
        system_prom = (
            "你是一位专业的财务基本面和估值分析师，负责评估公司的盈利能力、成长性、资产负债表健康度、"
            "现金流、资本结构、资本配置和估值水平。"
            "你需要撰写一份详细、细致的报告，评估公司的财务基本面和估值情况。"
            "结合最近的季度/年度趋势、盈利质量以及任何风险信号进行分析。"
            "在报告末尾附加一个 Markdown 表格来总结关键指标和要点。"
            "你是一个有用的 AI 助手，与其他助手协作。"
            "使用提供的工具来推进问题的解答。"
            "**重要：工作流程和停止条件**"
            "1. 首先调用 get_company_info 工具获取公司基本信息（最多调用1次）。"
            "2. 然后调用 get_financial_statements 工具获取三大财务报表（最多调用1次）。"
            "3. 调用 get_financial_indicators 工具获取财务指标（最多调用1次）。"
            "4. 调用 get_valuation_indicators 工具获取估值指标（最多调用1次）。"
            "5. 可选：调用 get_earnings_data 工具获取业绩预告/快报（最多调用1次）。"
            "6. 获取数据后，立即基于获取的数据撰写分析报告。"
            "7. 撰写完报告后，必须立即停止，不要再调用任何工具。"
            "8. 如果工具调用失败或返回空数据，也要基于已有信息撰写报告并停止，不要重复尝试。"
            "9. 不要重复调用相同的工具，每个工具最多调用1次。"
            "如果你无法完全回答，其他助手会继续。"
            "如果你确定最终交易建议：**买入/持有/卖出**，请在输出前加上相应前缀。"
            "分析提示："
            "1. 重点关注盈利能力指标（ROE、ROA、毛利率、净利率等）。"
            "2. 分析成长性指标（营收增长率、净利润增长率等）。"
            "3. 评估财务健康度（资产负债率、流动比率、现金流等）。"
            "4. 分析估值水平（PE、PB、PS等）并与市场/行业对比。"
            "5. 识别潜在风险信号（如盈利质量下降、现金流恶化等）。"
            "6. 在描述'当前'、'最新'等状态时，使用最新报告期的数据。"
            "7. 可以使用历史数据进行趋势分析，但描述当前状态时使用最新信息。"
            "你可用的工具包括：{tool_names}。"
            "当前日期是 {current_date}。"
            "当前要分析的股票代码是 {ticker}。"
            "请使用中文进行分析和报告。"
        ).format(
            tool_names=", ".join([tool.name for tool in tools]),
            current_date=current_date,
            ticker=ticker
        )

        agent = create_agent(
            model=llm,
            tools=tools,
            system_prompt=system_prom
        )

        # invoke agent with last user message
        if not state["messages"]:
            # 如果没有消息，使用初始消息
            last_message = {"role": "user", "content": f"分析股票 {ticker} 的基本面和估值情况"}
        else:
            last_message = state["messages"][-1]
        
        result = agent.invoke(
            input=last_message,
            config={"recursion_limit": 50}  # 增加递归限制
        )

        # 提取最后一条 AI 消息内容（跳过工具调用消息）
        fundamentals_report = ""
        # 从后往前查找最后一条有内容的 AI 消息（非工具调用）
        for msg in reversed(result["messages"]):
            # 检查是否是 AI 消息且有内容
            if hasattr(msg, 'content') and msg.content:
                # 检查是否有 tool_calls（如果有 tool_calls，说明是工具调用请求，不是最终回复）
                has_tool_calls = False
                if hasattr(msg, 'tool_calls'):
                    # tool_calls 可能是列表或非空值
                    if msg.tool_calls and len(msg.tool_calls) > 0:
                        has_tool_calls = True
                
                # 如果没有工具调用，这就是最终的 AI 回复
                if not has_tool_calls:
                    fundamentals_report = msg.content
                    break
        
        # 如果没有找到，使用最后一条消息的内容（作为兜底）
        if not fundamentals_report and result["messages"]:
            last_msg = result["messages"][-1]
            if hasattr(last_msg, 'content') and last_msg.content:
                fundamentals_report = last_msg.content

        return {
            "messages": result["messages"],     # append strategy
            "fundamentals_report": fundamentals_report,
        }

    return fundamentals_analyst_node


if __name__ == "__main__":
    from tradingagents.agents.init_llm import llm
    from langgraph.graph import StateGraph, START, END

    workflow = StateGraph(AgentState)
    workflow.add_node("fundamentals", create_fundamentals_analyst(llm))
    workflow.add_edge(START, "fundamentals")
    workflow.add_edge("fundamentals", END)

    app = workflow.compile()
    result = app.invoke(agentstate)
    print(result["messages"][-1].content)
