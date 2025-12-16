from tradingagents.agents.utils.agent_states import AgentState
from langchain.agents import create_agent


# agentstate def
agentstate = AgentState(
    company_of_interest="AAPL",
    trade_date="2025-12-07",
    sender="market_analyst",
    market_report="Market is showing positive trends with tech stocks performing well.",
    sentiment_report="Social media sentiment is largely positive for Apple with recent product launches.",
    news_report="Recent news indicates strong holiday sales expectations for Apple products.",
    fundamentals_report="Apple's financial fundamentals remain strong with consistent revenue growth.",
    investment_debate_state={
        "bull_history": "Bullish sentiment based on strong brand loyalty and ecosystem integration.",
        "bear_history": "Concerns about market saturation in mature markets.",
        "history": "Initial analysis shows balanced perspectives with slight bullish tilt.",
        "current_response": "Overall sentiment is positive with strong consumer demand.",
        "judge_decision": "Pending final evaluation.",
        "count": 1
    },
    investment_plan="Analyze social media trends and correlate with sales data.",
    trader_investment_plan="Monitor sentiment changes and adjust positions accordingly.",
    risk_debate_state={
        "risky_history": "High-risk tolerance due to strong market position.",
        "safe_history": "Conservative approach considering market volatility.",
        "neutral_history": "Balanced perspective weighing risks and opportunities.",
        "history": "Risk assessment in progress with multiple viewpoints.",
        "latest_speaker": "risk_analyst",
        "current_risky_response": "Potential for high returns with calculated risks.",
        "current_safe_response": "Recommend cautious approach with diversified portfolio.",
        "current_neutral_response": "Moderate risk strategy with regular monitoring.",
        "judge_decision": "Awaiting final risk assessment.",
        "count": 1
    },
    final_trade_decision="PENDING",

    # list[AnyMessage]
    messages=[{"role": "user", "content": "Start a detailed news indicator analysis for Apple Inc. (AAPL)."}]
)


# langgraph node def
def create_news_analyst(llm) -> dict:
    def news_analyst_node(state) -> dict:
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]

        # tools
        tools = [
            # get_news,
            # get_global_news,
        ]

        # system prompt
        system_prom = (
           "You are a professional news and macroeconomic researcher tasked with analyzing recent global "
            "and company-specific events over the past 7 days. Your objective is to write a detailed, "
            "fine-grained report summarizing relevant macroeconomic news, market signals, and key events "
            "that may impact trading and investment decision-making for the selected company."
            "Make sure to analyze both macro global news and specific company news related to {ticker}. "
            "You are a helpful AI assistant, collaborating with other assistants. "
            "Use the provided tools to progress towards answering the question. "
            "If you are unable to fully answer, another assistant with different tools will continue. "
            "If you determine a FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL**, prefix your output with that text. "
            "You have access to the following tools: {tool_names}. "
            "For your reference, the current date is {current_date}."
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

        # invoke agent with first message (same模式)
        result = agent.invoke(
            input=state["messages"][0],
        )

        # 存储最后 AI 回复
        rep = result["messages"][-1].content

        news_report = ""
        if len(result["messages"][-1].tool_calls) == 0:
            news_report = result["messages"][-1].content

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
