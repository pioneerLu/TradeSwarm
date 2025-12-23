"""
数据转换工具模块：将AkShare返回的财务数据转换为数据库格式
"""

from typing import Dict, Any, Optional
import re


def convert_amount_to_float(amount_str: str) -> Optional[float]:
    """
    将金额字符串转换为浮点数（以亿元为单位）
    
    Args:
        amount_str: 金额字符串，如 "893.35亿"、"1500万"、"-17.85亿" 等
    
    Returns:
        转换后的浮点数（亿元为单位），None表示无效或空值
    """
    if not amount_str or amount_str == '' or amount_str == 'false':
        return None
    
    try:
        # 提取数字部分（包括负号和小数点）
        numeric_match = re.search(r'-?\d+\.?\d*', amount_str)
        if not numeric_match:
            return None
        
        numeric_value = float(numeric_match.group())
        
        # 根据单位进行转换
        if '亿' in amount_str:
            return numeric_value  # 已经是亿元
        elif '万' in amount_str:
            return numeric_value / 10000  # 转换为亿元
        elif amount_str.replace('.', '').replace('-', '').isdigit():
            return numeric_value  # 纯数字，默认为亿元
        else:
            return None
    except (ValueError, AttributeError):
        return None


def convert_financial_data_to_db_format(
    data: Dict[str, Any],
    field_mapping: Dict[str, str]
) -> Dict[str, Any]:
    """
    将财务数据转换为数据库格式
    
    Args:
        data: 原始财务数据字典
        field_mapping: 字段映射字典（原始字段名 -> 数据库字段名）
    
    Returns:
        转换后的数据库格式数据
    """
    converted = {}
    
    # 处理基础字段（报告期等）
    if '报告期' in data:
        converted['report_period'] = str(data['报告期'])
    
    # 转换所有映射的字段
    for original_field, db_field in field_mapping.items():
        if original_field in data:
            original_value = data[original_field]
            converted[db_field] = convert_amount_to_float(str(original_value))
    
    return converted


def prepare_profit_statement_data(
    akshare_result: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    准备利润表数据用于插入数据库
    
    Args:
        akshare_result: AkShare返回的利润表结果
    
    Returns:
        准备好的数据库记录，如果数据无效则返回None
    """
    from .schemas import PROFIT_FIELD_MAPPING
    
    # 检查数据有效性
    if not akshare_result.get('data') or not akshare_result['data']:
        return None
    
    data_list = akshare_result['data']
    if not isinstance(data_list, list) or len(data_list) == 0:
        return None
    
    # 取第一条数据
    financial_data = data_list[0]
    
    # 转换基础信息
    result = {
        'symbol': akshare_result['symbol'],
        'report_type': akshare_result['report_type'],
        'data_source': akshare_result['actual_source'],
    }
    
    # 转换财务数据
    financial_data_converted = convert_financial_data_to_db_format(
        financial_data, 
        PROFIT_FIELD_MAPPING
    )
    result.update(financial_data_converted)
    
    return result


def prepare_balance_sheet_data(
    akshare_result: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    准备资产负债表数据用于插入数据库
    
    Args:
        akshare_result: AkShare返回的资产负债表结果
    
    Returns:
        准备好的数据库记录，如果数据无效则返回None
    """
    from .schemas import BALANCE_FIELD_MAPPING
    
    # 检查数据有效性
    if not akshare_result.get('data') or not akshare_result['data']:
        return None
    
    data_list = akshare_result['data']
    if not isinstance(data_list, list) or len(data_list) == 0:
        return None
    
    # 取第一条数据
    financial_data = data_list[0]
    
    # 转换基础信息
    result = {
        'symbol': akshare_result['symbol'],
        'report_type': akshare_result['report_type'],
        'data_source': akshare_result['actual_source'],
    }
    
    # 转换财务数据
    financial_data_converted = convert_financial_data_to_db_format(
        financial_data, 
        BALANCE_FIELD_MAPPING
    )
    result.update(financial_data_converted)
    
    return result


def prepare_cash_flow_statement_data(
    akshare_result: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    准备现金流量表数据用于插入数据库
    
    Args:
        akshare_result: AkShare返回的现金流量表结果
    
    Returns:
        准备好的数据库记录，如果数据无效则返回None
    """
    from .schemas import CASH_FLOW_FIELD_MAPPING
    
    # 检查数据有效性
    if not akshare_result.get('data') or not akshare_result['data']:
        return None
    
    data_list = akshare_result['data']
    if not isinstance(data_list, list) or len(data_list) == 0:
        return None
    
    # 取第一条数据
    financial_data = data_list[0]
    
    # 转换基础信息
    result = {
        'symbol': akshare_result['symbol'],
        'report_type': akshare_result['report_type'],
        'data_source': akshare_result['actual_source'],
    }
    
    # 转换财务数据
    financial_data_converted = convert_financial_data_to_db_format(
        financial_data, 
        CASH_FLOW_FIELD_MAPPING
    )
    result.update(financial_data_converted)
    
    return result


def prepare_macro_news_data(
    akshare_result: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    准备宏观新闻数据用于插入数据库
    
    Args:
        akshare_result: AkShare返回的宏观新闻结果
    
    Returns:
        准备好的数据库记录列表（多条记录），如果数据无效则返回None
    """
    data = akshare_result.get('data')
    if data is None:
        return None
    
    # 宏观新闻返回DataFrame，需要转换为记录列表
    if hasattr(data, 'empty') and data.empty:
        return None
    
    records = []
    
    for _, row in data.iterrows():
        record = {
            'title': str(row.get('title', '')) if row.get('title') is not None else '',
            'content': str(row.get('content', '')) if row.get('content') is not None and row.get('content') != '' else None,
            'publish_time': str(row.get('publish_time', '')) if row.get('publish_time') is not None and row.get('publish_time') != '' else None,
            'url': str(row.get('url', '')) if row.get('url') is not None and row.get('url') != '' else None,
            'original_source': str(row.get('original_source', '')) if row.get('original_source') is not None and row.get('original_source') != '' else None,
            'data_source': str(row.get('data_source', '')) if row.get('data_source') is not None and row.get('data_source') != '' else 'unknown',
        }
        records.append(record)
    
    return records


def prepare_northbound_money_flow_data(
    akshare_result: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    准备北向资金流向数据用于插入数据库
    
    Args:
        akshare_result: AkShare返回的北向资金流向结果
    
    Returns:
        准备好的数据库记录（单条记录），如果数据无效则返回None
    """
    data = akshare_result.get('data')
    if data is None:
        return None
    
    money_flow = data
    
    record = {
        'title': str(money_flow.get('title', '北向资金')) if money_flow.get('title') is not None else '北向资金',
        'value': str(money_flow.get('value', '')) if money_flow.get('value') is not None else '',
        'flow_status': str(money_flow.get('flow_status', '')) if money_flow.get('flow_status') is not None and money_flow.get('flow_status') != '' else None,
        'amount_yi': float(money_flow.get('amount_yi', 0)) if money_flow.get('amount_yi') is not None else None,
        'date': str(money_flow.get('date', '')) if money_flow.get('date') is not None and money_flow.get('date') != '' else None,
        'source': str(money_flow.get('source', '')) if money_flow.get('source') is not None and money_flow.get('source') != '' else None,
    }
    
    return record


def prepare_global_indices_data(
    akshare_result: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    准备核心指数表现数据用于插入数据库
    
    Args:
        akshare_result: AkShare返回的核心指数表现结果
    
    Returns:
        准备好的数据库记录列表（多条记录），如果数据无效则返回None
    """
    data = akshare_result.get('data')
    if data is None:
        return None
    
    # 核心指数返回DataFrame，需要转换为记录列表
    if hasattr(data, 'empty') and data.empty:
        return None
    
    records = []
    
    for _, row in data.iterrows():
        record = {
            'asset': str(row.get('asset', '')) if row.get('asset') is not None else '',
            'code': str(row.get('code', '')) if row.get('code') is not None else '',
            'price': float(row.get('price', 0)) if row.get('price') is not None else None,
            'change': str(row.get('change', '')) if row.get('change') is not None else '',
            'change_pct': float(row.get('change_pct', 0)) if row.get('change_pct') is not None else None,
        }
        records.append(record)
    
    return records


def prepare_currency_exchange_rate_data(
    akshare_result: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    准备汇率信息数据用于插入数据库
    
    Args:
        akshare_result: AkShare返回的汇率信息结果
    
    Returns:
        准备好的数据库记录（单条记录），如果数据无效则返回None
    """
    data = akshare_result.get('data')
    if data is None:
        return None
    
    currency = data
    
    record = {
        'currency_pair': str(currency.get('currency_pair', '')) if currency.get('currency_pair') is not None else '',
        'price': float(currency.get('price', 0)) if currency.get('price') is not None else None,
        'change': str(currency.get('change', '')) if currency.get('change') is not None and currency.get('change') != '' else None,
        'change_pct': float(currency.get('change_pct', 0)) if currency.get('change_pct') is not None else None,
        'description': str(currency.get('description', '')) if currency.get('description') is not None and currency.get('description') != '' else None,
        'date': str(currency.get('date', '')) if currency.get('date') is not None and currency.get('date') != '' else None,
    }
    
    return record


# 数据准备函数映射
DATA_PREPARERS = {
    "profit_statements": prepare_profit_statement_data,
    "balance_sheets": prepare_balance_sheet_data,
    "cash_flow_statements": prepare_cash_flow_statement_data,
    "macro_news": prepare_macro_news_data,
    "northbound_money_flow": prepare_northbound_money_flow_data,
    "global_indices": prepare_global_indices_data,
    "currency_exchange_rates": prepare_currency_exchange_rate_data,
}
