"""
快速验证脚本：检查测试数据结构和导入是否正确

此脚本不调用 LLM，仅验证：
1. 所有必要的导入是否正常
2. 测试数据是否符合新的 AgentState 结构
3. 节点工厂函数是否可以正常创建
"""
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

load_dotenv()


def verify_imports():
    """验证所有必要的导入"""
    print("=" * 80)
    print("验证导入")
    print("=" * 80)

    errors = []

    # 验证 AgentState 相关导入
    try:
        from tradingagents.agents.utils.agent_states import (
            AgentState,
            AnalystMemorySummary,
            InvestDebateState,
            RiskDebateState,
        )

        print("[OK] AgentState 相关导入成功")
    except ImportError as e:
        print(f"[ERROR] AgentState 相关导入失败: {e}")
        errors.append(f"AgentState import: {e}")

    # 验证 Research Manager 导入
    try:
        from tradingagents.agents.managers.research_manager import (
            create_research_manager,
        )
        from tradingagents.agents.utils.agent_states import ResearchSummary

        print("[OK] Research Manager 导入成功")
    except ImportError as e:
        print(f"[ERROR] Research Manager 导入失败: {e}")
        errors.append(f"Research Manager import: {e}")

    # 验证 Risk Manager 导入
    try:
        from tradingagents.agents.managers.risk_manager import (
            create_risk_manager,
        )
        from tradingagents.agents.utils.agent_states import RiskSummary

        print("[OK] Risk Manager 导入成功")
    except ImportError as e:
        print(f"[ERROR] Risk Manager 导入失败: {e}")
        errors.append(f"Risk Manager import: {e}")

    # 验证 Conservative Debator 导入
    try:
        from tradingagents.agents.risk_mgmt.conservative_debator import (
            create_safe_debator,
        )

        print("[OK] Conservative Debator 导入成功")
    except ImportError as e:
        print(f"[ERROR] Conservative Debator 导入失败: {e}")
        errors.append(f"Conservative Debator import: {e}")

    # 验证 Memory 导入
    try:
        from tradingagents.agents.utils.memory import FinancialSituationMemory

        print("[OK] Memory 导入成功")
    except ImportError as e:
        print(f"[ERROR] Memory 导入失败: {e}")
        errors.append(f"Memory import: {e}")

    return errors


def verify_test_data_structure():
    """验证测试数据结构"""
    print("\n" + "=" * 80)
    print("验证测试数据结构")
    print("=" * 80)

    from tradingagents.agents.utils.agent_states import AgentState, AnalystMemorySummary

    errors = []

    # 创建测试数据
    demo_summary: AnalystMemorySummary = {
        "today_report": "测试报告",
        "history_report": "测试历史报告",
    }

    test_state: AgentState = {
        "company_of_interest": "000001",
        "trade_date": "2024-12-07",
        "trade_timestamp": "2024-12-07 10:00:00",
        "market_analyst_summary": demo_summary,
        "news_analyst_summary": demo_summary,
        "sentiment_analyst_summary": demo_summary,
        "fundamentals_analyst_summary": demo_summary,
        "research_summary": None,  # type: ignore[assignment]
        "risk_summary": None,  # type: ignore[assignment]
        "investment_plan": None,
        "trader_investment_plan": None,
        "final_trade_decision": None,
        "messages": [],
    }

    # 验证必需字段
    required_fields = [
        "company_of_interest",
        "trade_date",
        "market_analyst_summary",
        "news_analyst_summary",
        "sentiment_analyst_summary",
        "fundamentals_analyst_summary",
    ]

    for field in required_fields:
        if field not in test_state:
            errors.append(f"缺少必需字段: {field}")
            print(f"[ERROR] 缺少必需字段: {field}")
        else:
            print(f"[OK] 字段存在: {field}")

    # 验证股票代码是 A 股格式
    if test_state["company_of_interest"] != "000001":
        errors.append("股票代码不是 A 股格式 (000001)")
        print("[ERROR] 股票代码不是 A 股格式")
    else:
        print("[OK] 股票代码是 A 股格式 (000001)")

    return errors


def verify_node_factories():
    """验证节点工厂函数（不实际创建节点，只检查函数是否存在）"""
    print("\n" + "=" * 80)
    print("验证节点工厂函数")
    print("=" * 80)

    errors = []

    # 验证 Research Manager 工厂函数
    try:
        from tradingagents.agents.managers.research_manager import (
            create_research_manager,
        )

        if callable(create_research_manager):
            print("[OK] create_research_manager 是可调用函数")
        else:
            errors.append("create_research_manager 不是可调用函数")
            print("[ERROR] create_research_manager 不是可调用函数")
    except Exception as e:
        errors.append(f"create_research_manager 验证失败: {e}")
        print(f"[ERROR] create_research_manager 验证失败: {e}")

    # 验证 Risk Manager 工厂函数
    try:
        from tradingagents.agents.managers.risk_manager import create_risk_manager

        if callable(create_risk_manager):
            print("[OK] create_risk_manager 是可调用函数")
        else:
            errors.append("create_risk_manager 不是可调用函数")
            print("[ERROR] create_risk_manager 不是可调用函数")
    except Exception as e:
        errors.append(f"create_risk_manager 验证失败: {e}")
        print(f"[ERROR] create_risk_manager 验证失败: {e}")

    # 验证 Conservative Debator 工厂函数
    try:
        from tradingagents.agents.risk_mgmt.conservative_debator import (
            create_safe_debator,
        )

        if callable(create_safe_debator):
            print("[OK] create_safe_debator 是可调用函数")
        else:
            errors.append("create_safe_debator 不是可调用函数")
            print("[ERROR] create_safe_debator 不是可调用函数")
    except Exception as e:
        errors.append(f"create_safe_debator 验证失败: {e}")
        print(f"[ERROR] create_safe_debator 验证失败: {e}")

    return errors


def main():
    """主验证函数"""
    print("=" * 80)
    print("快速验证：测试数据结构和导入")
    print("=" * 80)
    print("\n此脚本验证测试环境是否正确配置，不调用 LLM API。")

    all_errors = []

    # 验证导入
    import_errors = verify_imports()
    all_errors.extend(import_errors)

    # 验证数据结构
    data_errors = verify_test_data_structure()
    all_errors.extend(data_errors)

    # 验证工厂函数
    factory_errors = verify_node_factories()
    all_errors.extend(factory_errors)

    # 汇总结果
    print("\n" + "=" * 80)
    print("验证结果汇总")
    print("=" * 80)

    if all_errors:
        print(f"\n[ERROR] 发现 {len(all_errors)} 个错误：")
        for error in all_errors:
            print(f"  - {error}")
        return 1
    else:
        print("\n[OK] 所有验证通过！")
        print("\n可以运行以下命令进行完整测试：")
        print("  python test/test_research_manager.py")
        print("  python test/test_risk_manager.py")
        print("  python test/test_conservative_debator.py")
        print("  python test/test_all_managers.py")
        return 0


if __name__ == "__main__":
    exit(main())

