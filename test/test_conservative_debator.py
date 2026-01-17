"""
测试 Conservative Debator (Safe Debator) 节点

验证 conservative_debator 节点在新 AgentState 结构下是否可以正常运行。
"""
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from openai import OpenAI

from tradingagents.agents.risk_mgmt.conservative_debator import create_safe_debator
from tradingagents.agents.utils.agent_states import AgentState, AnalystMemorySummary

load_dotenv()


def create_test_state() -> AgentState:
    """创建测试用的 AgentState"""
    demo_summary: AnalystMemorySummary = {
        "today_report": "市场整体呈现上涨趋势，银行板块表现稳健。",
        "history_report": "过去一周银行板块持续走强。",
    }

    return {
        "company_of_interest": "000001",
        "trade_date": "2024-12-07",
        "trade_timestamp": "2024-12-07 10:00:00",
        "market_analyst_summary": demo_summary,
        "news_analyst_summary": {
            "today_report": "近期新闻显示，平安银行在零售业务转型方面取得积极进展。",
            "history_report": "过去一周银行业新闻整体偏正面。",
        },
        "sentiment_analyst_summary": {
            "today_report": "社交媒体情绪对平安银行整体偏正面，投资者对银行数字化转型持乐观态度。",
            "history_report": "过去一周市场情绪持续改善。",
        },
        "fundamentals_analyst_summary": {
            "today_report": "平安银行财务基本面保持稳健，营收持续增长，资产质量持续改善。",
            "history_report": "过去一个月基本面持续改善。",
        },
        "research_summary": {
            "investment_plan": "监控市场情绪变化，适时调整仓位。考虑到基本面强劲，可考虑适度增加仓位。",
        },
        "risk_summary": {
            "risk_debate_state": {
                "risky_history": "由于市场地位稳固，可承受较高风险。",
                "safe_history": "考虑到市场波动性，建议采取保守策略。",
                "neutral_history": "平衡风险和机会的视角。",
                "history": "风险评估正在进行中，存在多种观点。",
                "latest_speaker": "risk_analyst",
                "current_risky_response": "在计算风险的前提下，存在高回报潜力。",
                "current_safe_response": "",
                "current_neutral_response": "采取适度风险策略，定期监控。",
                "judge_decision": "等待最终风险评估。",
                "count": 1,
            },
        },
        "investment_plan": None,
        "trader_investment_plan": None,
        "final_trade_decision": None,
        "messages": [],
    }


def main():
    """主测试函数"""
    print("=" * 80)
    print("测试 Conservative Debator (Safe Debator) 节点")
    print("=" * 80)

    # 1. 初始化 LLM
    print("\n[1/3] 初始化 LLM...")
    llm = ChatOpenAI(
        model="qwen-plus",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key=os.getenv("DASHSCOPE_API_KEY"),
    )
    print("[OK] LLM 初始化完成")

    # 2. 创建 safe_debator_node
    print("\n[2/3] 创建 safe_debator_node...")
    safe_debator_node = create_safe_debator(llm)
    print("[OK] safe_debator_node 创建完成")

    # 3. 准备测试用的 state 并调用
    print("\n[3/3] 准备测试用的 AgentState 并调用...")
    test_state = create_test_state()

    print("-" * 80)
    try:
        result = safe_debator_node(test_state)

        print("\n" + "=" * 80)
        print("测试结果:")
        print("=" * 80)

        # 打印 risk_summary
        print("\n【Risk Summary】")
        print("-" * 80)
        risk_summary = result.get("risk_summary", {})
        if risk_summary:
            risk_debate_state = risk_summary.get("risk_debate_state", {})
            print(f"Latest Speaker: {risk_debate_state.get('latest_speaker', 'N/A')}")
            print(f"Count: {risk_debate_state.get('count', 'N/A')}")
            print(f"\nCurrent Safe Response:")
            safe_response = risk_debate_state.get("current_safe_response", "N/A")
            print(f"{safe_response[:500]}..." if isinstance(safe_response, str) and len(safe_response) > 500 else safe_response)
            print(f"\nSafe History:")
            safe_history = risk_debate_state.get("safe_history", "N/A")
            print(f"{safe_history[:300]}..." if isinstance(safe_history, str) and len(safe_history) > 300 else safe_history)
            print(f"\nHistory:")
            history = risk_debate_state.get("history", "N/A")
            print(f"{history[:300]}..." if isinstance(history, str) and len(history) > 300 else history)
        else:
            print("N/A")

        print("\n" + "=" * 80)
        print("[OK] 测试完成！")
        print("=" * 80)

    except Exception as e:
        print(f"\n[ERROR] 测试失败: {str(e)}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())

