import time
import json
from langchain.agents import create_agent
from tradingagents.agents.utils.agent_states import AgentState

# define state
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

def create_research_manager(llm, memory):
    def research_manager_node(state) -> dict:
        # history is a dict
        history = state["investment_debate_state"].get("history", "")

        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        investment_debate_state = state["investment_debate_state"]

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
        past_memories = memory.get_memories(curr_situation, n_matches=2)

        past_memory_str = ""
        for i, rec in enumerate(past_memories, 1):
            past_memory_str += rec["recommendation"] + "\n\n"

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
        
        # get agent and invoke
        # 沿用 Chatmodel 的方法
        response = llm.invoke(prompt)

        new_investment_debate_state = {
            # agent: append strategy -> response["messages"][-1].content
            "judge_decision": response.content,

            "history": investment_debate_state.get("history", ""),
            "bear_history": investment_debate_state.get("bear_history", ""),
            "bull_history": investment_debate_state.get("bull_history", ""),

            "current_response": response.content,

            "count": investment_debate_state["count"],
        }

        return {
            "investment_debate_state": new_investment_debate_state,
            "investment_plan": response.content,
        }

    return research_manager_node

if __name__ == "__main__":
    import os
    from openai import OpenAI
    from dotenv import load_dotenv
    from langchain_openai import ChatOpenAI
    from tradingagents.agents.utils.memory import FinancialSituationMemory
    
    # 加载环境变量
    load_dotenv()
    
    # 创建 client（与你的 memory.py 代码风格一致）
    client = OpenAI(
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    
    print("=" * 80)
    print("开始测试 research_manager_node")
    print("=" * 80)
    
    # 1. 初始化 Memory
    print("\n[1/4] 初始化 Memory...")
    config = {
        "backend_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "embedding_model": "text-embedding-v4"
    }
    memory = FinancialSituationMemory(name="test_research_manager", config=config)
    
    # 添加测试用的历史记忆
    test_memories = [
        (
            "Tech sector showing positive trends with strong fundamentals and positive sentiment",
            "Previous mistake: Overly optimistic about tech stocks without considering market volatility. Should have been more cautious and diversified portfolio."
        ),
        (
            "Market showing mixed signals with positive news but concerns about fundamentals",
            "Previous mistake: Defaulted to Hold position when clear bullish signals were present. Should have taken decisive action based on strong fundamentals."
        ),
    ]
    memory.add_situations(test_memories)
    print("✓ Memory 初始化完成，已添加测试记忆")
    
    # 2. 初始化 LLM
    print("\n[2/4] 初始化 LLM...")
    llm = ChatOpenAI(
        model="qwen-plus",  # 或使用其他阿里云百炼支持的模型
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key=os.getenv("DASHSCOPE_API_KEY")
    )
    print("✓ LLM 初始化完成")
    
    # 3. 创建 research_manager_node
    print("\n[3/4] 创建 research_manager_node...")
    research_manager_node = create_research_manager(llm, memory)
    print("✓ research_manager_node 创建完成")
    
    # 4. 准备测试用的 state
    print("\n[4/4] 准备测试用的 state 并调用...")

    # 5. 调用 research_manager_node
    print("-" * 80)
    try:
        result = research_manager_node(agentstate)
        
        print("\n" + "=" * 80)
        print("测试结果:")
        print("=" * 80)
        
        # 打印 investment_plan
        print("\n【Investment Plan】")
        print("-" * 80)
        print(result.get("investment_plan", "N/A"))
        
        # 打印 investment_debate_state
        print("\n【Investment Debate State】")
        print("-" * 80)
        debate_state = result.get("investment_debate_state", {})
        print(f"Judge Decision: {debate_state.get('judge_decision', 'N/A')[:300]}...")  # 显示前300字符
        print(f"\nCount: {debate_state.get('count', 'N/A')}")
        print(f"\nHistory: {debate_state.get('history', 'N/A')[:200]}...")
        
        print("\n" + "=" * 80)
        print("✓ 测试完成！")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()