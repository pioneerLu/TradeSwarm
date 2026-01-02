from tradingagents.agents.init_llm import llm
from langgraph.graph import StateGraph, START, END
from tradingagents.agents.utils.agent_states import AgentState
from tradingagents.agents.analysts.fundamentals_analyst import create_fundamentals_analyst
from tradingagents.agents.analysts.market_analyst import create_market_analyst
from tradingagents.agents.analysts.news_analyst import create_news_analyst
# from tradingagents.agents.analysts.social_media_analyst import create_social_media_analyst


def aggregate_analysts(state):
    """聚合所有分析师的报告"""
    market_research_report = state.get("market_report", "")
    # sentiment_report = state.get("sentiment_report", "")
    news_report = state.get("news_report", "")
    fundamentals_report = state.get("fundamentals_report", "")
    
    # curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
    curr_situation = f"{market_research_report}\n\n{news_report}\n\n{fundamentals_report}"
    
    return {
        "curr_situation": curr_situation,
    }


def create_analysts_graph(llm):
    """创建分析师工作流图"""
    workflow = StateGraph(AgentState)
    
    # 添加分析节点
    workflow.add_node("fundamentals", create_fundamentals_analyst(llm))
    workflow.add_node("market", create_market_analyst(llm))
    workflow.add_node("news", create_news_analyst(llm))
    # workflow.add_node("social_media", create_social_media_analyst(llm))

    # 添加聚合节点
    workflow.add_node("aggregate", aggregate_analysts)
    
    # 定义边：从 START 并行启动所有分析节点
    workflow.add_edge(START, "fundamentals")
    workflow.add_edge(START, "market")
    workflow.add_edge(START, "news")
    # workflow.add_edge(START, "social_media")  

    # 所有分析节点完成后，进入聚合节点
    workflow.add_edge("fundamentals", "aggregate")
    workflow.add_edge("market", "aggregate")
    workflow.add_edge("news", "aggregate")
    # workflow.add_edge("social_media", "aggregate")  
    
    # 聚合完成后结束
    workflow.add_edge("aggregate", END)
    
    return workflow.compile()


def create_initial_state() -> AgentState:
    """创建初始 AgentState 实例"""
    return AgentState(
        curr_situation="",
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


if __name__ == "__main__":

    from IPython.display import Image, display
    app = create_analysts_graph(llm)
    # Show workflow
    display(Image(app.get_graph().draw_mermaid_png()))
    # 创建初始状态
    initial_state = create_initial_state()
    
    # 执行图
    result = app.invoke(initial_state)
    
    # 打印结果
    if result.get("messages") and len(result["messages"]) > 0:
        last_message = result["messages"][-1]
        if hasattr(last_message, 'content') and last_message.content:
            print(result["messages"][-1].content)
        else:
            print("最后一条消息没有内容")
    else:
        print("没有消息返回")
    
    # 打印聚合结果
    if result.get("curr_situation"):
        print("\n" + "=" * 80)
        print("聚合后的当前情况:")
        print("=" * 80)
        print(result["curr_situation"])
    
