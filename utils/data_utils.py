"""数据源工具函数"""
from typing import Optional


def normalize_stock_code(stock_code: str) -> str:
    """
    标准化 A 股股票代码格式
    
    将各种格式的股票代码转换为 Tushare 标准格式（如 '000001.SZ'）
    
    Args:
        stock_code: 股票代码，支持以下格式：
            - '000001' (6位数字)
            - '000001.SZ' (已包含后缀)
            - '600000.SH' (已包含后缀)
    
    Returns:
        标准化后的股票代码，格式为 'XXXXXX.SZ' 或 'XXXXXX.SH'
    
    Examples:
        >>> normalize_stock_code('000001')
        '000001.SZ'
        >>> normalize_stock_code('600000')
        '600000.SH'
        >>> normalize_stock_code('000001.SZ')
        '000001.SZ'
    """
    # 去除空格
    stock_code = stock_code.strip()
    
    # 如果已经包含后缀，直接返回
    if '.' in stock_code:
        return stock_code.upper()
    
    # 如果是6位数字，判断市场
    if len(stock_code) == 6 and stock_code.isdigit():
        # 上海市场：60、68 开头
        if stock_code.startswith(('60', '68')):
            return f"{stock_code}.SH"
        # 深圳市场：00、30 开头
        elif stock_code.startswith(('00', '30')):
            return f"{stock_code}.SZ"
        # 其他情况默认深圳
        else:
            return f"{stock_code}.SZ"
    
    # 无法识别，返回原值（可能会在调用时出错）
    return stock_code


def format_date(date_str: str) -> str:
    """
    格式化日期字符串为 Tushare 需要的格式 (YYYYMMDD)
    
    Args:
        date_str: 日期字符串，支持格式：
            - 'YYYY-MM-DD'
            - 'YYYYMMDD'
            - 'YYYY/MM/DD'
    
    Returns:
        格式化为 'YYYYMMDD' 的字符串
    
    Examples:
        >>> format_date('2025-12-07')
        '20251207'
        >>> format_date('20251207')
        '20251207'
    """
    # 去除空格
    date_str = date_str.strip()
    
    # 如果已经是 YYYYMMDD 格式
    if len(date_str) == 8 and date_str.isdigit():
        return date_str
    
    # 处理 YYYY-MM-DD 或 YYYY/MM/DD 格式
    date_str = date_str.replace('-', '').replace('/', '')
    
    if len(date_str) == 8 and date_str.isdigit():
        return date_str
    
    # 无法格式化，返回原值
    return date_str


def extract_stock_code_number(stock_code: str) -> str:
    """
    提取股票代码的纯数字部分（去除后缀和特殊字符）
    
    用于需要纯数字代码的接口（如 Tushare 旧版接口）
    
    Args:
        stock_code: 股票代码，支持以下格式：
            - '000001' (6位数字)
            - '000001.SZ' (带后缀)
            - '600000.SH' (带后缀)
    
    Returns:
        纯数字股票代码（6位数字字符串）
    
    Examples:
        >>> extract_stock_code_number('000001.SZ')
        '000001'
        >>> extract_stock_code_number('600000.SH')
        '600000'
        >>> extract_stock_code_number('000001')
        '000001'
    """
    import re
    # 去除空格
    stock_code = stock_code.strip()
    
    # 提取所有数字
    numbers = re.sub(r"\D", "", stock_code)
    
    # 如果提取到6位数字，返回
    if len(numbers) == 6 and numbers.isdigit():
        return numbers
    
    # 如果提取到的数字不是6位，尝试截取前6位
    if len(numbers) >= 6:
        return numbers[:6]
    
    # 无法提取，返回原值
    return stock_code
