"""
TradeSwarm 入口模块：加载配置并初始化数据管理器与数据提供者。
"""

from data_sources.akshare_provider import AkshareProvider


def main() -> None:
    """
    主函数：测试AkShare财务报表功能。
    """
    
    # 简化测试，直接实例化AkShare提供者
    config = {}
    akshare_provider = AkshareProvider(config=config)
    
    print("AkShare 数据提供者已初始化:", type(akshare_provider).__name__)
    print("\n1. 测试利润表获取（使用所有数据源）:")
    profit_result = akshare_provider.get_profit_statement("600519", "annual", 1, "all")
    print(f"利润表获取结果: {profit_result.get('actual_source', '失败')}")
    print("\n2. 测试资产负债表获取（使用所有数据源）:")
    balance_result = akshare_provider.get_balance_sheet("600519", "annual", 1, "all")
    print(f"资产负债表获取结果: {balance_result.get('actual_source', '失败')}")
    
    # 测试现金流量表获取
    print("\n3. 测试现金流量表获取（使用所有数据源）:")
    cashflow_result = akshare_provider.get_cash_flow_statement("600519", "annual", 1, "all")
    print(f"现金流量表获取结果: {cashflow_result.get('actual_source', '失败')}")
    
    # 测试东方财富数据源的一致性
    print("\n=== 测试东方财富数据源一致性 ===")
    em_profit = akshare_provider.get_profit_statement("600519", "annual", 1, "em")
    print(f"东方财富利润表: {'成功' if em_profit.get('data') else '失败'}")
    if em_profit.get('errors'):
        print(f"东方财富利润表错误: {em_profit['errors']}")
    
    em_balance = akshare_provider.get_balance_sheet("600519", "annual", 1, "em")
    print(f"东方财富资产负债表: {'成功' if em_balance.get('data') else '失败'}")
    if em_balance.get('errors'):
        print(f"东方财富资产负债表错误: {em_balance['errors']}")
    
    em_cashflow = akshare_provider.get_cash_flow_statement("600519", "annual", 1, "em")
    print(f"东方财富现金流量表: {'成功' if em_cashflow.get('data') else '失败'}")
    if em_cashflow.get('errors'):
        print(f"东方财富现金流量表错误: {em_cashflow['errors']}")

if __name__ == "__main__":
    main()