"""
TradeSwarm 数据流脚本：对齐 tool_outputs.md 的输出格式

说明：
- 使用 TradingAgents provider：y_finance / openai / alpha_vantage / stockstats
- 输出结构严格对齐 tradingagents/tool_nodes/tool_outputs.md
- 每个函数返回 JSON 字符串
- 结果写入 scripts/dataflows_output.txt
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
from dotenv import dotenv_values
from stockstats import wrap


# 第一阶段：在导入 yfinance 前注入代理环境变量
_project_root = Path(__file__).resolve().parents[1]
_env_path = _project_root / ".env"
if _env_path.exists():
    _env_values = dotenv_values(_env_path)
    for _key in ["HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY"]:
        _value = _env_values.get(_key)
        if _value:
            os.environ[_key] = str(_value)

import yfinance as yf


_RUNTIME_READY: bool = False


def _load_env_values(project_root: Path, required_keys: List[str]) -> Dict[str, str]:
    """
    加载 .env 并校验必需环境变量。

    Args:
        project_root: 项目根目录
        required_keys: 必需环境变量列表

    Returns:
        Dict[str, str]: 已解析并校验的环境变量
    """

    env_path = project_root / ".env"
    if not env_path.exists():
        raise FileNotFoundError("缺少 .env 文件，请在项目根目录创建 .env")

    env_values = dotenv_values(env_path)

    resolved: Dict[str, str] = {}
    for key in required_keys:
        value = os.getenv(key) or env_values.get(key)
        if not value:
            raise ValueError(f"环境变量缺失或为空: {key}")
        resolved[key] = str(value)

    for key, value in resolved.items():
        os.environ[key] = value

    return resolved


def _prepare_runtime() -> None:
    """
    准备运行时环境：加载 .env、确保关键变量可用。
    """
    global _RUNTIME_READY
    if _RUNTIME_READY:
        return

    project_root = Path(__file__).resolve().parents[1]

    required_keys = [
        "ALPHA_VANTAGE_API_KEY",
        "OPENAI_API_KEY",
    ]
    _load_env_values(project_root, required_keys)

    _RUNTIME_READY = True


def _alpha_vantage_request(params: Dict[str, str]) -> str:
    """
    发送 Alpha Vantage 请求并返回原始字符串。

    Args:
        params: 请求参数字典

    Returns:
        str: API 返回的原始字符串
    """
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
    if not api_key:
        raise ValueError("ALPHA_VANTAGE_API_KEY 未设置")

    request_params = dict(params)
    request_params["apikey"] = api_key
    response = requests.get("https://www.alphavantage.co/query", params=request_params, timeout=30)
    response.raise_for_status()
    return response.text


def _format_av_datetime(date_value: str, is_end: bool) -> str:
    """
    转换日期为 Alpha Vantage 所需格式：YYYYMMDDTHHMM。

    Args:
        date_value: 日期字符串（YYYY-MM-DD）
        is_end: 是否为结束时间

    Returns:
        str: 格式化后的日期字符串
    """
    date_obj = datetime.strptime(date_value, "%Y-%m-%d")
    if is_end:
        return date_obj.strftime("%Y%m%dT2359")
    return date_obj.strftime("%Y%m%dT0000")


def _openai_web_search(
    openai_base_url: str,
    openai_model: str,
    prompt_text: str,
) -> str:
    """
    使用 OpenAI Responses API 触发 web_search_preview。

    Args:
        openai_base_url: OpenAI Base URL
        openai_model: OpenAI 模型名
        prompt_text: 搜索指令

    Returns:
        str: API 返回的原始字符串
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY 未设置")

    url = f"{openai_base_url.rstrip('/')}/responses"
    payload = {
        "model": openai_model,
        "input": [
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": prompt_text,
                    }
                ],
            }
        ],
        "text": {"format": {"type": "text"}},
        "tools": [
            {
                "type": "web_search_preview",
                "user_location": {"type": "approximate"},
                "search_context_size": "low",
            }
        ],
        "temperature": 1,
        "max_output_tokens": 4096,
        "top_p": 1,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=60)
    response.raise_for_status()
    return response.text


def _safe_json_load(text: str) -> Optional[Dict[str, Any]]:
    """
    安全解析 JSON 字符串。

    Args:
        text: JSON 字符串

    Returns:
        Optional[Dict[str, Any]]: 解析后的字典，失败返回 None
    """
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
        return None
    except Exception:
        return None


def _pick_fields(payload: Dict[str, Any], fields: List[str]) -> Dict[str, Any]:
    """
    从字典中提取指定字段。

    Args:
        payload: 原始字典
        fields: 字段列表

    Returns:
        Dict[str, Any]: 提取后的字典
    """
    result: Dict[str, Any] = {}
    for field in fields:
        result[field] = payload.get(field)
    return result


def _format_trade_date(date_value: Any) -> str:
    """
    统一格式化交易日期为 YYYYMMDD。

    Args:
        date_value: 日期输入（datetime / str）

    Returns:
        str: 格式化日期字符串
    """
    if isinstance(date_value, datetime):
        return date_value.strftime("%Y%m%d")
    if isinstance(date_value, str):
        try:
            return datetime.strptime(date_value, "%Y-%m-%d").strftime("%Y%m%d")
        except ValueError:
            return date_value.replace("-", "")
    return str(date_value)


def _normalize_yfinance_frame(data: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """
    规整 yfinance 返回的 DataFrame，处理多级列名。

    Args:
        data: 原始 DataFrame
        symbol: 股票代码

    Returns:
        pd.DataFrame: 规整后的 DataFrame
    """
    if isinstance(data.columns, pd.MultiIndex):
        # 第一阶段：优先选择指定 symbol 的列
        if symbol in data.columns.get_level_values(-1):
            data = data.xs(symbol, axis=1, level=-1)
        elif symbol in data.columns.get_level_values(0):
            data = data.xs(symbol, axis=1, level=0)
        else:
            # 第二阶段：回退为第一层列名
            data.columns = [col[0] for col in data.columns]
    return data


def _build_result(success: bool, message: str, data: Any, summary: Dict[str, Any]) -> str:
    """
    构建统一 JSON 返回结构。

    Args:
        success: 是否成功
        message: 提示信息
        data: 数据主体
        summary: 摘要信息

    Returns:
        str: JSON 字符串
    """
    payload = {
        "success": success,
        "message": message,
        "data": data,
        "summary": summary,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def fetch_market_data(
    symbol: str,
    start_date: str,
    end_date: str,
) -> str:
    """
    获取市场数据流（market）：对齐 get_stock_data 输出。

    Args:
        symbol: 股票代码（如 AAPL）
        start_date: 开始日期（YYYY-MM-DD）
        end_date: 结束日期（YYYY-MM-DD）

    Returns:
        str: JSON 字符串
    """
    _prepare_runtime()

    data = yf.download(
        symbol,
        start=start_date,
        end=end_date,
        progress=False,
        auto_adjust=True,
    )

    if data is None or data.empty:
        return _build_result(
            False,
            f"未获取到行情数据: {symbol} {start_date} ~ {end_date}",
            [],
            {},
        )

    # 第一阶段：规范列名与日期
    data = _normalize_yfinance_frame(data, symbol)
    data = data.reset_index()
    data["Date"] = pd.to_datetime(data["Date"])

    # 第二阶段：构造记录列表
    records: List[Dict[str, Any]] = []
    prev_close: Optional[float] = None
    for _, row in data.iterrows():
        close_raw = row.get("Close")
        open_raw = row.get("Open")
        high_raw = row.get("High")
        low_raw = row.get("Low")
        volume_raw = row.get("Volume")

        close_value = float(close_raw) if pd.notna(close_raw) else None
        open_value = float(open_raw) if pd.notna(open_raw) else None
        high_value = float(high_raw) if pd.notna(high_raw) else None
        low_value = float(low_raw) if pd.notna(low_raw) else None
        volume_value = float(volume_raw) if pd.notna(volume_raw) else None
        trade_date = _format_trade_date(row.get("Date"))

        change_value = None
        pct_chg_value = None
        if close_value is not None and prev_close is not None and prev_close != 0:
            change_value = close_value - prev_close
            pct_chg_value = (change_value / prev_close) * 100

        amount_value = None
        if close_value is not None and volume_value is not None:
            amount_value = close_value * volume_value

        record = {
            "ts_code": symbol,
            "trade_date": trade_date,
            "open": open_value,
            "high": high_value,
            "low": low_value,
            "close": close_value,
            "pre_close": prev_close,
            "change": change_value,
            "pct_chg": pct_chg_value,
            "vol": volume_value,
            "amount": amount_value,
        }
        records.append(record)
        prev_close = close_value

    # 第三阶段：生成摘要
    start_trade_date = records[0]["trade_date"] if records else None
    end_trade_date = records[-1]["trade_date"] if records else None
    latest = records[-1] if records else {}
    summary = {
        "total_records": len(records),
        "date_range": {
            "start": start_trade_date,
            "end": end_trade_date,
        },
        "latest_price": {
            "close": latest.get("close"),
            "pct_chg": latest.get("pct_chg"),
        } if records else None,
    }

    return _build_result(True, f"成功获取 {len(records)} 条数据", records, summary)


def fetch_indicators_data(
    symbol: str,
    curr_date: str,
    indicators: str,
    period: int,
) -> str:
    """
    获取技术指标（对齐 get_indicators 输出）。

    Args:
        symbol: 股票代码
        curr_date: 当前日期（YYYY-MM-DD）
        indicators: 指标列表（例如 MA,RSI）
        period: 回看天数

    Returns:
        str: JSON 字符串
    """
    _prepare_runtime()

    end_date_obj = datetime.strptime(curr_date, "%Y-%m-%d")
    start_date_obj = end_date_obj - timedelta(days=period)
    start_date = start_date_obj.strftime("%Y-%m-%d")
    end_date = end_date_obj.strftime("%Y-%m-%d")

    data = yf.download(
        symbol,
        start=start_date,
        end=end_date,
        progress=False,
        auto_adjust=True,
    )
    if data is None or data.empty:
        return _build_result(False, "技术指标数据为空", [], {})

    # 第一阶段：准备数据格式
    data = _normalize_yfinance_frame(data, symbol)
    data = data.reset_index()
    data["Date"] = pd.to_datetime(data["Date"])
    data.rename(
        columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
            "Date": "date",
        },
        inplace=True,
    )
    df = wrap(data)

    # 第二阶段：解析指标列表
    raw_indicators = [item.strip().upper() for item in indicators.split(",") if item.strip()]
    indicator_columns: List[str] = []
    display_names: List[str] = []
    for item in raw_indicators:
        if item == "MA":
            indicator_columns.extend(["close_5_sma", "close_10_sma", "close_20_sma"])
            display_names.extend(["MA5", "MA10", "MA20"])
        elif item == "RSI":
            indicator_columns.append("rsi_14")
            display_names.append("RSI")
        elif item == "MACD":
            indicator_columns.extend(["macd", "macds", "macdh"])
            display_names.extend(["MACD", "MACD_SIGNAL", "MACD_HIST"])
        elif item == "BOLL":
            indicator_columns.extend(["boll", "boll_ub", "boll_lb"])
            display_names.extend(["BOLL", "BOLL_UB", "BOLL_LB"])

    # 第三阶段：计算指标与组织输出
    for col in indicator_columns:
        df[col]

    records: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        record = {
            "trade_date": _format_trade_date(row.get("date")),
            "close": row.get("close"),
        }
        for name, col in zip(display_names, indicator_columns):
            record[name] = row.get(col)
        records.append(record)

    latest = records[-1] if records else {}
    summary = {
        "total_records": len(records),
        "indicators_calculated": display_names,
        "latest_indicators": {name: latest.get(name) for name in display_names},
    }
    payload = {
        "success": True,
        "message": "成功计算技术指标",
        "indicators": display_names,
        "data": records,
        "summary": summary,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def fetch_news_data(
    curr_date: str,
    look_back_days: int,
    limit: int,
    openai_base_url: str,
    openai_model: str,
    ticker: str,
) -> str:
    """
    获取个股新闻（对齐 get_news 输出）。

    Args:
        curr_date: 当前日期（YYYY-MM-DD）
        look_back_days: 回看天数
        limit: 新闻条数限制
        openai_base_url: OpenAI Base URL
        openai_model: OpenAI 模型名
        ticker: 股票代码

    Returns:
        str: JSON 字符串
    """
    _prepare_runtime()

    end_date_obj = datetime.strptime(curr_date, "%Y-%m-%d")
    start_date_obj = end_date_obj - timedelta(days=look_back_days)
    start_date_text = start_date_obj.strftime("%Y-%m-%d")
    end_date_text = end_date_obj.strftime("%Y-%m-%d")

    prompt = (
        f"请生成 Markdown 格式的公司新闻简报，股票代码/名称为 {ticker}。"
        f"时间范围：{start_date_text} 到 {end_date_text}，不超过 {limit} 条。"
        f"输出包含标题、时间、摘要，尽量保持结构清晰。"
    )
    raw_response = _openai_web_search(openai_base_url, openai_model, prompt)
    response_payload = _safe_json_load(raw_response) or {}
    content_text = None

    # 第一阶段：解析 OpenAI Responses 输出文本
    outputs = response_payload.get("output")
    if isinstance(outputs, list) and outputs:
        for item in outputs:
            content = item.get("content") if isinstance(item, dict) else None
            if isinstance(content, list):
                for content_item in content:
                    if content_item.get("type") == "output_text":
                        content_text = content_item.get("text")
                        break
            if content_text:
                break

    if not content_text:
        content_text = raw_response

    summary = {
        "data_source": "openai",
        "date_range": {
            "start": start_date_text,
            "end": end_date_text,
        },
        "note": "数据以 Markdown 格式返回，便于 LLM 理解与处理。",
    }
    payload = {
        "success": True,
        "message": f"成功获取 {ticker} 个股新闻",
        "format": "markdown",
        "content": content_text,
        "summary": summary,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def fetch_global_news_data(
    curr_date: str,
    look_back_days: int,
    limit: int,
    openai_base_url: str,
    openai_model: str,
) -> str:
    """
    获取宏观新闻（对齐 get_global_news 输出）。

    Args:
        curr_date: 当前日期（YYYY-MM-DD）
        look_back_days: 回看天数
        limit: 新闻条数限制
        openai_base_url: OpenAI Base URL
        openai_model: OpenAI 模型名

    Returns:
        str: JSON 字符串
    """
    _prepare_runtime()

    end_date_obj = datetime.strptime(curr_date, "%Y-%m-%d")
    start_date_obj = end_date_obj - timedelta(days=look_back_days)
    start_date_text = start_date_obj.strftime("%Y-%m-%d")
    end_date_text = end_date_obj.strftime("%Y-%m-%d")

    prompt = (
        f"请生成 Markdown 格式的宏观市场简报，时间范围：{start_date_text} 到 {end_date_text}，"
        f"不超过 {limit} 条。内容包括宏观新闻、市场情绪、关键事件，并保持结构化标题。"
    )
    raw_response = _openai_web_search(openai_base_url, openai_model, prompt)
    response_payload = _safe_json_load(raw_response) or {}
    content_text = None

    # 第一阶段：解析 OpenAI Responses 输出文本
    outputs = response_payload.get("output")
    if isinstance(outputs, list) and outputs:
        for item in outputs:
            content = item.get("content") if isinstance(item, dict) else None
            if isinstance(content, list):
                for content_item in content:
                    if content_item.get("type") == "output_text":
                        content_text = content_item.get("text")
                        break
            if content_text:
                break

    if not content_text:
        content_text = raw_response

    summary = {
        "data_source": "openai",
        "date_range": {
            "start": start_date_text,
            "end": end_date_text,
        },
        "note": "数据以 Markdown 格式返回，便于 LLM 理解与处理。",
        "errors": [],
    }
    payload = {
        "success": True,
        "message": "成功获取宏观市场简报",
        "format": "markdown",
        "content": content_text,
        "summary": summary,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def fetch_sentiments_data(
    ticker: str,
    start_date: str,
    end_date: str,
) -> str:
    """
    获取情绪数据。

    Args:
        ticker: 股票代码
        start_date: 开始日期（YYYY-MM-DD）
        end_date: 结束日期（YYYY-MM-DD）

    Returns:
        str: JSON 字符串
    """
    _prepare_runtime()

    time_from = _format_av_datetime(start_date, False)
    time_to = _format_av_datetime(end_date, True)
    raw_text = _alpha_vantage_request(
        {
            "function": "NEWS_SENTIMENT",
            "tickers": ticker,
            "time_from": time_from,
            "time_to": time_to,
            "sort": "LATEST",
            "limit": "50",
        }
    )
    payload = _safe_json_load(raw_text) or {"raw": raw_text}
    summary = {
        "data_source": "alpha_vantage",
        "date_range": {"start": start_date, "end": end_date},
    }
    return _build_result(True, "成功获取情绪数据", payload, summary)


def fetch_company_info_data(
    ticker: str,
    curr_date: str,
) -> str:
    """
    获取公司信息（对齐 get_company_info 输出）。

    Args:
        ticker: 股票代码
        curr_date: 当前日期（YYYY-MM-DD）

    Returns:
        str: JSON 字符串
    """
    _prepare_runtime()

    overview_text = _alpha_vantage_request(
        {
            "function": "OVERVIEW",
            "symbol": ticker,
        }
    )
    overview_payload = _safe_json_load(overview_text) or {}
    data = {
        "ts_code": overview_payload.get("Symbol") or ticker,
        "name": overview_payload.get("Name"),
        "area": overview_payload.get("Country"),
        "industry": overview_payload.get("Industry") or overview_payload.get("Sector"),
        "market": overview_payload.get("Exchange"),
        "list_date": overview_payload.get("LatestQuarter"),
        "total_share": overview_payload.get("SharesOutstanding"),
        "float_share": overview_payload.get("SharesOutstanding"),
    }
    summary = {
        "data_source": "alpha_vantage",
        "update_time": curr_date,
    }
    return _build_result(True, "成功获取公司信息", data, summary)


def _build_preview_meta(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    构建 preview/meta 结构。

    Args:
        records: 原始记录列表

    Returns:
        Dict[str, Any]: 包含 preview 与 meta 的结构
    """
    columns: List[str] = list(records[0].keys()) if records else []
    preview = records
    meta = {
        "total_rows": len(records),
        "preview_rows": len(preview),
        "columns": columns,
    }
    return {"preview": preview, "meta": meta}


def fetch_financial_statements_data(
    ticker: str,
    report_type: str,
    periods: int,
) -> str:
    """
    获取三大财报（对齐 get_financial_statements 输出）。

    Args:
        ticker: 股票代码
        report_type: 报表类型（annual / quarter）
        periods: 预览条数

    Returns:
        str: JSON 字符串
    """
    _prepare_runtime()

    report_key = "annualReports" if report_type == "annual" else "quarterlyReports"

    income_text = _alpha_vantage_request({"function": "INCOME_STATEMENT", "symbol": ticker})
    balance_text = _alpha_vantage_request({"function": "BALANCE_SHEET", "symbol": ticker})
    cashflow_text = _alpha_vantage_request({"function": "CASH_FLOW", "symbol": ticker})

    income_payload = _safe_json_load(income_text) or {}
    balance_payload = _safe_json_load(balance_text) or {}
    cashflow_payload = _safe_json_load(cashflow_text) or {}

    income_records = income_payload.get(report_key, []) or []
    balance_records = balance_payload.get(report_key, []) or []
    cashflow_records = cashflow_payload.get(report_key, []) or []

    income_preview = [dict(item) for item in income_records[:periods]]
    balance_preview = [dict(item) for item in balance_records[:periods]]
    cashflow_preview = [dict(item) for item in cashflow_records[:periods]]

    data = {
        "income_statement": _build_preview_meta(income_preview),
        "balance_sheet": _build_preview_meta(balance_preview),
        "cash_flow": _build_preview_meta(cashflow_preview),
    }
    summary = {
        "report_type": report_type,
        "periods": periods,
        "data_source": "alpha_vantage",
    }
    return _build_result(True, "成功获取财务报表", data, summary)


def fetch_financial_indicators_data(
    ticker: str,
    report_type: str,
    periods: int,
) -> str:
    """
    获取财务指标（对齐 get_financial_indicators 输出）。

    Args:
        ticker: 股票代码
        report_type: 报表类型（annual / quarter）
        periods: 预览条数

    Returns:
        str: JSON 字符串
    """
    _prepare_runtime()

    overview_text = _alpha_vantage_request({"function": "OVERVIEW", "symbol": ticker})
    overview_payload = _safe_json_load(overview_text) or {}

    record = _pick_fields(
        overview_payload,
        [
            "LatestQuarter",
            "ROE",
            "ROA",
            "GrossProfitTTM",
            "ProfitMargin",
            "OperatingMarginTTM",
            "EPS",
        ],
    )
    records = [record]
    preview_meta = _build_preview_meta(records[:periods])

    summary = {
        "report_type": report_type,
        "periods": periods,
        "data_source": "alpha_vantage",
    }
    return _build_result(True, "成功获取财务指标", preview_meta, summary)


def fetch_valuation_indicators_data(
    ticker: str,
    include_market_comparison: bool,
) -> str:
    """
    获取估值指标（对齐 get_valuation_indicators 输出）。

    Args:
        ticker: 股票代码
        include_market_comparison: 是否包含市场对比

    Returns:
        str: JSON 字符串
    """
    _prepare_runtime()

    overview_text = _alpha_vantage_request({"function": "OVERVIEW", "symbol": ticker})
    overview_payload = _safe_json_load(overview_text) or {}
    data = {
        "pe": overview_payload.get("PERatio"),
        "pb": overview_payload.get("PriceToBookRatio"),
        "ps": overview_payload.get("PriceToSalesRatioTTM"),
        "dividend_yield": overview_payload.get("DividendYield"),
        "update_date": overview_payload.get("LatestQuarter"),
    }
    summary = {
        "data_source": "alpha_vantage",
        "include_market_comparison": include_market_comparison,
    }
    return _build_result(True, "成功获取估值指标", data, summary)


def fetch_earnings_data(
    ticker: str,
    limit: int,
) -> str:
    """
    获取业绩数据（对齐 get_earnings_data 输出）。

    Args:
        ticker: 股票代码
        limit: 预览条数

    Returns:
        str: JSON 字符串
    """
    _prepare_runtime()

    earnings_text = _alpha_vantage_request({"function": "EARNINGS", "symbol": ticker})
    earnings_payload = _safe_json_load(earnings_text) or {}

    annual_records = earnings_payload.get("annualEarnings", []) or []
    quarterly_records = earnings_payload.get("quarterlyEarnings", []) or []

    forecast_preview = [dict(item) for item in quarterly_records[:limit]]
    express_preview = [dict(item) for item in annual_records[:limit]]

    data = {
        "forecast": _build_preview_meta(forecast_preview),
        "express": _build_preview_meta(express_preview),
    }
    summary = {
        "data_source": "alpha_vantage",
        "total_forecast": len(quarterly_records),
        "total_express": len(annual_records),
    }
    return _build_result(True, "成功获取业绩数据", data, summary)


def _parse_cli_args() -> Dict[str, str]:
    """
    解析命令行参数，并从 .env 补全。

    Returns:
        Dict[str, str]: 参数字典
    """
    # 第一阶段：解析参数
    import argparse

    parser = argparse.ArgumentParser(description="运行 TradeSwarm 数据流脚本")
    parser.add_argument("--symbol", required=False, help="股票代码，例如 AAPL")
    parser.add_argument("--start-date", required=False, help="开始日期，YYYY-MM-DD")
    parser.add_argument("--end-date", required=False, help="结束日期，YYYY-MM-DD")
    parser.add_argument("--curr-date", required=False, help="当前日期，YYYY-MM-DD")
    parser.add_argument("--look-back-days", required=False, type=int, help="回看天数")
    parser.add_argument("--limit", required=False, type=int, help="新闻返回数量限制")
    parser.add_argument("--openai-base-url", required=False, help="OpenAI Base URL")
    parser.add_argument("--openai-model", required=False, help="OpenAI 模型名")
    parser.add_argument("--report-type", required=False, choices=["annual", "quarter"], help="报表类型")
    parser.add_argument("--periods", required=False, type=int, help="预览条数")
    parser.add_argument("--indicators", required=False, help="技术指标列表（MA,RSI）")
    parser.add_argument("--indicator-period", required=False, type=int, help="技术指标回看天数")
    parser.add_argument("--include-market-comparison", required=False, help="是否包含市场对比（true/false）")
    parser.add_argument("--earnings-limit", required=False, type=int, help="业绩数据预览条数")

    args = parser.parse_args()

    # 第二阶段：读取 .env 作为默认值
    project_root = Path(__file__).resolve().parents[1]
    env_path = project_root / ".env"
    env_values = dotenv_values(env_path) if env_path.exists() else {}

    def _env_get(key: str) -> Optional[str]:
        return os.getenv(key) or env_values.get(key)

    # 第三阶段：合并参数
    merged = {
        "symbol": args.symbol or _env_get("SYMBOL"),
        "start_date": args.start_date or _env_get("START_DATE"),
        "end_date": args.end_date or _env_get("END_DATE"),
        "curr_date": args.curr_date or _env_get("CURR_DATE"),
        "look_back_days": str(args.look_back_days) if args.look_back_days is not None else _env_get("LOOK_BACK_DAYS"),
        "limit": str(args.limit) if args.limit is not None else _env_get("LIMIT"),
        "openai_base_url": args.openai_base_url or _env_get("OPENAI_BASE_URL"),
        "openai_model": args.openai_model or _env_get("OPENAI_MODEL"),
        "report_type": args.report_type or _env_get("REPORT_TYPE"),
        "periods": str(args.periods) if args.periods is not None else _env_get("PERIODS"),
        "indicators": args.indicators or _env_get("INDICATORS"),
        "indicator_period": str(args.indicator_period) if args.indicator_period is not None else _env_get("INDICATOR_PERIOD"),
        "include_market_comparison": args.include_market_comparison or _env_get("INCLUDE_MARKET_COMPARISON"),
        "earnings_limit": str(args.earnings_limit) if args.earnings_limit is not None else _env_get("EARNINGS_LIMIT"),
    }

    # 第四阶段：校验必需字段
    missing = [key for key, value in merged.items() if not value]
    if missing:
        raise ValueError(f"缺少必需参数（可从 .env 提供）：{', '.join(missing)}")

    return {
        "symbol": merged["symbol"],
        "start_date": merged["start_date"],
        "end_date": merged["end_date"],
        "curr_date": merged["curr_date"],
        "look_back_days": merged["look_back_days"],
        "limit": merged["limit"],
        "openai_base_url": merged["openai_base_url"],
        "openai_model": merged["openai_model"],
        "report_type": merged["report_type"],
        "periods": merged["periods"],
        "indicators": merged["indicators"],
        "indicator_period": merged["indicator_period"],
        "include_market_comparison": merged["include_market_comparison"],
        "earnings_limit": merged["earnings_limit"],
    }


def _save_output(text: str) -> Path:
    """
    保存输出到 scripts 目录下的文件。

    Args:
        text: 要保存的文本

    Returns:
        Path: 输出文件路径
    """
    output_path = Path(__file__).resolve().parent / "dataflows_output.txt"
    output_path.write_text(text, encoding="utf-8")
    return output_path


def _save_output_named(filename: str, text: str) -> Path:
    """
    保存输出到 scripts 目录下指定文件名。

    Args:
        filename: 文件名
        text: 要保存的文本

    Returns:
        Path: 输出文件路径
    """
    output_path = Path(__file__).resolve().parent / filename
    output_path.write_text(text, encoding="utf-8")
    return output_path


def run_all_streams() -> None:
    """
    运行所有数据流并写入文件。
    """
    # 第一阶段：解析参数
    args = _parse_cli_args()

    # 第二阶段：调用 market
    market_text = fetch_market_data(
        symbol=args["symbol"],
        start_date=args["start_date"],
        end_date=args["end_date"],
    )
    # 第三阶段：调用 indicators
    indicators_text = fetch_indicators_data(
        symbol=args["symbol"],
        curr_date=args["curr_date"],
        indicators=args["indicators"],
        period=int(args["indicator_period"]),
    )
    # 第四阶段：调用 news
    news_text = fetch_news_data(
        curr_date=args["curr_date"],
        look_back_days=int(args["look_back_days"]),
        limit=int(args["limit"]),
        openai_base_url=args["openai_base_url"],
        openai_model=args["openai_model"],
        ticker=args["symbol"],
    )
    # 第五阶段：调用 global news
    global_news_text = fetch_global_news_data(
        curr_date=args["curr_date"],
        look_back_days=int(args["look_back_days"]),
        limit=int(args["limit"]),
        openai_base_url=args["openai_base_url"],
        openai_model=args["openai_model"],
    )
    # 第六阶段：调用 company info
    company_info_text = fetch_company_info_data(
        ticker=args["symbol"],
        curr_date=args["curr_date"],
    )
    # 第七阶段：调用 financial statements
    financial_statements_text = fetch_financial_statements_data(
        ticker=args["symbol"],
        report_type=args["report_type"],
        periods=int(args["periods"]),
    )
    # 第八阶段：调用 financial indicators
    financial_indicators_text = fetch_financial_indicators_data(
        ticker=args["symbol"],
        report_type=args["report_type"],
        periods=int(args["periods"]),
    )
    # 第九阶段：调用 valuation indicators
    include_market_comparison = str(args["include_market_comparison"]).lower() == "true"
    valuation_indicators_text = fetch_valuation_indicators_data(
        ticker=args["symbol"],
        include_market_comparison=include_market_comparison,
    )
    # 第十阶段：调用 earnings data
    earnings_text = fetch_earnings_data(
        ticker=args["symbol"],
        limit=int(args["earnings_limit"]),
    )

    # 第十一阶段：调用 sentiments
    sentiments_text = fetch_sentiments_data(
        ticker=args["symbol"],
        start_date=args["start_date"],
        end_date=args["end_date"],
    )

    # 第十二阶段：按 MARKET / NEWS / SENTIMENTS / FUNDAMENTALS 拆分输出
    market_output = "\n\n".join(
        [
            "========== MARKET ==========",
            "=== market.data ===",
            market_text,
            "=== market.indicators ===",
            indicators_text,
        ]
    )
    news_output = "\n\n".join(
        [
            "========== NEWS ==========",
            "=== news.company ===",
            news_text,
            "=== news.global ===",
            global_news_text,
        ]
    )
    sentiments_output = "\n\n".join(
        [
            "========== SENTIMENTS ==========",
            "=== sentiments.company ===",
            sentiments_text,
        ]
    )
    fundamentals_output = "\n\n".join(
        [
            "========== FUNDAMENTALS ==========",
            "=== fundamentals.company_info ===",
            company_info_text,
            "=== fundamentals.financial_statements ===",
            financial_statements_text,
            "=== fundamentals.financial_indicators ===",
            financial_indicators_text,
            "=== fundamentals.valuation_indicators ===",
            valuation_indicators_text,
            "=== fundamentals.earnings_data ===",
            earnings_text,
        ]
    )

    market_path = _save_output_named("market_output.txt", market_output)
    news_path = _save_output_named("news_output.txt", news_output)
    sentiments_path = _save_output_named("sentiments.txt", sentiments_output)
    fundamentals_path = _save_output_named("fundamentals.txt", fundamentals_output)
    print(f"输出已保存: {market_path}")
    print(f"输出已保存: {news_path}")
    print(f"输出已保存: {sentiments_path}")
    print(f"输出已保存: {fundamentals_path}")


if __name__ == "__main__":
    run_all_streams()
