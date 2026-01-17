"""
测试 Risk Manager 节点

验证 risk_manager 节点在新 AgentState 结构下是否可以正常运行。
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

from tradingagents.agents.managers.risk_manager import create_risk_manager
from tradingagents.agents.utils.agent_states import AgentState, AnalystMemorySummary
from tradingagents.agents.utils.memory import FinancialSituationMemory

load_dotenv()


def create_test_state() -> AgentState:
    """创建测试用的 AgentState"""
    demo_summary: AnalystMemorySummary = {
        "today_report": "市场整体呈现上涨趋势，银行板块表现稳健。技术指标显示向上动能，成交量支撑良好。",
        "history_report": "过去一周银行板块持续走强，市场对银行股信心增强。",
    }

    return {
        "company_of_interest": "000001",
        "trade_date": "2024-12-07",
        "trade_timestamp": "2024-12-07 10:00:00",
        "market_analyst_summary": demo_summary,
        "news_analyst_summary": {
            "today_report": "近期新闻显示，平安银行在零售业务转型方面取得积极进展。分析师基于强劲的资产质量改善预期，上调了目标价。",
            "history_report": "过去一周银行业新闻整体偏正面，监管政策支持银行发展。",
        },
        "sentiment_analyst_summary": {
            "today_report": "社交媒体情绪对平安银行整体偏正面，投资者对银行数字化转型和零售业务增长持乐观态度。",
            "history_report": "过去一周市场情绪持续改善，投资者对银行股关注度提升。",
        },
        "fundamentals_analyst_summary": {
            "today_report": "平安银行财务基本面保持稳健，营收持续增长。资产质量持续改善，不良贷款率下降，资本充足率保持在合理水平。",
            "history_report": "过去一个月基本面持续改善，ROE 和 ROA 指标稳步提升。",
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


def main():
    """主测试函数"""
    print("=" * 80)
    print("测试 Risk Manager 节点")
    print("=" * 80)

    # 1. 初始化 Memory
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
    print("[OK] Memory 初始化完成，已添加测试记忆")

    # 2. 初始化 LLM
    print("\n[2/4] 初始化 LLM...")
    llm = ChatOpenAI(
        model="qwen-plus",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key=os.getenv("DASHSCOPE_API_KEY"),
    )
    print("[OK] LLM 初始化完成")

    # 3. 创建 risk_manager_node
    print("\n[3/4] 创建 risk_manager_node...")
    risk_manager_node = create_risk_manager(llm, memory)
    print("[OK] risk_manager_node 创建完成")

    # 4. 准备测试用的 state 并调用
    print("\n[4/4] 准备测试用的 AgentState 并调用...")
    test_state = create_test_state()

    print("-" * 80)
    try:
        result = risk_manager_node(test_state)

        print("\n" + "=" * 80)
        print("测试结果:")
        print("=" * 80)

        # 打印 final_trade_decision
        print("\n【Final Trade Decision】")
        print("-" * 80)
        final_decision = result.get("final_trade_decision", "N/A")
        print(final_decision[:500] if isinstance(final_decision, str) else final_decision)

        # 打印 risk_summary
        print("\n【Risk Summary】")
        print("-" * 80)
        risk_summary = result.get("risk_summary", {})
        if risk_summary:
            risk_state = risk_summary.get("risk_debate_state", {})
            print(f"Judge Decision: {risk_state.get('judge_decision', 'N/A')[:300]}...")
            print(f"\nCount: {risk_state.get('count', 'N/A')}")
            print(f"\nLatest Speaker: {risk_state.get('latest_speaker', 'N/A')}")
            print(f"\nHistory: {risk_state.get('history', 'N/A')[:200]}...")
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

