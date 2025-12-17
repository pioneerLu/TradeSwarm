"""新闻工具"""
import json
import re
from typing import Optional
from datetime import datetime, timedelta
import pandas as pd
from langchain_core.tools import tool
from tradingagents.data_sources.tushare_provider import TushareProvider
from tradingagents.data_sources.akshare_provider import AkshareProvider
from tradingagents.data_sources.utils import normalize_stock_code, format_date


# 全局 Provider 实例（懒加载）
_tushare_provider: Optional[TushareProvider] = None
_akshare_provider: Optional[AkshareProvider] = None


def _get_tushare_provider() -> TushareProvider:
    """获取 Tushare Provider 实例（单例模式）"""
    global _tushare_provider
    if _tushare_provider is None:
        _tushare_provider = TushareProvider()
    return _tushare_provider


def _get_akshare_provider() -> AkshareProvider:
    """获取 AkShare Provider 实例（单例模式）"""
    global _akshare_provider
    if _akshare_provider is None:
        _akshare_provider = AkshareProvider()
    return _akshare_provider


@tool
def get_news(
    ts_code: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    days: Optional[int] = 7,
    limit: Optional[int] = 10
) -> str:
    """
    获取 A 股股票相关的新闻和公告信息
    
    此工具用于获取指定股票在指定日期范围内的新闻、公告和重要事件信息。
    包括公司公告、新闻资讯等可能影响股价的信息。
    优先使用 AkShare（东方财富）获取新闻，失败时使用 Tushare 作为备选。
    
    Args:
        ts_code: 股票代码，支持以下格式：
            - '000001' (6位数字，会自动识别市场)
            - '000001.SZ' (深圳市场)
            - '600000.SH' (上海市场)
            示例：'000001' 或 '600000'
        start_date: 可选，开始日期，格式为 'YYYYMMDD' 或 'YYYY-MM-DD'
            如果不提供，默认使用最近 days 天的数据
            示例：'20250101' 或 '2025-01-01'
        end_date: 可选，结束日期，格式为 'YYYYMMDD' 或 'YYYY-MM-DD'
            如果不提供，默认使用当前日期
            示例：'20251231' 或 '2025-12-31'
        days: 可选，如果未提供日期范围，获取最近 days 天的数据（默认 7 天）
            示例：7（获取最近7天的数据）
        limit: 可选，返回的新闻数量限制（默认 10 条）
            示例：10
    
    Returns:
        JSON 格式的字符串，包含以下字段：
        - success: 是否成功
        - message: 提示信息
        - data: 新闻/公告列表，每个元素包含：
            - publish_time: 发布时间
            - title: 新闻标题
            - url: 文章链接
            - content: 新闻内容（如果有）
            - source: 文章来源（如果有）
        - summary: 数据摘要（包含数据条数、日期范围等）
    
    Examples:
        >>> get_news('000001', days=7, limit=10)
        '{"success": true, "data": [...], "summary": {...}}'
        
        >>> get_news('000001', start_date='20250101', end_date='20250131', limit=20)
        '{"success": true, "data": [...], "summary": {...}}'
    """
    try:
        # 处理日期参数（用于后续日期筛选）
        if not start_date or not end_date:
            end_date_obj = datetime.now()
            start_date_obj = end_date_obj - timedelta(days=days)
            start_date = start_date_obj.strftime('%Y%m%d')
            end_date = end_date_obj.strftime('%Y%m%d')
        
        # 首先尝试使用 AkShare 获取新闻
        try:
            ak_provider = _get_akshare_provider()
            # 注意：get_stock_news 现在返回 Markdown 格式字符串
            markdown_content = ak_provider.get_stock_news(ts_code, limit=limit or 10)
            
            # 返回包含 Markdown 的 JSON 格式，便于 Agent 处理
            result = {
                "success": True,
                "message": f"成功从 AkShare 获取股票 {ts_code} 的新闻",
                "format": "markdown",
                "content": markdown_content,
                "summary": {
                    "data_source": "akshare",
                    "date_range": {
                        "start": start_date,
                        "end": end_date
                    },
                    "note": "数据以 Markdown 格式返回，便于 LLM 理解和处理"
                }
            }
            
            return json.dumps(result, ensure_ascii=False, indent=2, default=str)
            
        except Exception as ak_error:
            # AkShare 失败，尝试使用 Tushare 作为备选
            ak_error_msg = str(ak_error)
            try:
                tushare_provider = _get_tushare_provider()
                
                # 标准化股票代码
                ts_code_normalized = normalize_stock_code(ts_code)
                start_date_formatted = format_date(start_date)
                end_date_formatted = format_date(end_date)
                
                # 使用 Tushare 的 notice 接口（如果可用）
                # 注意：Tushare 的 notice 接口可能需要特定权限
                try:
                    df = tushare_provider.pro.notice(
                        ts_code=ts_code_normalized,
                        start_date=start_date_formatted,
                        end_date=end_date_formatted
                    )
                except (AttributeError, Exception) as tushare_api_error:
                    # 如果 notice 接口不存在或调用失败
                    # 返回友好的错误信息，避免 agent 陷入循环
                    return json.dumps({
                        "success": False,
                        "message": f"获取新闻数据失败。AkShare 接口异常（可能是网络问题或接口变更），Tushare 接口也不可用。"
                                  f"建议：1) 检查网络连接 2) 稍后重试 3) 手动关注相关新闻。"
                                  f"错误详情：AkShare - {ak_error_msg[:100]}",
                        "data": [],
                        "summary": {
                            "total_records": 0,
                            "data_source": "error",
                            "date_range": {"start": start_date, "end": end_date}
                        }
                    }, ensure_ascii=False, indent=2)
                
                if df is not None and not df.empty:
                    data_list = df.to_dict('records')
                    
                    summary = {
                        "total_records": len(data_list),
                        "data_source": "tushare",
                        "date_range": {
                            "start": data_list[0].get('ann_date', start_date) if data_list else start_date,
                            "end": data_list[-1].get('ann_date', end_date) if data_list else end_date
                        }
                    }
                    
                    result = {
                        "success": True,
                        "message": f"成功从 Tushare 获取 {len(data_list)} 条公告/新闻（AkShare 失败，已使用备选数据源）",
                        "data": data_list,
                        "summary": summary
                    }
                    
                    return json.dumps(result, ensure_ascii=False, indent=2, default=str)
                else:
                    # Tushare 返回空数据，返回友好提示
                    return json.dumps({
                        "success": True,
                        "message": f"在 {start_date} 至 {end_date} 期间未找到股票 {ts_code} 的新闻/公告信息。"
                                  f"AkShare 接口异常，Tushare 也未找到数据。建议手动关注相关新闻。",
                        "data": [],
                        "summary": {
                            "total_records": 0,
                            "data_source": "none",
                            "date_range": {"start": start_date, "end": end_date}
                        }
                    }, ensure_ascii=False, indent=2)
                    
            except Exception as tushare_error:
                # 两个数据源都失败，返回友好的错误信息
                return json.dumps({
                    "success": False,
                    "message": f"获取新闻数据失败。AkShare 错误: {ak_error_msg[:100]}。Tushare 错误: {str(tushare_error)[:100]}。"
                              f"建议：1) 检查网络连接 2) 稍后重试 3) 手动关注相关新闻。",
                    "data": [],
                    "summary": {
                        "total_records": 0,
                        "data_source": "error",
                        "date_range": {"start": start_date, "end": end_date}
                    }
                }, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "message": f"获取新闻数据时发生错误: {str(e)}",
            "data": [],
            "summary": {}
        }, ensure_ascii=False, indent=2)


@tool
def get_global_news(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    days: Optional[int] = 7,
    limit: Optional[int] = 10
) -> str:
    """
    获取宏观经济新闻和全球市场新闻
    
    此工具用于获取指定日期范围内的宏观经济新闻、政策新闻、市场信号等
    可能影响 A 股市场的全球性新闻信息。使用 AkShare 获取财经新闻。
    
    Args:
        start_date: 可选，开始日期，格式为 'YYYYMMDD' 或 'YYYY-MM-DD'
            如果不提供，默认使用最近 days 天的数据
            示例：'20250101' 或 '2025-01-01'
        end_date: 可选，结束日期，格式为 'YYYYMMDD' 或 'YYYY-MM-DD'
            如果不提供，默认使用当前日期
            示例：'20251231' 或 '2025-12-31'
        days: 可选，如果未提供日期范围，获取最近 days 天的数据（默认 7 天）
            示例：7（获取最近7天的数据）
        limit: 可选，返回的新闻数量限制（默认 10 条）
            示例：10
    
    Returns:
        JSON 格式的字符串，包含以下字段：
        - success: 是否成功
        - message: 提示信息
        - data: 新闻列表（如果数据源可用）
        - summary: 数据摘要
    
    Examples:
        >>> get_global_news(days=7, limit=10)
        '{"success": true, "data": [...], "summary": {...}}'
    """
    try:
        # 处理日期参数
        if not start_date or not end_date:
            end_date_obj = datetime.now()
            start_date_obj = end_date_obj - timedelta(days=days)
            start_date = start_date_obj.strftime('%Y%m%d')
            end_date = end_date_obj.strftime('%Y%m%d')
        
        start_date_formatted = format_date(start_date)
        end_date_formatted = format_date(end_date)
        
        # 尝试使用 AkShare 获取宏观市场全景简报
        try:
            ak_provider = _get_akshare_provider()
            # 注意：get_global_news 现在返回 Markdown 格式的宏观市场全景简报
            # 包含：宏观新闻、北向资金、核心指数、汇率信息
            markdown_content = ak_provider.get_global_news()
            
            # 返回包含 Markdown 的 JSON 格式，便于 Agent 处理
            result = {
                "success": True,
                "message": f"成功获取宏观市场全景简报",
                "format": "markdown",
                "content": markdown_content,
                "summary": {
                    "data_source": "akshare",
                    "date_range": {
                        "start": start_date_formatted,
                        "end": end_date_formatted
                    },
                    "note": "数据以 Markdown 格式返回，包含宏观新闻、北向资金、核心指数、汇率四个维度"
                }
            }
            
            return json.dumps(result, ensure_ascii=False, indent=2, default=str)
                
        except Exception as ak_error:
            # AkShare 失败，返回提示信息
            return json.dumps({
                "success": False,
                "message": f"获取宏观市场全景简报时发生错误: {str(ak_error)}。"
                          f"建议关注 {start_date_formatted} 至 {end_date_formatted} 期间的宏观经济信息。",
                "format": "markdown",
                "content": f"# 宏观市场全景简报\n\n## ❌ 数据获取失败\n\n**错误信息**: {str(ak_error)}\n\n建议：检查网络连接或稍后重试。",
                "summary": {
                    "data_source": "error",
                    "date_range": {"start": start_date_formatted, "end": end_date_formatted}
                }
            }, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "message": f"获取宏观经济新闻时发生错误: {str(e)}",
            "data": [],
            "summary": {}
        }, ensure_ascii=False, indent=2)

