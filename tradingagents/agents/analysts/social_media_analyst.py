from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import time
import json
from tradingagents.agents.utils.agent_states import AgentState
from langchain.agents import create_agent

# agentstate def
agentstate = AgentState(
    company_of_interest="AAPL",
    trade_date="2025-12-07",
    sender="social_media_analyst",
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
    messages=[{"role": "user", "content": "Start a detailed social media sentiment and news analysis for Apple Inc. (AAPL)."}]
)


# langgraph node def
def create_social_media_analyst(llm) -> dict:
    def social_media_analyst_node(state)->dict:
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]

        tools = [
        ]

        # Combine the system message parts into a single string variable
        system_prom = (
            "You are a social media and company specific news researcher/analyst tasked with analyzing social media posts, recent company news, and public sentiment for a specific company over the past week. You will be given a company's name your objective is to write a comprehensive long report detailing your analysis, insights, and implications for traders and investors on this company's current state after looking at social media and what people are saying about that company, analyzing sentiment data of what people feel each day about the company, and looking at recent company news. Try to look at all sources possible from social media to sentiment to news. Do not simply state the trends are mixed, provide detailed and finegrained analysis and insights that may help traders make decisions."
            + """ Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."""
            + " You are a helpful AI assistant, collaborating with other assistants."
            + " Use the provided tools to progress towards answering the question."
            + " If you are unable to fully answer, that's OK; another assistant with different tools"
            + " will help where you left off. Execute what you can to make progress."
            + " If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** or deliverable,"
            + " prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop."
            # + "Use the get_news(query,start_date, end_date) tool to search for company-specific news and social media discussions."
            + " You have access to the following tools: {tool_names}."
            + "For your reference, the current date is {current_date}. The current company we want to analyze is {ticker}"
        )
        
        # format the system_prompt
        system_prom = system_prom.format(
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
        
        # get result
        result = agent.invoke(
            input=state["messages"][0],
            )
        
        # pay attention to format:
        rep = result["messages"][-1].content
        # print(rep)

        report = ""

        if len(result["messages"][-1].tool_calls) == 0:
            report = result["messages"][-1].content

        # verify 
        # print(result)

        return {
            "messages": result["messages"],
            "sentiment_report": report,
        }

    return social_media_analyst_node

# function test for the node
# def debug_agent_state_flow():
#         # verify agentstate: init
#         print(agentstate)

#         # Create the social media analyst agent(return a func)
#         social_media_analyst_func = create_social_media_analyst(llm)

#         # Run the agent
#         social_media_analyst_func(agentstate)

#         # verify agentstate: afterwards

#         print(agentstate)

if __name__ == "__main__":
    # Import the LLM from init_llm.py
    from tradingagents.agents.init_llm import llm
    from langgraph.graph import StateGraph, START, END
    from langgraph.graph.message import add_messages

    # test langgraph design to see "append" strategy: before
    # print(len(agentstate["messages"]))

    # design pattern: agentstate -> (modified) agentstate
    # 1.workflow init
    workflow = StateGraph(AgentState)
    
    # 2.add_node
    # when defining node: follow the format "def ...(state)" is important 
    workflow.add_node("social", create_social_media_analyst(llm))
    
    # 3.define edge
    workflow.add_edge(START, "social")
    workflow.add_edge("social", END)
    
    app = workflow.compile()


    result = app.invoke(agentstate)

    # 4.get result(literally modified result)
    result = app.invoke(agentstate)
    print(result["messages"][-1].content)

    # test langgraph design to see "append" strategy: after
    # print(len(result["messages"]))

