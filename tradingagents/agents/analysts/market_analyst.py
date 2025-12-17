from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import time
import json
from tradingagents.agents.utils.agent_states import AgentState
from langchain.agents import create_agent
from tradingagents.tools.market_tools import get_stock_data
from tradingagents.tools.technical_tools import get_indicators


# agentstate def
## 测试用例state
agentstate = AgentState(
    company_of_interest="000001",
    trade_date="2025-12-11",
    sender="market_analyst",
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
    messages=[{"role": "user", "content": "开始对平安银行（000001）进行详细的市场指标分析。"}]
)


# langgraph node def
def create_market_analyst(llm) -> dict:
    def market_analyst_node(state) -> dict:
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]

        # 工具列表
        tools = [
            get_stock_data,
            get_indicators,
        ]

        # system prompt
        system_prom = (
            "你是一位专业的市场分析师，负责选择和分析金融指标来评估股票当前的市场状况。"
            "你需要基于市场数据、技术指标和波动性信号撰写一份详细的分析报告。"
            "从可用的工具中选择合适的指标，避免冗余，并对每个指标给出细致的解读。"
            "在报告末尾附加一个 Markdown 表格来总结分析结果。"
            "你是一个有用的 AI 助手，与其他助手协作。"
            "使用提供的工具来推进问题的解答。"
            "如果你无法完全回答，其他助手会继续。"
            "如果你或任何其他助手有最终交易建议：**买入/持有/卖出**，"
            "请在回复前加上相应前缀，以便团队知道停止。"
            "重要提示："
            "1. 你可以使用历史数据进行趋势分析和技术指标分析，这是完全合理的。"
            "2. 但是，当描述'当前'、'最新'、'现在'、'目前'等表示当前状态的信息时，"
            "   必须使用数据中最新交易日（trade_date最大）的收盘价和指标值。"
            "3. 在分析中明确说明使用的数据日期范围，例如'分析期间为YYYYMMDD至YYYYMMDD'，"
            "   并在描述当前状态时明确标注'截至YYYYMMDD'或'最新交易日为YYYYMMDD'。"
            "4. 区分历史分析和当前状态描述："
            "   - 历史分析：可以使用所有历史数据，描述趋势、变化等"
            "   - 当前状态：必须使用最新交易日的数据，如'当前股价'、'最新收盘价'、'当前MA5值'等"
            "5. 如果数据中有多个交易日，描述'当前'时必须使用最后一个交易日的数据。"
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
            last_message = {"role": "user", "content": f"分析股票 {ticker} 的市场数据"}
        else:
            last_message = state["messages"][-1]
        
        result = agent.invoke(
            input=last_message,
        )

        # 提取最后一条 AI 消息内容（跳过工具调用消息）
        market_report = ""
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
                    market_report = msg.content
                    break
        
        if not market_report and result["messages"]:
            last_msg = result["messages"][-1]
            if hasattr(last_msg, 'content') and last_msg.content:
                market_report = last_msg.content

        return {
            "messages": result["messages"],     # append strategy
            "market_report": market_report,
        }

    return market_analyst_node


# main test
if __name__ == "__main__":
    from tradingagents.agents.init_llm import llm
    from langgraph.graph import StateGraph, START, END

    # 1.workflow init
    workflow = StateGraph(AgentState)

    # 2.add_node
    workflow.add_node("market", create_market_analyst(llm))

    # 3.define edges
    workflow.add_edge(START, "market")
    workflow.add_edge("market", END)

    app = workflow.compile()

    # 4.invoke graph to get result
    result = app.invoke(agentstate)

    # print last agent reply
    print(result["messages"][-1].content)
