"""市场数据工具"""
import json
from typing import Optional
from langchain_core.tools import tool
from tradingagents.data_sources.tushare_provider import TushareProvider


# 全局 Tushare Provider 实例（懒加载）
_provider: Optional[TushareProvider] = None


def _get_provider() -> TushareProvider:
    """获取 Tushare Provider 实例（单例模式）"""
    global _provider
    if _provider is None:
        _provider = TushareProvider()
    return _provider


@tool
def get_stock_data(
    ts_code: str,
    start_date: str,
    end_date: str
) -> str:
    """
    获取 A 股股票的日线行情数据
    
    此工具用于获取指定股票在指定日期范围内的日线行情数据，包括开盘价、收盘价、最高价、最低价、
    成交量、成交额、涨跌幅等关键市场数据。
    
    Args:
        ts_code: 股票代码，支持以下格式：
            - '000001' (6位数字，会自动识别市场)
            - '000001.SZ' (深圳市场)
            - '600000.SH' (上海市场)
            示例：'000001' 或 '600000' 或 '000001.SZ'
        start_date: 开始日期，格式为 'YYYYMMDD' 或 'YYYY-MM-DD'
            示例：'20250101' 或 '2025-01-01'
        end_date: 结束日期，格式为 'YYYYMMDD' 或 'YYYY-MM-DD'
            示例：'20251231' 或 '2025-12-31'
    
    Returns:
        JSON 格式的字符串，包含以下字段：
        - success: 是否成功
        - message: 提示信息
        - data: 股票数据列表，每个元素包含：
            - ts_code: 股票代码
            - trade_date: 交易日期
            - open: 开盘价
            - high: 最高价
            - low: 最低价
            - close: 收盘价
            - pre_close: 昨收价
            - change: 涨跌额
            - pct_chg: 涨跌幅（%）
            - vol: 成交量（手）
            - amount: 成交额（千元）
        - summary: 数据摘要（包含数据条数、日期范围等）
    
    Examples:
        >>> get_stock_data('000001', '20250101', '20250131')
        '{"success": true, "data": [...], "summary": {...}}'
    """
    try:
        provider = _get_provider()
        df = provider.get_daily(ts_code, start_date, end_date)
        
        if df.empty:
            return json.dumps({
                "success": False,
                "message": f"未找到股票 {ts_code} 在 {start_date} 至 {end_date} 期间的数据",
                "data": [],
                "summary": {}
            }, ensure_ascii=False, indent=2)
        
        # 转换为字典列表
        data_list = df.to_dict('records')
        
        # 计算摘要信息
        summary = {
            "total_records": len(data_list),
            "date_range": {
                "start": data_list[0]['trade_date'] if data_list else None,
                "end": data_list[-1]['trade_date'] if data_list else None
            },
            "latest_price": {
                "close": float(data_list[-1]['close']) if data_list else None,
                "pct_chg": float(data_list[-1]['pct_chg']) if data_list else None
            } if data_list else None
        }
        
        # 返回 JSON 字符串
        result = {
            "success": True,
            "message": f"成功获取 {len(data_list)} 条数据",
            "data": data_list,
            "summary": summary
        }
        
        return json.dumps(result, ensure_ascii=False, indent=2, default=str)
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "message": f"获取股票数据时发生错误: {str(e)}",
            "data": [],
            "summary": {}
        }, ensure_ascii=False, indent=2)

