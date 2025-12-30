"""技术指标工具"""
import json
import pandas as pd
import numpy as np
from typing import List, Optional, Dict, Any
from langchain_core.tools import tool
from datasources.data_sources.tushare_provider import TushareProvider
from utils.data_utils import normalize_stock_code, format_date
from utils.config_loader import load_config


# 全局 Tushare Provider 实例（懒加载）
_provider: Optional[TushareProvider] = None


def _get_provider() -> TushareProvider:
    """获取 Tushare Provider 实例（单例模式）"""
    global _provider
    if _provider is None:
        config = load_config()
        _provider = TushareProvider(config)
    return _provider


def _calculate_ma(data: pd.Series, period: int) -> pd.Series:
    """计算移动平均线（MA）"""
    return data.rolling(window=period).mean()


def _calculate_ema(data: pd.Series, period: int) -> pd.Series:
    """计算指数移动平均线（EMA）"""
    return data.ewm(span=period, adjust=False).mean()


def _calculate_rsi(data: pd.Series, period: int = 14) -> pd.Series:
    """计算相对强弱指标（RSI）"""
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def _calculate_macd(
    data: pd.Series,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9
) -> Dict[str, pd.Series]:
    """计算 MACD 指标"""
    ema_fast = _calculate_ema(data, fast_period)
    ema_slow = _calculate_ema(data, slow_period)
    macd_line = ema_fast - ema_slow
    signal_line = _calculate_ema(macd_line, signal_period)
    histogram = macd_line - signal_line
    
    return {
        'macd': macd_line,
        'signal': signal_line,
        'histogram': histogram
    }


def _calculate_boll(
    data: pd.Series,
    period: int = 20,
    num_std: float = 2.0
) -> Dict[str, pd.Series]:
    """计算布林带（BOLL）"""
    ma = _calculate_ma(data, period)
    std = data.rolling(window=period).std()
    upper = ma + (std * num_std)
    lower = ma - (std * num_std)
    
    return {
        'upper': upper,
        'middle': ma,
        'lower': lower
    }


def _calculate_kdj(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 9
) -> Dict[str, pd.Series]:
    """计算 KDJ 指标"""
    low_min = low.rolling(window=period).min()
    high_max = high.rolling(window=period).max()
    rsv = (close - low_min) / (high_max - low_min) * 100
    
    k = rsv.ewm(com=2, adjust=False).mean()
    d = k.ewm(com=2, adjust=False).mean()
    j = 3 * k - 2 * d
    
    return {
        'k': k,
        'd': d,
        'j': j
    }


def _calculate_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """计算能量潮指标（OBV）"""
    obv = (np.sign(close.diff()) * volume).fillna(0).cumsum()
    return obv


def _calculate_indicators(
    df: pd.DataFrame,
    indicators: List[str],
    **kwargs
) -> pd.DataFrame:
    """
    计算技术指标
    
    Args:
        df: 包含股票数据的 DataFrame（必须包含 close, high, low, vol 等列）
        indicators: 要计算的指标列表，支持：
            - 'MA': 移动平均线（需要 period 参数，默认 5, 10, 20, 30, 60）
            - 'EMA': 指数移动平均线（需要 period 参数，默认 12, 26）
            - 'RSI': 相对强弱指标（需要 period 参数，默认 14）
            - 'MACD': MACD 指标（需要 fast_period, slow_period, signal_period，默认 12, 26, 9）
            - 'BOLL': 布林带（需要 period, num_std 参数，默认 20, 2.0）
            - 'KDJ': KDJ 指标（需要 period 参数，默认 9）
            - 'OBV': 能量潮指标
        **kwargs: 指标参数
    
    Returns:
        包含原始数据和技术指标的 DataFrame
    """
    result_df = df.copy()
    close = df['close']
    high = df['high'] if 'high' in df.columns else close
    low = df['low'] if 'low' in df.columns else close
    volume = df['vol'] if 'vol' in df.columns else pd.Series([0] * len(df), index=df.index)
    
    for indicator in indicators:
        indicator = indicator.upper()
        
        if indicator == 'MA':
            # 移动平均线，支持多个周期
            periods = kwargs.get('ma_periods', [5, 10, 20, 30, 60])
            if isinstance(periods, (int, float)):
                periods = [int(periods)]
            for period in periods:
                result_df[f'MA{period}'] = _calculate_ma(close, int(period))
        
        elif indicator == 'EMA':
            # 指数移动平均线
            periods = kwargs.get('ema_periods', [12, 26])
            if isinstance(periods, (int, float)):
                periods = [int(periods)]
            for period in periods:
                result_df[f'EMA{period}'] = _calculate_ema(close, int(period))
        
        elif indicator == 'RSI':
            # 相对强弱指标
            period = kwargs.get('rsi_period', 14)
            result_df['RSI'] = _calculate_rsi(close, int(period))
        
        elif indicator == 'MACD':
            # MACD 指标
            fast = kwargs.get('macd_fast', 12)
            slow = kwargs.get('macd_slow', 26)
            signal = kwargs.get('macd_signal', 9)
            macd_data = _calculate_macd(close, int(fast), int(slow), int(signal))
            result_df['MACD'] = macd_data['macd']
            result_df['MACD_Signal'] = macd_data['signal']
            result_df['MACD_Hist'] = macd_data['histogram']
        
        elif indicator == 'BOLL':
            # 布林带
            period = kwargs.get('boll_period', 20)
            num_std = kwargs.get('boll_std', 2.0)
            boll_data = _calculate_boll(close, int(period), float(num_std))
            result_df['BOLL_Upper'] = boll_data['upper']
            result_df['BOLL_Middle'] = boll_data['middle']
            result_df['BOLL_Lower'] = boll_data['lower']
        
        elif indicator == 'KDJ':
            # KDJ 指标
            period = kwargs.get('kdj_period', 9)
            kdj_data = _calculate_kdj(high, low, close, int(period))
            result_df['KDJ_K'] = kdj_data['k']
            result_df['KDJ_D'] = kdj_data['d']
            result_df['KDJ_J'] = kdj_data['j']
        
        elif indicator == 'OBV':
            # 能量潮指标
            result_df['OBV'] = _calculate_obv(close, volume)
    
    return result_df


@tool
def get_indicators(
    ts_code: str,
    indicators: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    period: Optional[int] = None
) -> str:
    """
    获取 A 股股票的技术指标数据
    
    此工具用于计算指定股票的技术指标，支持多种常用技术指标的计算，包括移动平均线、
    相对强弱指标、MACD、布林带等。工具会先获取股票的基础数据，然后计算相应的技术指标。
    
    Args:
        ts_code: 股票代码，支持以下格式：
            - '000001' (6位数字，会自动识别市场)
            - '000001.SZ' (深圳市场)
            - '600000.SH' (上海市场)
            示例：'000001' 或 '600000'
        indicators: 要计算的指标，多个指标用逗号分隔。支持的指标：
            - 'MA': 移动平均线（默认计算 5, 10, 20, 30, 60 日均线）
            - 'EMA': 指数移动平均线（默认计算 12, 26 日均线）
            - 'RSI': 相对强弱指标（默认周期 14）
            - 'MACD': MACD 指标（默认参数 12, 26, 9）
            - 'BOLL': 布林带（默认周期 20，标准差 2.0）
            - 'KDJ': KDJ 指标（默认周期 9）
            - 'OBV': 能量潮指标
            示例：'MA,RSI,MACD' 或 'RSI,BOLL'
        start_date: 可选，开始日期，格式为 'YYYYMMDD' 或 'YYYY-MM-DD'
            如果不提供，默认使用最近 120 个交易日的数据
            示例：'20250101' 或 '2025-01-01'
        end_date: 可选，结束日期，格式为 'YYYYMMDD' 或 'YYYY-MM-DD'
            如果不提供，默认使用当前日期
            示例：'20251231' 或 '2025-12-31'
        period: 可选，如果只提供 period，将获取最近 period 个交易日的数据
            示例：30（获取最近30个交易日）
    
    Returns:
        JSON 格式的字符串，包含以下字段：
        - success: 是否成功
        - message: 提示信息
        - data: 技术指标数据列表，每个元素包含：
            - 原始数据字段（trade_date, open, high, low, close, vol 等）
            - 计算得到的技术指标字段（根据请求的指标而定）
        - indicators: 已计算的指标列表
        - summary: 数据摘要（包含最新指标值等）
    
    Examples:
        >>> get_indicators('000001', 'MA,RSI', start_date='20250101', end_date='20250131')
        '{"success": true, "data": [...], "indicators": ["MA", "RSI"], ...}'
        
        >>> get_indicators('600000', 'MACD,BOLL', period=60)
        '{"success": true, "data": [...], "indicators": ["MACD", "BOLL"], ...}'
    """
    try:
        provider = _get_provider()
        
        # 处理日期参数
        if period:
            # 如果提供了 period，获取最近 period 个交易日
            from datetime import datetime, timedelta
            end_date_obj = datetime.now()
            start_date_obj = end_date_obj - timedelta(days=period * 2)  # 预留足够的天数
            start_date = start_date_obj.strftime('%Y%m%d')
            end_date = end_date_obj.strftime('%Y%m%d')
        elif not start_date or not end_date:
            # 默认获取最近 120 个交易日
            from datetime import datetime, timedelta
            end_date_obj = datetime.now()
            start_date_obj = end_date_obj - timedelta(days=180)  # 预留足够的天数
            start_date = start_date_obj.strftime('%Y%m%d')
            end_date = end_date_obj.strftime('%Y%m%d')
        
        # 获取基础数据
        df = provider.get_daily(ts_code, start_date, end_date)
        
        if df.empty:
            return json.dumps({
                "success": False,
                "message": f"未找到股票 {ts_code} 在指定期间的数据",
                "data": [],
                "indicators": [],
                "summary": {}
            }, ensure_ascii=False, indent=2)
        
        # 解析指标列表
        indicator_list = [ind.strip().upper() for ind in indicators.split(',')]
        
        # 计算技术指标
        result_df = _calculate_indicators(df, indicator_list)
        
        # 转换为字典列表，并将 NaN 值转换为 None（JSON 中的 null）
        data_list = result_df.replace({np.nan: None}).to_dict('records')
        
        # 提取最新指标值作为摘要
        summary = {
            "total_records": len(data_list),
            "date_range": {
                "start": data_list[0]['trade_date'] if data_list else None,
                "end": data_list[-1]['trade_date'] if data_list else None
            },
            "latest_indicators": {}
        }
        
        if data_list:
            latest = data_list[-1]
            # 提取所有指标字段（排除基础数据字段）
            base_fields = ['ts_code', 'trade_date', 'open', 'high', 'low', 'close', 
                          'pre_close', 'change', 'pct_chg', 'vol', 'amount']
            for key, value in latest.items():
                if key not in base_fields and value is not None:
                    summary["latest_indicators"][key] = float(value) if isinstance(value, (int, float)) else str(value)
        
        # 返回 JSON 字符串（NaN 会被转换为 null）
        result = {
            "success": True,
            "message": f"成功计算 {len(indicator_list)} 个技术指标，共 {len(data_list)} 条数据",
            "data": data_list,
            "indicators": indicator_list,
            "summary": summary
        }
        
        return json.dumps(result, ensure_ascii=False, indent=2, default=str)
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "message": f"计算技术指标时发生错误: {str(e)}",
            "data": [],
            "indicators": [],
            "summary": {}
        }, ensure_ascii=False, indent=2)

