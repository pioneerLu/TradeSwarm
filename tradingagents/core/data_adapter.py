#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据适配器

封装数据加载功能，提供统一的数据接口。
"""

import pandas as pd
from typing import Optional, List
from datetime import datetime, timedelta

from .data.loader import load_stock_data


class DataAdapter:
    """数据适配器"""
    
    def __init__(self, use_cache: bool = True):
        self.use_cache = use_cache
    
    def load_stock_data_until(self, symbol: str, date: str, start_date: Optional[str] = None) -> Optional[pd.DataFrame]:
        """加载截止到指定日期的股票数据"""
        try:
            if start_date is None:
                from datetime import datetime, timedelta
                date_obj = datetime.strptime(date, "%Y-%m-%d")
                start_date_obj = date_obj - timedelta(days=90)
                start_date = start_date_obj.strftime("%Y-%m-%d")
            
            df = load_stock_data(symbol, start_date, date, use_cache=self.use_cache)
            
            if df is None or len(df) == 0:
                return None
            
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)
            # 与 date 比较时统一时区：若 index 带时区则把截止日转为同一时区，避免 Invalid comparison
            cutoff = pd.to_datetime(date)
            if df.index.tz is not None:
                cutoff = cutoff.tz_localize(df.index.tz)
            df = df[df.index <= cutoff]
            return df
        except Exception as e:
            print(f"[DataAdapter] 加载 {symbol} 数据失败: {e}")
            return None
    
    def get_price(self, symbol: str, date: str, price_type: str = "open") -> Optional[float]:
        """获取指定日期的价格"""
        try:
            df = self.load_stock_data_until(symbol, date)
            if df is None or len(df) == 0:
                return None
            
            date_obj = pd.to_datetime(date)
            if df.index.tz is not None:
                date_obj = date_obj.tz_localize(df.index.tz)
            if date_obj not in df.index:
                df = df[df.index <= date_obj]
                if len(df) == 0:
                    return None
                date_obj = df.index[-1]
            
            if price_type == "open":
                return float(df.loc[date_obj, "Open"])
            elif price_type == "close":
                return float(df.loc[date_obj, "Close"])
            else:
                raise ValueError(f"不支持的价格类型: {price_type}")
        except Exception as e:
            print(f"[DataAdapter] 获取 {symbol} 在 {date} 的 {price_type} 价格失败: {e}")
            return None
    
    def get_last_n_trading_days(self, end_date: str, n: int, symbol: str = "SPY") -> List[str]:
        """
        获取截止到 end_date 的最近 n 个交易日（含 end_date）。
        用于 history_report 7 日窗口基于真实交易日历。
        """
        try:
            from datetime import datetime, timedelta
            start = (datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=max(n * 2, 60))).strftime("%Y-%m-%d")
            df = self.load_stock_data_until(symbol, end_date, start_date=start)
            if df is None or len(df) == 0:
                return []
            dates = sorted(set(d.strftime("%Y-%m-%d") for d in df.index if d.strftime("%Y-%m-%d") <= end_date))
            return dates[-n:] if len(dates) >= n else dates
        except Exception:
            return []

    def get_next_trading_day(self, current_date: str, symbol: str = "SPY") -> Optional[str]:
        """获取下一个交易日"""
        try:
            df = self.load_stock_data_until(symbol, "2099-12-31", start_date=current_date)
            if df is None or len(df) == 0:
                return None
            
            current_date_obj = pd.to_datetime(current_date)
            if df.index.tz is not None:
                current_date_obj = current_date_obj.tz_localize(df.index.tz)
            future_dates = df[df.index > current_date_obj].index
            if len(future_dates) == 0:
                return None
            
            next_date = future_dates[0]
            return next_date.strftime("%Y-%m-%d")
        except Exception as e:
            print(f"[DataAdapter] 获取下一个交易日失败: {e}")
            return None

