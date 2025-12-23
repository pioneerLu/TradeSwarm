"""
TradeSwarm 入口模块：加载配置并初始化数据管理器与数据提供者。
"""

import pandas as pd
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

    # 获取宏观新闻数据
    print("\n=== 获取宏观市场数据 ===")
    
    # 1. 获取宏观新闻
    print("\n1. 获取宏观新闻...")
    macro_news_result = akshare_provider.get_macro_news(source="all", limit=10)
    print(f"更新时间: {macro_news_result.get('update_time', 'N/A')}")
    print(f"实际数据源: {macro_news_result.get('actual_sources', [])}")
    
    macro_news_df = macro_news_result.get('data', pd.DataFrame())
    if not macro_news_df.empty:
        print(f"\n宏观新闻 (共{len(macro_news_df)}条):")
        for idx, (_, row) in enumerate(macro_news_df.iterrows(), 1):
            title = row.get('title', '无标题')
            source = row.get('data_source', '未知来源')
            print(f"{idx}. {title} (来源: {source})")
    else:
        print("未获取到宏观新闻")
    
    if macro_news_result.get('errors'):
        print(f"错误信息: {macro_news_result.get('errors')}")
    
    # 2. 获取北向资金流向
    print("\n2. 获取北向资金流向...")
    money_flow_result = akshare_provider.get_northbound_money_flow()
    print(f"更新时间: {money_flow_result.get('update_time', 'N/A')}")
    
    money_flow = money_flow_result.get('data', {})
    if money_flow:
        print(f"\n北向资金:")
        print(f"状态: {money_flow.get('flow_status', 'N/A')}")
        print(f"金额: {money_flow.get('value', 'N/A')}")
        print(f"日期: {money_flow.get('date', 'N/A')}")
    else:
        print("未获取到北向资金数据")
    
    if money_flow_result.get('errors'):
        print(f"错误信息: {money_flow_result.get('errors')}")
    
    # 3. 获取核心指数表现
    print("\n3. 获取核心指数表现...")
    indices_result = akshare_provider.get_global_indices_performance()
    print(f"更新时间: {indices_result.get('update_time', 'N/A')}")
    
    indices_df = indices_result.get('data', pd.DataFrame())
    if not indices_df.empty:
        print(f"\n核心指数表现 (共{len(indices_df)}条):")
        print(indices_df[['asset', 'code', 'price', 'change']].to_string(index=False))
    else:
        print("未获取到核心指数数据")
    
    if indices_result.get('errors'):
        print(f"错误信息: {indices_result.get('errors')}")
    
    # 4. 获取汇率信息
    print("\n4. 获取汇率信息...")
    currency_result = akshare_provider.get_currency_exchange_rate()
    print(f"更新时间: {currency_result.get('update_time', 'N/A')}")
    
    currency = currency_result.get('data', {})
    if currency:
        print(f"\n汇率信息:")
        print(f"货币对: {currency.get('currency_pair', 'N/A')}")
        print(f"汇率: {currency.get('description', 'N/A')}")
    else:
        print("未获取到汇率数据")
    
    if currency_result.get('errors'):
        print(f"错误信息: {currency_result.get('errors')}")

    # 插入宏观市场数据到数据库
    print("\n=== 插入宏观市场数据到数据库 ===")
    
    # 插入宏观新闻
    print("\n1. 插入宏观新闻...")
    success = data_manager.insert_financial_data(macro_news_result, "macro_news")
    print(f"宏观新闻插入结果: {'成功' if success else '失败'}")
    
    # 插入北向资金流向
    print("\n2. 插入北向资金流向...")
    success = data_manager.insert_financial_data(money_flow_result, "northbound_money_flow")
    print(f"北向资金流向插入结果: {'成功' if success else '失败'}")
    
    # 插入核心指数表现
    print("\n3. 插入核心指数表现...")
    success = data_manager.insert_financial_data(indices_result, "global_indices")
    print(f"核心指数表现插入结果: {'成功' if success else '失败'}")
    
    # 插入汇率信息
    print("\n4. 插入汇率信息...")
    success = data_manager.insert_financial_data(currency_result, "currency_exchange_rates")
    print(f"汇率信息插入结果: {'成功' if success else '失败'}")
    
    # 查询刚插入的宏观市场数据
    print("\n=== 查询宏观市场数据 ===")
    
    # 查询宏观新闻（最近5条）
    print("\n1. 查询宏观新闻（最近5条）...")
    news_results = data_manager.query_financial_data(table_name="macro_news", limit=5)
    print(f"找到 {len(news_results)} 条宏观新闻记录:")
    for idx, result in enumerate(news_results, 1):
        title = result.get('title', '无标题')
        data_source = result.get('data_source', '未知来源')
        print(f"{idx}. {title} (来源: {data_source})")
    
    # 查询北向资金流向（最近1条）
    print("\n2. 查询北向资金流向（最近1条）...")
    money_flow_results = data_manager.query_financial_data(table_name="northbound_money_flow", limit=1)
    if money_flow_results:
        result = money_flow_results[0]
        print(f"北向资金流向记录:")
        print(f"状态: {result.get('flow_status', 'N/A')}")
        print(f"金额: {result.get('value', 'N/A')}")
        print(f"日期: {result.get('date', 'N/A')}")
        print(f"创建时间: {result.get('created_at', 'N/A')}")
    else:
        print("未找到北向资金流向记录")
    
    # 查询核心指数表现（最近5条）
    print("\n3. 查询核心指数表现（最近5条）...")
    indices_results = data_manager.query_financial_data(table_name="global_indices", limit=5)
    print(f"找到 {len(indices_results)} 条核心指数记录:")
    for idx, result in enumerate(indices_results, 1):
        asset = result.get('asset', 'N/A')
        code = result.get('code', 'N/A')
        price = result.get('price', 'N/A')
        change = result.get('change', 'N/A')
        print(f"{idx}. {asset}({code}) - {price} - {change}")
    
    # 查询汇率信息（最近1条）
    print("\n4. 查询汇率信息（最近1条）...")
    currency_results = data_manager.query_financial_data(table_name="currency_exchange_rates", limit=1)
    if currency_results:
        result = currency_results[0]
        print(f"汇率信息记录:")
        print(f"货币对: {result.get('currency_pair', 'N/A')}")
        print(f"汇率: {result.get('price', 'N/A')}")
        print(f"涨跌幅: {result.get('change', 'N/A')}")
        print(f"创建时间: {result.get('created_at', 'N/A')}")
    else:
        print("未找到汇率信息记录")


if __name__ == "__main__":
    main()