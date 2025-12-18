"""Tushare"""
import tushare as ts
from typing import Optional, Dict
import pandas as pd
from .utils import normalize_stock_code, format_date, extract_stock_code_number


class TushareProvider:
    """Tushare 数据提供者封装类"""
    
    def __init__(self, token: Optional[str] = None, config: Optional[Dict] = None):
        """
        初始化 Tushare Provider

        Args:
            token: Tushare token，可选
            config: 配置字典，必需，用于从配置中读取token

        """
        if token is None:
            if config and 'data_sources' in config and 'tushare_token' in config['data_sources']:
                token = config['data_sources']['tushare_token']
                if token:
                    # 去除可能的引号
                    token = token.strip().strip("'").strip('"')

        if not token:
            raise ValueError("Tushare Token 未设置，请在 config/config.yaml 中设置 data_sources.tushare_token")

        ts.set_token(token)
        self.pro = ts.pro_api()
    
    def get_daily(
        self,
        ts_code: str,
        start_date: str,
        end_date: str,
        trade_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        获取股票日线行情数据
        
        Args:
            ts_code: 股票代码（会自动标准化）
            start_date: 开始日期（格式：YYYYMMDD 或 YYYY-MM-DD）
            end_date: 结束日期（格式：YYYYMMDD 或 YYYY-MM-DD）
            trade_date: 可选，指定交易日期（格式：YYYYMMDD 或 YYYY-MM-DD）
        
        Returns:
            pandas.DataFrame，包含以下字段：
                - ts_code: 股票代码
                - trade_date: 交易日期
                - open: 开盘价
                - high: 最高价
                - low: 最低价
                - close: 收盘价
                - pre_close: 昨收价
                - change: 涨跌额
                - pct_chg: 涨跌幅
                - vol: 成交量（手）
                - amount: 成交额（千元）
        """
        # 标准化股票代码
        ts_code = normalize_stock_code(ts_code)
        
        # 格式化日期
        start_date = format_date(start_date)
        end_date = format_date(end_date)
        
        try:
            if trade_date:
                # 如果指定了交易日期，使用 trade_date 参数
                trade_date = format_date(trade_date)
                df = self.pro.daily(
                    ts_code=ts_code,
                    trade_date=trade_date
                )
            else:
                # 使用日期范围查询
                df = self.pro.daily(
                    ts_code=ts_code,
                    start_date=start_date,
                    end_date=end_date
                )
            
            if df is None or df.empty:
                return pd.DataFrame()
            
            # 按交易日期排序（升序）
            df = df.sort_values('trade_date', ascending=True)
            
            return df
            
        except Exception as e:
            raise Exception(f"获取股票数据失败: {str(e)}")
    
    def get_stock_basic(self, ts_code: Optional[str] = None) -> pd.DataFrame:
        """
        获取股票基本信息
        
        Args:
            ts_code: 可选，股票代码。如果不提供，返回所有股票基本信息
        
        Returns:
            pandas.DataFrame，包含股票基本信息
        """
        try:
            if ts_code:
                ts_code = normalize_stock_code(ts_code)
                df = self.pro.stock_basic(
                    exchange='',
                    list_status='L',
                    fields='ts_code,symbol,name,area,industry,market,list_date'
                )
                df = df[df['ts_code'] == ts_code]
            else:
                df = self.pro.stock_basic(
                    exchange='',
                    list_status='L',
                    fields='ts_code,symbol,name,area,industry,market,list_date'
                )
            
            return df if df is not None else pd.DataFrame()
            
        except Exception as e:
            raise Exception(f"获取股票基本信息失败: {str(e)}")
    
    def get_realtime_orderbook(
        self,
        ts_code: str,
        return_format: str = "dict"
    ) -> dict:
        """
        获取实时五档盘口数据
        
        策略：
        1. 优先使用 Tushare Pro API（如果可用）
        2. 如果 Pro API 失败，fallback 到旧版爬虫接口（get_realtime_quotes）
        3. 如果使用旧版接口，会给出警告提示
        
        Args:
            ts_code: 股票代码，支持以下格式：
                - '000001' (6位数字)
                - '000001.SZ' (带后缀)
                - '600000.SH' (带后缀)
            return_format: 返回格式，可选：
                - 'dict': 返回字典格式（默认，包含结构化数据）
                - 'markdown': 返回 Markdown 格式字符串（便于 Agent 阅读）
        
        Returns:
            如果 return_format='dict'，返回字典，包含以下字段：
                - name: 股票名称
                - code: 股票代码（纯数字）
                - price: 当前价格
                - pre_close: 昨收价
                - change_pct: 涨跌幅（百分比）
                - ask_prices: 卖盘价格列表（卖5到卖1）
                - ask_volumes: 卖盘挂单量列表
                - bid_prices: 买盘价格列表（买1到买5）
                - bid_volumes: 买盘挂单量列表
                - data_source: 数据来源（'pro_api' 或 'legacy_crawler'）
            
            如果 return_format='markdown'，返回 Markdown 格式字符串
        
        Note:
            - 返回格式说明：
              * dict 格式：适合程序处理和进一步分析
              * markdown 格式：适合直接展示给 Agent 阅读
            - 如果使用旧版爬虫接口，会在返回的字典中添加 'warning' 字段提示
        """
        import warnings
        
        # 提取纯数字代码
        clean_symbol = extract_stock_code_number(ts_code)
        
        # 策略1: 优先使用 Pro API
        try:
            # 标准化代码（Pro API）
            ts_code_normalized = normalize_stock_code(ts_code)
            
            # Pro API 的实时行情接口比较快，但需要5000分
            try:
                df = self.pro.quote(
                    ts_code=ts_code_normalized,
                    fields='ts_code,name,price,pre_close,pct_chg,vol,amount,open,high,low'
                )
                
                if df is not None and not df.empty:
                    row = df.iloc[0]
                    
                    result = {
                        "name": str(row.get('name', '')),
                        "code": clean_symbol,
                        "price": float(row.get('price', 0)),
                        "pre_close": float(row.get('pre_close', 0)),
                        "change_pct": float(row.get('pct_chg', 0)),
                        "vol": float(row.get('vol', 0)),
                        "amount": float(row.get('amount', 0)),
                        "open": float(row.get('open', 0)),
                        "high": float(row.get('high', 0)),
                        "low": float(row.get('low', 0)),
                        "ask_prices": [],  # Pro API 可能不提供五档数据
                        "ask_volumes": [],
                        "bid_prices": [],
                        "bid_volumes": [],
                        "data_source": "pro_api"
                    }
                    
                    if return_format == "markdown":
                        return self._format_orderbook_markdown(result)
                    
                    return result
                    
            except (AttributeError, Exception) as pro_error:
                # Pro API 接口不可用或需要权限，继续尝试旧版接口
                pass
        
        except Exception as pro_error:
            # Pro API 初始化或调用失败，继续尝试旧版接口
            pass
        
        # 策略2: Fallback 到旧版爬虫接口（延迟也能接受，我测试了一下大概60ms左右）
        try:
            warnings.warn(
                f"⚠️ Tushare Pro API 不可用或需要权限，已切换到旧版爬虫接口获取 {clean_symbol} 的实时数据。"
                f"建议：检查 Tushare Pro API 权限或升级积分。",
                UserWarning
            )
            
            # 旧版接口
            df = ts.get_realtime_quotes(clean_symbol)
            
            if df is None or df.empty:
                raise Exception(f"找不到股票 {clean_symbol} 的实时行情")
            
            row = df.iloc[0]
            name = str(row['name'])
            price = float(row['price'])
            pre_close = float(row['pre_close'])
            change_pct = (price - pre_close) / pre_close * 100 if pre_close > 0 else 0
            
            # 提取五档盘口数据
            ask_prices = []
            ask_volumes = []
            bid_prices = []
            bid_volumes = []
            
            # 卖盘 (卖5 -> 卖1)
            for i in range(5, 0, -1):
                try:
                    ask_prices.append(float(row[f'a{i}_p']))
                    ask_volumes.append(int(row[f'a{i}_v']))
                except (KeyError, ValueError):
                    ask_prices.append(0.0)
                    ask_volumes.append(0)
            
            # 买盘 (买1 -> 买5)
            for i in range(1, 6):
                try:
                    bid_prices.append(float(row[f'b{i}_p']))
                    bid_volumes.append(int(row[f'b{i}_v']))
                except (KeyError, ValueError):
                    bid_prices.append(0.0)
                    bid_volumes.append(0)
            
            result = {
                "name": name,
                "code": clean_symbol,
                "price": price,
                "pre_close": pre_close,
                "change_pct": change_pct,
                "ask_prices": ask_prices,
                "ask_volumes": ask_volumes,
                "bid_prices": bid_prices,
                "bid_volumes": bid_volumes,
                "data_source": "legacy_crawler",
                "warning": "使用旧版爬虫接口，数据可能不如 Pro API 稳定"
            }
            
            # 如果请求 markdown 格式，转换为 markdown
            if return_format == "markdown":
                return self._format_orderbook_markdown(result)
            
            return result
            
        except Exception as e:
            raise Exception(f"获取实时盘口失败: {str(e)}")
    
    def _format_orderbook_markdown(self, data: dict) -> str:
        """
        将盘口数据格式化为 Markdown 字符串
        
        Args:
            data: 盘口数据字典
        
        Returns:
            Markdown 格式字符串
        """
        md = f"### 📊 {data['name']} ({data['code']}) 实时盘口\n"
        md += f"**现价**: {data['price']:.2f} ({data['change_pct']:+.2f}%)\n"
        
        if data.get('data_source') == 'legacy_crawler':
            md += f"*⚠️ {data.get('warning', '')}*\n"
        
        md += "\n"
        md += "| 档位 | 价格 | 挂单量 |\n"
        md += "| :--- | :--- | :--- |\n"
        
        # 卖盘 (卖5 -> 卖1)
        ask_prices = data.get('ask_prices', [])
        ask_volumes = data.get('ask_volumes', [])
        if ask_prices:
            for i in range(len(ask_prices) - 1, -1, -1):
                level = 5 - i
                p = ask_prices[i]
                v = ask_volumes[i] if i < len(ask_volumes) else 0
                if p > 0:  # 只显示有价格的档位
                    md += f"| 🟢 卖{level} | {p:.2f} | {v} |\n"
        
        # 买盘 (买1 -> 买5)
        bid_prices = data.get('bid_prices', [])
        bid_volumes = data.get('bid_volumes', [])
        if bid_prices:
            for i in range(len(bid_prices)):
                level = i + 1
                p = bid_prices[i]
                v = bid_volumes[i] if i < len(bid_volumes) else 0
                if p > 0:  # 只显示有价格的档位
                    md += f"| 🔴 买{level} | {p:.2f} | {v} |\n"
        
        return md
    
    # ==================== fundamentals ====================
    
    def get_company_info(self, ts_code: Optional[str] = None) -> dict:
        """
        获取公司基本信息
        
        Args:
            ts_code: 股票代码
        
        Returns:
            包含公司基本信息的字典
        """
        try:
            df = self.get_stock_basic(ts_code)
            
            if df is None or df.empty:
                return {"error": "未找到公司基本信息"}
            
            row = df.iloc[0]
            return {
                "symbol": row.get('ts_code', ''),
                "name": row.get('name', ''),
                "industry": row.get('industry', ''),
                "area": row.get('area', ''),
                "market": row.get('market', ''),
                "list_date": row.get('list_date', ''),
                "data": row.to_dict()
            }
        except Exception as e:
            return {"error": f"获取公司信息失败: {str(e)}"}
    
    def get_income(
        self,
        ts_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        period: Optional[str] = None
    ) -> pd.DataFrame:
        """
        获取利润表数据
        
        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            period: 报告期（YYYYMMDD）
        
        Returns:
            利润表 DataFrame
        """
        ts_code = normalize_stock_code(ts_code)
        
        try:
            if period:
                period = format_date(period)
                df = self.pro.income(ts_code=ts_code, period=period)
            elif start_date and end_date:
                start_date = format_date(start_date)
                end_date = format_date(end_date)
                df = self.pro.income(
                    ts_code=ts_code,
                    start_date=start_date,
                    end_date=end_date
                )
            else:
                # 获取最近4期
                df = self.pro.income(ts_code=ts_code)
                if df is not None and not df.empty:
                    df = df.head(4)
            
            return df if df is not None else pd.DataFrame()
        except Exception as e:
            raise Exception(f"获取利润表失败: {str(e)}")
    
    def get_balancesheet(
        self,
        ts_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        period: Optional[str] = None
    ) -> pd.DataFrame:
        """
        获取资产负债表数据
        
        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            period: 报告期（YYYYMMDD）
        
        Returns:
            资产负债表 DataFrame
        """
        ts_code = normalize_stock_code(ts_code)
        
        try:
            if period:
                period = format_date(period)
                df = self.pro.balancesheet(ts_code=ts_code, period=period)
            elif start_date and end_date:
                start_date = format_date(start_date)
                end_date = format_date(end_date)
                df = self.pro.balancesheet(
                    ts_code=ts_code,
                    start_date=start_date,
                    end_date=end_date
                )
            else:
                # 获取最近4期
                df = self.pro.balancesheet(ts_code=ts_code)
                if df is not None and not df.empty:
                    df = df.head(4)
            
            return df if df is not None else pd.DataFrame()
        except Exception as e:
            raise Exception(f"获取资产负债表失败: {str(e)}")
    
    def get_cashflow(
        self,
        ts_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        period: Optional[str] = None
    ) -> pd.DataFrame:
        """
        获取现金流量表数据
        
        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            period: 报告期（YYYYMMDD）
        
        Returns:
            现金流量表 DataFrame
        """
        ts_code = normalize_stock_code(ts_code)
        
        try:
            if period:
                period = format_date(period)
                df = self.pro.cashflow(ts_code=ts_code, period=period)
            elif start_date and end_date:
                start_date = format_date(start_date)
                end_date = format_date(end_date)
                df = self.pro.cashflow(
                    ts_code=ts_code,
                    start_date=start_date,
                    end_date=end_date
                )
            else:
                # 获取最近4期
                df = self.pro.cashflow(ts_code=ts_code)
                if df is not None and not df.empty:
                    df = df.head(4)
            
            return df if df is not None else pd.DataFrame()
        except Exception as e:
            raise Exception(f"获取现金流量表失败: {str(e)}")
    
    def get_fina_indicator(
        self,
        ts_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        period: Optional[str] = None
    ) -> pd.DataFrame:
        """
        获取财务指标数据
        
        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            period: 报告期（YYYYMMDD）
        
        Returns:
            财务指标 DataFrame
        """
        ts_code = normalize_stock_code(ts_code)
        
        try:
            if period:
                period = format_date(period)
                df = self.pro.fina_indicator(ts_code=ts_code, period=period)
            elif start_date and end_date:
                start_date = format_date(start_date)
                end_date = format_date(end_date)
                df = self.pro.fina_indicator(
                    ts_code=ts_code,
                    start_date=start_date,
                    end_date=end_date
                )
            else:
                # 获取最近4期
                df = self.pro.fina_indicator(ts_code=ts_code)
                if df is not None and not df.empty:
                    df = df.head(4)
            
            return df if df is not None else pd.DataFrame()
        except Exception as e:
            raise Exception(f"获取财务指标失败: {str(e)}")
    
    def get_daily_basic(
        self,
        ts_code: str,
        trade_date: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        获取每日基本面指标（PE、PB、PS等）
        
        Args:
            ts_code: 股票代码
            trade_date: 交易日期
            start_date: 开始日期
            end_date: 结束日期
        
        Returns:
            每日基本面指标 DataFrame
        """
        ts_code = normalize_stock_code(ts_code)
        
        try:
            if trade_date:
                trade_date = format_date(trade_date)
                df = self.pro.daily_basic(ts_code=ts_code, trade_date=trade_date)
            elif start_date and end_date:
                start_date = format_date(start_date)
                end_date = format_date(end_date)
                df = self.pro.daily_basic(
                    ts_code=ts_code,
                    start_date=start_date,
                    end_date=end_date
                )
            else:
                # 获取最近一条
                df = self.pro.daily_basic(ts_code=ts_code)
                if df is not None and not df.empty:
                    df = df.head(1)
            
            return df if df is not None else pd.DataFrame()
        except Exception as e:
            raise Exception(f"获取每日基本面指标失败: {str(e)}")
    
    def get_forecast(
        self,
        ts_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 10
    ) -> pd.DataFrame:
        """
        获取业绩预告
        
        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            limit: 返回最近 N 条
        
        Returns:
            业绩预告 DataFrame
        """
        ts_code = normalize_stock_code(ts_code)
        
        try:
            if start_date and end_date:
                start_date = format_date(start_date)
                end_date = format_date(end_date)
                df = self.pro.forecast(
                    ts_code=ts_code,
                    start_date=start_date,
                    end_date=end_date
                )
            else:
                df = self.pro.forecast(ts_code=ts_code)
            
            if df is not None and not df.empty and limit > 0:
                df = df.head(limit)
            
            return df if df is not None else pd.DataFrame()
        except Exception as e:
            raise Exception(f"获取业绩预告失败: {str(e)}")
    
    def get_express(
        self,
        ts_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 10
    ) -> pd.DataFrame:
        """
        获取业绩快报
        
        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            limit: 返回最近 N 条
        
        Returns:
            业绩快报 DataFrame
        """
        ts_code = normalize_stock_code(ts_code)
        
        try:
            if start_date and end_date:
                start_date = format_date(start_date)
                end_date = format_date(end_date)
                df = self.pro.express(
                    ts_code=ts_code,
                    start_date=start_date,
                    end_date=end_date
                )
            else:
                df = self.pro.express(ts_code=ts_code)
            
            if df is not None and not df.empty and limit > 0:
                df = df.head(limit)
            
            return df if df is not None else pd.DataFrame()
        except Exception as e:
            raise Exception(f"获取业绩快报失败: {str(e)}")
