
from langchain_core.messages import AIMessage
import time
import json
from tradingagents.agents.utils.agent_states import AgentState


# agentstate def
agentstate = AgentState(
    company_of_interest="AAPL",
    trade_date="2025-12-07",
    sender="conservative_debator",
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
    trader_investment_plan="Monitor sentiment changes and adjust positions accordingly. Consider aggressive position sizing given strong fundamentals.",
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
    messages=[{"role": "user", "content": "Start a detailed risk assessment analysis for Apple Inc. (AAPL)."}]
)


def create_safe_debator(llm):
    def safe_node(state) -> dict:
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        safe_history = risk_debate_state.get("safe_history", "")

        current_risky_response = risk_debate_state.get("current_risky_response", "")
        current_neutral_response = risk_debate_state.get("current_neutral_response", "")

        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        trader_decision = state["trader_investment_plan"]

        prompt = f"""As the Safe/Conservative Risk Analyst, your primary objective is to protect assets, minimize volatility, and ensure steady, reliable growth. You prioritize stability, security, and risk mitigation, carefully assessing potential losses, economic downturns, and market volatility. When evaluating the trader's decision or plan, critically examine high-risk elements, pointing out where the decision may expose the firm to undue risk and where more cautious alternatives could secure long-term gains. Here is the trader's decision:

{trader_decision}

Your task is to actively counter the arguments of the Risky and Neutral Analysts, highlighting where their views may overlook potential threats or fail to prioritize sustainability. Respond directly to their points, drawing from the following data sources to build a convincing case for a low-risk approach adjustment to the trader's decision:

Market Research Report: {market_research_report}
Social Media Sentiment Report: {sentiment_report}
Latest World Affairs Report: {news_report}
Company Fundamentals Report: {fundamentals_report}
Here is the current conversation history: {history} Here is the last response from the risky analyst: {current_risky_response} Here is the last response from the neutral analyst: {current_neutral_response}. If there are no responses from the other viewpoints, do not halluncinate and just present your point.

Engage by questioning their optimism and emphasizing the potential downsides they may have overlooked. Address each of their counterpoints to showcase why a conservative stance is ultimately the safest path for the firm's assets. Focus on debating and critiquing their arguments to demonstrate the strength of a low-risk strategy over their approaches. Output conversationally as if you are speaking without any special formatting."""

        response = llm.invoke(prompt)

        argument = f"Safe Analyst: {response.content}"

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "risky_history": risk_debate_state.get("risky_history", ""),
            "safe_history": safe_history + "\n" + argument,
            "neutral_history": risk_debate_state.get("neutral_history", ""),
            "latest_speaker": "Safe",
            "current_risky_response": risk_debate_state.get(
                "current_risky_response", ""
            ),
            "current_safe_response": argument,
            "current_neutral_response": risk_debate_state.get(
                "current_neutral_response", ""
            ),
            "count": risk_debate_state["count"] + 1,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return safe_node


if __name__ == "__main__":
    import os
    from openai import OpenAI
    from dotenv import load_dotenv
    from langchain_openai import ChatOpenAI
    
    # 加载环境变量
    load_dotenv()
    
    # 创建 client（与你的 memory.py 代码风格一致）
    client = OpenAI(
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    
    print("=" * 80)
    print("开始测试 conservative_debator_node (safe_debator)")
    print("=" * 80)
    
    # 1. 初始化 LLM
    print("\n[1/3] 初始化 LLM...")
    llm = ChatOpenAI(
        model="qwen-plus",  # 或使用其他阿里云百炼支持的模型
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key=os.getenv("DASHSCOPE_API_KEY")
    )
    print("✓ LLM 初始化完成")
    
    # 2. 创建 safe_debator_node
    print("\n[2/3] 创建 safe_debator_node...")
    safe_debator_node = create_safe_debator(llm)
    print("✓ safe_debator_node 创建完成")
    
    # 3. 准备测试用的 state 并调用
    print("\n[3/3] 准备测试用的 state 并调用...")
    print("-" * 80)
    
    try:
        result = safe_debator_node(agentstate)
        
        print("\n" + "=" * 80)
        print("测试结果:")
        print("=" * 80)
        
        # 打印 risk_debate_state
        print("\n【Risk Debate State】")
        print("-" * 80)
        risk_debate_state = result.get("risk_debate_state", {})
        print(f"Latest Speaker: {risk_debate_state.get('latest_speaker', 'N/A')}")
        print(f"Count: {risk_debate_state.get('count', 'N/A')}")
        print(f"\nCurrent Safe Response:")
        print(f"{risk_debate_state.get('current_safe_response', 'N/A')[:500]}...")  # 显示前500字符
        print(f"\nSafe History:")
        print(f"{risk_debate_state.get('safe_history', 'N/A')[:300]}...")  # 显示前300字符
        print(f"\nHistory:")
        print(f"{risk_debate_state.get('history', 'N/A')[:300]}...")  # 显示前300字符
        
        print("\n" + "=" * 80)
        print("✓ 测试完成！")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
