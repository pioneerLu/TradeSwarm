from tradingagents.agents.utils.agent_states import AgentState
from langchain.agents import create_agent
from tradingagents.tools.news_tools import get_news, get_global_news


# agentstate def
agentstate = AgentState(
    company_of_interest="000001",
    trade_date="2025-12-11",
    sender="news_analyst",
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
        "count": 1
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
        "count": 1
    },
    final_trade_decision="待定",

    # list[AnyMessage]
    messages=[{"role": "user", "content": "开始对平安银行（000001）进行详细的新闻和宏观经济分析。"}]
)


# langgraph node def
def create_news_analyst(llm) -> dict:
    def news_analyst_node(state) -> dict:
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]

        # 工具列表
        tools = [
            get_news,
            get_global_news,
        ]

        # system prompt
        system_prom = (
            "你是一位专业的新闻和宏观经济研究员，负责分析最近7天内的全球和公司特定事件。"
            "你的目标是撰写一份详细、细致的报告，总结相关的宏观经济新闻、市场信号和关键事件，"
            "这些信息可能影响所选股票的交易和投资决策。"
            "确保同时分析宏观全球新闻和与 {ticker} 相关的特定公司新闻。"
            "你是一个有用的 AI 助手，与其他助手协作。"
            "使用提供的工具来推进问题的解答。"
            "**重要：工作流程和停止条件**"
            "1. 首先调用 get_news 工具获取股票相关新闻（最多调用1次）。"
            "2. 然后调用 get_global_news 工具获取宏观经济新闻（最多调用1次）。"
            "3. 获取数据后，立即基于获取的数据撰写分析报告。"
            "4. 撰写完报告后，必须立即停止，不要再调用任何工具。"
            "5. 如果工具调用失败或返回空数据，也要基于已有信息撰写报告并停止，不要重复尝试。"
            "6. 不要重复调用相同的工具，每个工具最多调用1次。"
            "如果你无法完全回答，其他助手会继续。"
            "如果你确定最终交易建议：**买入/持有/卖出**，请在输出前加上相应前缀。"
            "分析提示："
            "1. 重点关注可能影响股价的重大新闻和事件（如政策变化、业绩公告、行业动态等）。"
            "2. 分析新闻对股票可能产生的正面或负面影响。"
            "3. 区分短期影响和长期影响。"
            "4. 在描述'当前'、'最新'等状态时，使用最新日期的新闻信息。"
            "5. 可以使用历史新闻进行趋势分析，但描述当前状态时使用最新信息。"
            "你可用的工具包括：{tool_names}。"
            "当前日期是 {current_date}。"
            "当前要分析的股票代码是 {ticker}。"
            "请使用中文进行分析和报告。"
        ).format(
            tool_names=", ".join([tool.name for tool in tools]),
            current_date=current_date,
            ticker=ticker
        )

        # init agent
        agent = create_agent(
            model=llm,
            tools=tools,
            system_prompt=system_prom
        )

        # invoke agent with last user message (LangChain agent 通常接受单个输入)
        # 使用最后一条用户消息，agent 会自动处理工具调用
        if not state["messages"]:
            # 如果没有消息，使用初始消息
            last_message = {"role": "user", "content": f"分析股票 {ticker} 的新闻和宏观经济信息"}
        else:
            last_message = state["messages"][-1]
        
        result = agent.invoke(
            input=last_message,
            config={"recursion_limit": 50}  # 增加递归限制
        )

        # 提取最后一条 AI 消息内容（跳过工具调用消息）
        news_report = ""
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
                    news_report = msg.content
                    break
        
        # 如果没有找到，使用最后一条消息的内容（作为兜底）
        if not news_report and result["messages"]:
            last_msg = result["messages"][-1]
            if hasattr(last_msg, 'content') and last_msg.content:
                news_report = last_msg.content

        return {
            "messages": result["messages"],     # append strategy
            "news_report": news_report,
        }

    return news_analyst_node


# main test
if __name__ == "__main__":
    from tradingagents.agents.init_llm import llm
    from langgraph.graph import StateGraph, START, END

    # 1.workflow init
    workflow = StateGraph(AgentState)

    # 2.add_node
    workflow.add_node("news", create_news_analyst(llm))

    # 3.define edges
    workflow.add_edge(START, "news")
    workflow.add_edge("news", END)

    app = workflow.compile()

    # 4.invoke graph to get result
    result = app.invoke(agentstate)

    # print last agent reply
    print(result["messages"][-1].content)
