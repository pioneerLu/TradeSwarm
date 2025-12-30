"""基本面分析工具"""
import json
import re
from typing import Optional
from langchain_core.tools import tool
from tradingagents.data_sources.tushare_provider import TushareProvider
from tradingagents.data_sources.akshare_provider import AkshareProvider
from tradingagents.data_sources.utils import normalize_stock_code


def _df_to_preview(df, limit: int = 5):
    """
    将 DataFrame 转换为预览数据和元信息，限制返回条数。
    返回: (records, meta)
    """
    if df is None:
        return None, {"total_rows": 0, "columns": []}
    if hasattr(df, "empty") and df.empty:
        return None, {"total_rows": 0, "columns": list(df.columns)}
    # 截断
    preview_df = df.head(limit) if limit and hasattr(df, "head") else df
    try:
        records = preview_df.to_dict("records")
    except Exception:
        records = []
    meta = {
        "total_rows": len(df) if hasattr(df, "__len__") else 0,
        "preview_rows": len(preview_df) if hasattr(preview_df, "__len__") else 0,
        "columns": list(df.columns) if hasattr(df, "columns") else [],
    }
    return records, meta


def _get_latest_row(df):
    if df is None or getattr(df, "empty", True):
        return None
    try:
        return df.iloc[0].to_dict()
    except Exception:
        return None


def _pick_fields(row: dict, fields: list, alias: dict = None):
    if row is None:
        return None
    data = {}
    for k in fields:
        v = row.get(k)
        data[k] = v
    if alias:
        for old, new in alias.items():
            if old in row:
                data[new] = row.get(old)
    return data


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
def get_company_info(ts_code: str) -> str:
    """
    获取公司基本信息
    
    此工具用于获取指定股票代码的公司基本信息，包括公司名称、所属行业、上市日期、股本等。
    优先使用 AkShare 获取公司信息，失败时使用 Tushare 作为备选。
    
    Args:
        ts_code: 股票代码，支持以下格式：
            - '000001' (6位数字，会自动识别市场)
            - '000001.SZ' (深圳市场)
            - '600000.SH' (上海市场)
            示例：'000001' 或 '600000'
    
    Returns:
        JSON 格式的字符串，包含以下字段：
        - success: 是否成功
        - message: 提示信息
        - data: 公司基本信息字典，包含：
            - symbol: 股票代码
            - name: 公司名称
            - industry: 所属行业
            - list_date: 上市日期
            - 其他相关信息
        - summary: 数据摘要
    
    Examples:
        >>> get_company_info('000001')
        '{"success": true, "data": {...}, "summary": {...}}'
    """
    try:
        # 首先尝试使用 AkShare
        try:
            ak_provider = _get_akshare_provider()
            result = ak_provider.get_company_info(ts_code)
            
            if "error" in result:
                raise Exception(result["error"])
            
            return json.dumps({
                "success": True,
                "message": f"成功从 AkShare 获取股票 {ts_code} 的公司信息",
                "data": result,
                "summary": {
                    "data_source": "akshare",
                    "symbol": result.get("symbol", ts_code)
                }
            }, ensure_ascii=False, indent=2, default=str)
            
        except Exception as ak_error:
            # AkShare 失败，尝试使用 Tushare 作为备选
            try:
                tushare_provider = _get_tushare_provider()
                result = tushare_provider.get_company_info(ts_code)
                
                if "error" in result:
                    raise Exception(result["error"])
                
                return json.dumps({
                    "success": True,
                    "message": f"成功从 Tushare 获取股票 {ts_code} 的公司信息（AkShare 失败，已使用备选数据源）",
                    "data": result,
                    "summary": {
                        "data_source": "tushare",
                        "symbol": result.get("symbol", ts_code)
                    }
                }, ensure_ascii=False, indent=2, default=str)
                
            except Exception as tushare_error:
                return json.dumps({
                    "success": False,
                    "message": f"获取公司信息失败。AkShare 错误: {str(ak_error)[:100]}。Tushare 错误: {str(tushare_error)[:100]}。",
                    "data": {},
                    "summary": {
                        "data_source": "error",
                        "symbol": ts_code
                    }
                }, ensure_ascii=False, indent=2)
    
    except Exception as e:
        return json.dumps({
            "success": False,
            "message": f"获取公司信息时发生错误: {str(e)}",
            "data": {},
            "summary": {}
        }, ensure_ascii=False, indent=2)


@tool
def get_financial_statements(
    ts_code: str,
    report_type: Optional[str] = "annual",
    periods: Optional[int] = 4
) -> str:
    """
    获取三大财务报表（利润表、资产负债表、现金流量表）
    
    此工具用于获取指定股票的三大财务报表数据，支持年度和季度报告。
    优先使用 AkShare 获取财务报表，失败时使用 Tushare 作为备选。
    
    Args:
        ts_code: 股票代码，支持以下格式：
            - '000001' (6位数字)
            - '000001.SZ' (深圳市场)
            - '600000.SH' (上海市场)
        report_type: 报告类型，可选值：
            - 'annual': 年度报告（默认）
            - 'quarter': 季度报告
        periods: 获取最近 N 期数据（默认 4 期）
    
    Returns:
        JSON 格式的字符串，包含以下字段：
        - success: 是否成功
        - message: 提示信息
        - data: 包含以下字段的字典：
            - income: 利润表数据（列表）
            - balance: 资产负债表数据（列表）
            - cashflow: 现金流量表数据（列表）
            - errors: 错误列表（如果有）
        - summary: 数据摘要
    
    Examples:
        >>> get_financial_statements('000001', report_type='annual', periods=4)
        '{"success": true, "data": {...}, "summary": {...}}'
    """
    try:
        # AK的财务报表接口有点问题
        if report_type not in ["annual", "quarter"]:
            report_type = "annual"

        tushare_provider = _get_tushare_provider()
        ts_code_normalized = normalize_stock_code(ts_code)
        
        income_df = tushare_provider.get_income(ts_code_normalized)
        balance_df = tushare_provider.get_balancesheet(ts_code_normalized)
        cashflow_df = tushare_provider.get_cashflow(ts_code_normalized)

        # 核心字段提取（最新一条）
        income_row = _get_latest_row(income_df)
        balance_row = _get_latest_row(balance_df)
        cashflow_row = _get_latest_row(cashflow_df)

        income_core = _pick_fields(
            income_row,
            [
                "ann_date",
                "end_date",
                "revenue",
                "total_revenue",
                "operate_profit",
                "n_income",
                "basic_eps",
            ],
        )

        balance_core = _pick_fields(
            balance_row,
            [
                "ann_date",
                "end_date",
                "total_assets",
                "total_liab",
                "total_hldr_eqy_exc_min_int",
                "depos",
                "loanto_oth_bank_fi",
            ],
        )

        cashflow_core = _pick_fields(
            cashflow_row,
            [
                "ann_date",
                "end_date",
                "n_cashflow_act",
                "n_cashflow_inv_act",
                "n_cash_flows_fnc_act",
                "n_incr_cash_cash_equ",
            ],
        )

        income_preview, income_meta = _df_to_preview(income_df, limit=periods or 5)
        balance_preview, balance_meta = _df_to_preview(balance_df, limit=periods or 5)
        cashflow_preview, cashflow_meta = _df_to_preview(cashflow_df, limit=periods or 5)

        result = {
            "symbol": ts_code_normalized,
            "report_type": report_type,
            "income": income_preview,
            "balance": balance_preview,
            "cashflow": cashflow_preview,
            "meta": {
                "income": income_meta,
                "balance": balance_meta,
                "cashflow": cashflow_meta,
            },
            "core": {
                "income": income_core,
                "balance": balance_core,
                "cashflow": cashflow_core,
            },
            "errors": []
        }
        
        if result["income"] is None:
            result["errors"].append("利润表数据为空")
        if result["balance"] is None:
            result["errors"].append("资产负债表数据为空")
        if result["cashflow"] is None:
            result["errors"].append("现金流量表数据为空")
        
        return json.dumps({
            "success": True,
            "message": f"成功从 Tushare 获取股票 {ts_code} 的财务报表",
            "data": result,
            "summary": {
                "data_source": "tushare",
                "symbol": ts_code_normalized,
                "report_type": report_type,
                "periods": periods
            }
        }, ensure_ascii=False, indent=2, default=str)

    except Exception as e:
        return json.dumps({
            "success": False,
            "message": f"获取财务报表时发生错误: {str(e)}",
            "data": {},
            "summary": {}
        }, ensure_ascii=False, indent=2)


@tool
def get_financial_indicators(
    ts_code: str,
    report_type: Optional[str] = "annual",
    periods: Optional[int] = 4
) -> str:
    """
    获取财务指标（ROE、ROA、毛利率、净利率等）
    
    此工具用于获取指定股票的财务分析指标，包括盈利能力、成长能力、偿债能力等指标。
    优先使用 AkShare 获取财务指标，失败时使用 Tushare 作为备选。
    
    Args:
        ts_code: 股票代码，支持以下格式：
            - '000001' (6位数字)
            - '000001.SZ' (深圳市场)
            - '600000.SH' (上海市场)
        report_type: 报告类型，可选值：
            - 'annual': 年度报告（默认）
            - 'quarter': 季度报告
        periods: 获取最近 N 期数据（默认 4 期）
    
    Returns:
        JSON 格式的字符串，包含以下字段：
        - success: 是否成功
        - message: 提示信息
        - data: 财务指标数据（列表）
        - summary: 数据摘要
    
    Examples:
        >>> get_financial_indicators('000001', report_type='annual', periods=4)
        '{"success": true, "data": {...}, "summary": {...}}'
    """
    try:
        if report_type not in ["annual", "quarter"]:
            report_type = "annual"

        tushare_provider = _get_tushare_provider()
        ts_code_normalized = normalize_stock_code(ts_code)
        df = tushare_provider.get_fina_indicator(ts_code_normalized)
        preview, meta = _df_to_preview(df, limit=periods or 5)

        latest = _get_latest_row(df)
        core = _pick_fields(
            latest,
            [
                "ann_date",
                "end_date",
                "eps",
                "dt_eps",
                "roe",
                "roe_dt",
                "netprofit_margin",
                "debt_to_assets",
                "assets_to_eqt",
                "bps",
                "ocfps",
                "q_sales_yoy",
                "q_op_qoq",
                "equity_yoy",
            ],
        )

        if preview is None:
            return json.dumps({
                "success": False,
                "message": "Tushare 财务指标数据为空",
                "data": {},
                "summary": {"data_source": "tushare", "symbol": ts_code_normalized}
            }, ensure_ascii=False, indent=2)

        return json.dumps({
            "success": True,
            "message": f"成功从 Tushare 获取股票 {ts_code} 的财务指标",
            "data": {
                "symbol": ts_code_normalized,
                "report_type": report_type,
                "data": preview,
                "meta": meta,
                "core": core
            },
            "summary": {
                "data_source": "tushare",
                "symbol": ts_code_normalized,
                "report_type": report_type,
                "periods": periods
            }
        }, ensure_ascii=False, indent=2, default=str)
    
    except Exception as e:
        return json.dumps({
            "success": False,
            "message": f"获取财务指标时发生错误: {str(e)}",
            "data": {},
            "summary": {}
        }, ensure_ascii=False, indent=2)


@tool
def get_valuation_indicators(
    ts_code: str,
    include_market_comparison: Optional[bool] = True
) -> str:
    """
    获取估值指标（PE、PB、PS、股息率等）
    
    此工具用于获取指定股票的估值指标，包括市盈率（PE）、市净率（PB）、市销率（PS）、股息率等。
    可选包含市场/行业对比数据。
    优先使用 AkShare 获取估值指标，失败时使用 Tushare 作为备选。
    
    Args:
        ts_code: 股票代码，支持以下格式：
            - '000001' (6位数字)
            - '000001.SZ' (深圳市场)
            - '600000.SH' (上海市场)
        include_market_comparison: 是否包含市场/行业对比（默认 True）
    
    Returns:
        JSON 格式的字符串，包含以下字段：
        - success: 是否成功
        - message: 提示信息
        - data: 估值指标数据，包含：
            - pe_pb: PE/PB 数据
            - dividend: 分红数据
            - market_comparison: 市场对比数据（如果请求）
        - summary: 数据摘要
    
    Examples:
        >>> get_valuation_indicators('000001', include_market_comparison=True)
        '{"success": true, "data": {...}, "summary": {...}}'
    """
    try:
        tushare_provider = _get_tushare_provider()
        ts_code_normalized = normalize_stock_code(ts_code)
        
        df = tushare_provider.get_daily_basic(ts_code_normalized)
        preview, meta = _df_to_preview(df, limit=1)
        latest = _get_latest_row(df)
        core = _pick_fields(
            latest,
            [
                "trade_date",
                "close",
                "pe",
                "pe_ttm",
                "pb",
                "ps",
                "ps_ttm",
                "total_mv",
                "circ_mv",
            ],
        )

        if preview is None:
            return json.dumps({
                "success": False,
                "message": "Tushare 估值指标数据为空",
                "data": {},
                "summary": {"data_source": "tushare", "symbol": ts_code_normalized}
            }, ensure_ascii=False, indent=2)
        
        return json.dumps({
            "success": True,
            "message": f"成功从 Tushare 获取股票 {ts_code} 的估值指标",
            "data": {
                "symbol": ts_code_normalized,
                "pe_pb": preview,
                "dividend": None,
                "market_comparison": None,
                "meta": meta,
                "core": core,
                "errors": []
            },
            "summary": {
                "data_source": "tushare",
                "symbol": ts_code_normalized,
                "include_market_comparison": include_market_comparison
            }
        }, ensure_ascii=False, indent=2, default=str)
    
    except Exception as e:
        return json.dumps({
            "success": False,
            "message": f"获取估值指标时发生错误: {str(e)}",
            "data": {},
            "summary": {}
        }, ensure_ascii=False, indent=2)


@tool
def get_earnings_data(
    ts_code: str,
    limit: Optional[int] = 10
) -> str:
    """
    获取业绩预告、快报数据
    
    此工具用于获取指定股票的业绩预告和业绩快报数据。
    优先使用 AkShare 获取业绩数据，失败时使用 Tushare 作为备选。
    
    Args:
        ts_code: 股票代码，支持以下格式：
            - '000001' (6位数字)
            - '000001.SZ' (深圳市场)
            - '600000.SH' (上海市场)
        limit: 返回最近 N 条记录（默认 10 条）
    
    Returns:
        JSON 格式的字符串，包含以下字段：
        - success: 是否成功
        - message: 提示信息
        - data: 业绩数据，包含：
            - forecast: 业绩预告数据（列表）
            - express: 业绩快报数据（列表）
            - errors: 错误列表（如果有）
        - summary: 数据摘要
    
    Examples:
        >>> get_earnings_data('000001', limit=10)
        '{"success": true, "data": {...}, "summary": {...}}'
    """
    try:
        try:
            ak_provider = _get_akshare_provider()
            result = ak_provider.get_earnings_data(ts_code, limit)
            
            forecast = result.get("forecast") if isinstance(result, dict) else None
            express = result.get("express") if isinstance(result, dict) else None
            
            if (forecast and isinstance(forecast, list) and len(forecast) > limit):
                forecast = forecast[:limit]
            if (express and isinstance(express, list) and len(express) > limit):
                express = express[:limit]
            
            if ("error" in result) or (forecast is None and express is None):
                raise Exception(result.get("error") or "AkShare 业绩数据为空，尝试 fallback")
            
            # 核心字段压缩
            def _trim_forecast(items):
                if not items:
                    return None
                trimmed = []
                for it in items[:limit]:
                    trimmed.append({
                        "ann_date": it.get("公告日期") or it.get("ann_date"),
                        "end_date": it.get("报告时间") or it.get("end_date"),
                        "summary": it.get("summary") or it.get("summary", ""),
                        "type": it.get("type") or it.get("预测指标"),
                        "p_change_min": it.get("p_change_min") or it.get("业绩变动幅度"),
                        "p_change_max": it.get("p_change_max"),
                    })
                return trimmed

            def _trim_express(items):
                if not items:
                    return None
                trimmed = []
                for it in items[:limit]:
                    trimmed.append({
                        "ann_date": it.get("公告日期") or it.get("ann_date"),
                        "end_date": it.get("end_date"),
                        "revenue": it.get("营业收入-营业收入") or it.get("revenue"),
                        "n_income": it.get("净利润-净利润") or it.get("n_income"),
                        "eps": it.get("每股收益") or it.get("diluted_eps") or it.get("eps"),
                        "total_assets": it.get("total_assets"),
                        "equity": it.get("total_hldr_eqy_exc_min_int"),
                    })
                return trimmed

            forecast_core = _trim_forecast(forecast)
            express_core = _trim_express(express)

            return json.dumps({
                "success": True,
                "message": f"成功从 AkShare 获取股票 {ts_code} 的业绩数据",
                "data": {
                    "symbol": result.get("symbol", ts_code),
                    "forecast": forecast,
                    "express": express,
                    "core": {
                        "forecast": forecast_core,
                        "express": express_core
                    },
                    "errors": result.get("errors", [])
                },
                "summary": {
                    "data_source": "akshare",
                    "symbol": result.get("symbol", ts_code),
                    "limit": limit,
                    "forecast_count": len(forecast) if forecast else 0,
                    "express_count": len(express) if express else 0
                }
            }, ensure_ascii=False, indent=2, default=str)
            
        except Exception as ak_error:
            # 直接使用 Tushare
            try:
                tushare_provider = _get_tushare_provider()
                ts_code_normalized = normalize_stock_code(ts_code)
                
                forecast_df = tushare_provider.get_forecast(ts_code_normalized, limit=limit)
                express_df = tushare_provider.get_express(ts_code_normalized, limit=limit)

                forecast_preview, forecast_meta = _df_to_preview(forecast_df, limit=limit or 5)
                express_preview, express_meta = _df_to_preview(express_df, limit=limit or 5)

                forecast_core = None
                express_core = None
                if forecast_preview:
                    forecast_core = []
                    for it in forecast_preview:
                        forecast_core.append({
                            "ann_date": it.get("ann_date"),
                            "end_date": it.get("end_date"),
                            "type": it.get("type"),
                            "p_change_min": it.get("p_change_min"),
                            "p_change_max": it.get("p_change_max"),
                            "summary": it.get("summary"),
                        })
                if express_preview:
                    express_core = []
                    for it in express_preview:
                        express_core.append({
                            "ann_date": it.get("ann_date"),
                            "end_date": it.get("end_date"),
                            "revenue": it.get("revenue"),
                            "n_income": it.get("n_income"),
                            "eps": it.get("diluted_eps") or it.get("eps"),
                            "total_assets": it.get("total_assets"),
                            "equity": it.get("total_hldr_eqy_exc_min_int"),
                        })
                
                result = {
                    "symbol": ts_code_normalized,
                    "forecast": forecast_preview,
                    "express": express_preview,
                    "meta": {
                        "forecast": forecast_meta,
                        "express": express_meta
                    },
                    "core": {
                        "forecast": forecast_core,
                        "express": express_core
                    },
                    "errors": []
                }
                
                if result["forecast"] is None:
                    result["errors"].append("业绩预告数据为空")
                if result["express"] is None:
                    result["errors"].append("业绩快报数据为空")
                
                return json.dumps({
                    "success": True,
                    "message": f"成功从 Tushare 获取股票 {ts_code} 的业绩数据（AkShare 不可用）",
                    "data": result,
                    "summary": {
                        "data_source": "tushare",
                        "symbol": ts_code_normalized,
                        "limit": limit,
                        "forecast_count": forecast_meta.get("total_rows", 0),
                        "express_count": express_meta.get("total_rows", 0)
                    }
                }, ensure_ascii=False, indent=2, default=str)
                
            except Exception as tushare_error:
                return json.dumps({
                    "success": False,
                    "message": f"获取业绩数据失败。AkShare 错误: {str(ak_error)[:100]}。Tushare 错误: {str(tushare_error)[:100]}。",
                    "data": {
                        "symbol": ts_code,
                        "forecast": None,
                        "express": None,
                        "errors": [str(ak_error), str(tushare_error)]
                    },
                    "summary": {
                        "data_source": "error",
                        "symbol": ts_code
                    }
                }, ensure_ascii=False, indent=2)
    
    except Exception as e:
        return json.dumps({
            "success": False,
            "message": f"获取业绩数据时发生错误: {str(e)}",
            "data": {},
            "summary": {}
        }, ensure_ascii=False, indent=2)

