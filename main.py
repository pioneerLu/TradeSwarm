"""
TradeSwarm 入口模块：加载配置并初始化数据管理器与数据提供者。
"""

from data_sources.akshare_provider import AkshareProvider
from data_manager.data_manager import DataManager


def main() -> None:
    """
    主函数：测试AkShare财务报表功能并插入数据库。
    
    实现流程:
        1. 初始化数据提供者和管理器
        2. 获取三大财务报表数据
        3. 创建数据库表
        4. 插入财务数据到数据库
        5. 验证插入结果
    """
    # 初始化配置
    config = {
        "storage": {
            "sqlite_path": "data/tradeswarm.db",
            "chroma_persist_directory": "data/chroma",
            "chroma_collection": "financial_data"
        }
    }
    
    # 初始化组件
    akshare_provider = AkshareProvider(config=config)
    data_manager = DataManager(config)
    
    # 获取财务数据
    symbol = "600519"  # 贵州茅台
    profit_result = akshare_provider.get_profit_statement(symbol, "annual", 1, "all")
    balance_result = akshare_provider.get_balance_sheet(symbol, "annual", 1, "all")
    cashflow_result = akshare_provider.get_cash_flow_statement(symbol, "annual", 1, "all")
    
    # 创建数据库表
    data_manager.create_tables()
    
    # 插入财务数据
    data_manager.insert_financial_data(profit_result, "profit_statements")
    data_manager.insert_financial_data(balance_result, "balance_sheets")
    data_manager.insert_financial_data(cashflow_result, "cash_flow_statements")
    
    # 验证插入结果
    results = data_manager.query_financial_data(symbol=symbol, report_period="2024")
    for result in results:
        table_name = result.get('table_name')
        symbol = result.get('symbol')
        period = result.get('report_period')
        data_source = result.get('data_source')
        
        # 根据不同表类型显示关键字段
        if table_name == "profit_statements":
            net_profit = result.get('net_profit')
            total_revenue = result.get('total_revenue')
        elif table_name == "balance_sheets":
            total_assets = result.get('total_assets')
            total_equity = result.get('total_equity')
        elif table_name == "cash_flow_statements":
            operating_cash = result.get('operating_cash_flow')
            net_cash_increase = result.get('net_cash_increase')


if __name__ == "__main__":
    main()