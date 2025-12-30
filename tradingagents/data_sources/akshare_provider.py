"""AkShare"""
import re
from typing import Optional, List, Dict
import pandas as pd
import akshare as ak
from datetime import datetime


class AkshareProvider:
    """AkShare 数据提供者封装 - 主要获取新闻和宏观数据，具体tick数据延迟较大"""
    
    def __init__(self):
        """初始化 AkShare Provider（无需 token）"""
        pass
    
    # ==================== Public ==================
    
    def get_stock_news(
        self,
        symbol: str,
        limit: int = 10
    ) -> str:
        """
        获取股票相关新闻（来源：东方财富）
        
        返回 Markdown 格式的个股新闻简报，便于 LLM 理解和处理。
        
        Args:
            symbol: 股票代码，支持以下格式：
                - '000001' (6位数字)
                - '000001.SZ' (带后缀)
                - '600000.SH' (带后缀)
            limit: 返回的新闻数量限制（默认 10 条）
        
        Returns:
            Markdown 格式的字符串，包含个股新闻简报
        """
        try:
            # 清洗股票代码
            clean_symbol = re.sub(r"\D", "", symbol)
            
            if not clean_symbol or len(clean_symbol) != 6:
                return self._format_stock_news_error(symbol, f"无效的股票代码: {symbol}")
            
            # 获取新闻数据
            df = self._fetch_stock_news_data(clean_symbol, limit)
            
            if df is None or df.empty:
                return self._format_stock_news_empty(clean_symbol)
            
            # 格式化为 Markdown
            return self._format_stock_news_markdown(clean_symbol, df, limit)
            
        except Exception as e:
            error_msg = str(e)
            if "Expecting value" in error_msg or "JSON" in error_msg or "JSONDecodeError" in error_msg:
                return self._format_stock_news_error(
                    symbol, 
                    "AkShare 接口返回格式异常（可能是接口变更、网络问题或数据源暂时不可用）。请稍后重试或使用 Tushare 作为备选数据源。"
                )
            else:
                return self._format_stock_news_error(symbol, f"获取股票新闻失败: {error_msg}")
    
    def get_global_news(self) -> str:
        """
        获取宏观市场全景简报
        
        聚合四个维度的宏观数据：
        1. 宏观新闻（10条）
        2. 北向资金流向
        3. 核心指数表现
        4. 实时汇率信息
        
        返回 Markdown 格式的宏观市场全景简报，便于 LLM 理解和处理。
        
        Returns:
            Markdown 格式的字符串，包含宏观市场全景简报
        """
        update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sections = []
        errors = []
        
        # 1. 获取宏观新闻
        try:
            news_df = self._get_macro_news(limit=10)
            if news_df is not None and not news_df.empty:
                sections.append(self._format_macro_news_section(news_df))
            else:
                errors.append("宏观新闻")
        except Exception as e:
            errors.append(f"宏观新闻（错误: {str(e)[:50]}）")
        
        # 2. 获取北向资金
        try:
            money_flow = self._get_smart_money_flow()
            if money_flow and "error" not in money_flow:
                sections.append(self._format_money_flow_section(money_flow))
            else:
                errors.append("北向资金")
        except Exception as e:
            errors.append(f"北向资金（错误: {str(e)[:50]}）")
        
        # 3. 获取核心指数
        try:
            indices = self._get_global_indices_summary()
            if indices:
                sections.append(self._format_indices_section(indices))
            else:
                errors.append("核心指数")
        except Exception as e:
            errors.append(f"核心指数（错误: {str(e)[:50]}）")
        
        # 4. 获取汇率
        try:
            currency = self._get_currency_rate()
            if currency and currency.get("price") is not None:
                sections.append(self._format_currency_section(currency))
            else:
                errors.append("汇率信息")
        except Exception as e:
            errors.append(f"汇率信息（错误: {str(e)[:50]}）")
        
        # 组装完整的 Markdown
        markdown = f"# 宏观市场全景简报\n\n"
        markdown += f"**更新时间**: {update_time}\n\n"
        markdown += "---\n\n"
        
        # 添加各个部分
        for section in sections:
            markdown += section + "\n\n---\n\n"
        
        if errors:
            markdown += f"## ⚠️ 数据获取提示\n\n"
            markdown += f"以下数据获取失败，可能影响分析完整性：\n"
            for error in errors:
                markdown += f"- {error}\n"
            markdown += f"\n建议：检查网络连接或稍后重试。\n\n"
        
        markdown += f"*数据来源: AkShare (东方财富)*\n"
        
        return markdown
    
    # ==================== Internal Methods ================
    
    def _fetch_stock_news_data(self, clean_symbol: str, limit: int) -> pd.DataFrame:
        """获取股票新闻原始数据"""
        df = ak.stock_news_em(symbol=clean_symbol)
        if df is not None and not df.empty and limit > 0:
            df = df.head(limit)
        return df
    
    def _get_macro_news(self, limit: int = 10) -> pd.DataFrame:
        """
        获取宏观经济新闻（内部方法）
        
        策略：
        1. 优先使用央视财经新闻
        2. 如果失败，尝试使用上证指数（000001）的新闻
        3. 最后尝试百度财经新闻
        """
        try:
            # 策略1: 使用央视财经新闻
            try:
                df = ak.news_cctv()
                if df is not None and not df.empty:
                    if limit > 0:
                        df = df.head(limit)
                    return df
            except Exception:
                pass
            
            # 策略2: 使用上证指数新闻（000001）
            try:
                df = ak.stock_news_em(symbol="000001")
                if df is not None and not df.empty:
                    if limit > 0:
                        df = df.head(limit)
                    return df
            except Exception:
                pass
            
            # 策略3: Fallback 到百度财经新闻
            try:
                df_baidu = ak.news_economic_baidu()
                if df_baidu is not None and not df_baidu.empty:
                    if limit > 0:
                        df_baidu = df_baidu.head(limit)
                    return df_baidu
            except Exception:
                pass
            
            return pd.DataFrame()
            
        except Exception:
            return pd.DataFrame()
    
    def _get_smart_money_flow(self) -> Dict:
        """获取北向资金实时净流入情况"""
        try:
            # 策略1: 尝试使用资金流向汇总接口
            try:
                df = ak.stock_hsgt_fund_flow_summary_em()
                
                if df is not None and not df.empty:
                    item = df.iloc[0]
                    money = 0.0
                    date_str = datetime.now().strftime("%Y-%m-%d")
                    
                    # 尝试不同的列名
                    for col in ['value', 'net_flow', '净流入', '当日净流入', '累计净流入']:
                        if col in item:
                            money = float(item[col])
                            break
                    
                    # 如果没找到，尝试计算（买入-卖出）
                    if money == 0.0:
                        buy_col = None
                        sell_col = None
                        for col in df.columns:
                            if '买入' in str(col) or 'buy' in str(col).lower():
                                buy_col = col
                            if '卖出' in str(col) or 'sell' in str(col).lower():
                                sell_col = col
                        if buy_col and sell_col:
                            money = float(item[buy_col]) - float(item[sell_col])
                    
                    # 查找日期字段
                    for col in ['date', '日期', '交易日期']:
                        if col in item:
                            date_str = str(item[col])
                            break
                    
                    # 转换为亿元
                    amount_yi = money / 10000
                    flow_status = "净流入" if amount_yi > 0 else "净流出"
                    
                    return {
                        "title": "北向资金(Smart Money)",
                        "value": f"{flow_status} {abs(amount_yi):.2f} 亿元",
                        "date": date_str,
                        "source": "EastMoney HSGT",
                        "amount_yi": amount_yi,
                        "flow_status": flow_status
                    }
            except Exception:
                pass
            
            # 策略2: 尝试使用历史数据接口获取最新数据
            try:
                df = ak.stock_hsgt_hist_em(symbol="北向资金", start_date=datetime.now().strftime("%Y%m%d"))
                
                if df is not None and not df.empty:
                    item = df.iloc[-1]
                    money = 0.0
                    for col in ['value', 'net_flow', '净流入', '当日净流入']:
                        if col in item:
                            money = float(item[col])
                            break
                    
                    if money != 0.0:
                        amount_yi = money / 10000
                        flow_status = "净流入" if amount_yi > 0 else "净流出"
                        
                        return {
                            "title": "北向资金(Smart Money)",
                            "value": f"{flow_status} {abs(amount_yi):.2f} 亿元",
                            "date": str(item.get('date', datetime.now().strftime("%Y-%m-%d"))),
                            "source": "EastMoney HSGT",
                            "amount_yi": amount_yi,
                            "flow_status": flow_status
                        }
            except Exception:
                pass
            
            return {
                "error": "无法获取北向资金数据（接口可能已变更）",
                "title": "北向资金(Smart Money)",
                "value": "数据不可用",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "source": "EastMoney HSGT"
            }
            
        except Exception as e:
            return {
                "error": f"北向资金获取失败: {str(e)}",
                "title": "北向资金(Smart Money)",
                "value": "数据获取失败",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "source": "EastMoney HSGT"
            }
    
    def _get_global_indices_summary(self) -> List[Dict]:
        """获取关键外围指数涨跌幅）"""
        summary = []
        
        try:
            df = ak.index_global_spot_em()
            
            if df is not None and not df.empty:
                target_codes = ['DJIA', 'SPX', 'NDX', 'HSI', 'N225', 'GDAXI', 'FTSE', 'FCHI', 'A50', 'STI']
                target_keywords = ['道琼斯', '纳斯达克', '标普', '恒生', '日经', 'DAX', '富时', 'CAC', 'A50']
                
                for _, row in df.iterrows():
                    code = str(row.get('代码', ''))
                    name = str(row.get('名称', ''))
                    
                    is_target = False
                    if code in target_codes:
                        is_target = True
                    elif any(keyword in name for keyword in target_keywords):
                        is_target = True
                    
                    if not is_target:
                        continue
                    
                    price = 0.0
                    price_col = row.get('最新价', None)
                    if pd.notna(price_col):
                        try:
                            price = float(price_col)
                        except (ValueError, TypeError):
                            pass
                    
                    change_pct = 0.0
                    change_pct_str = None
                    change_col = row.get('涨跌幅', None)
                    if pd.notna(change_col):
                        try:
                            if isinstance(change_col, str):
                                change_pct_str = change_col
                                change_pct = float(change_col.replace('%', '').replace('+', '').strip())
                            else:
                                change_pct = float(change_col)
                                change_pct_str = f"{change_pct:+.2f}%"
                        except (ValueError, AttributeError):
                            pass
                    
                    if price > 0:
                        summary.append({
                            "asset": name,
                            "code": code,
                            "price": price,
                            "change": change_pct_str if change_pct_str else f"{change_pct:+.2f}%",
                            "change_pct": change_pct
                        })
                
                priority_order = {'DJIA': 1, 'SPX': 2, 'NDX': 3, 'HSI': 4, 'N225': 5, 'GDAXI': 6, 'FTSE': 7, 'FCHI': 8}
                summary.sort(key=lambda x: priority_order.get(x.get('code', ''), 99))
                summary = summary[:10]
                
        except Exception:
            pass
        
        return summary
    
    def _get_currency_rate(self) -> Dict:
        """获取美元/人民币汇率"""
        try:
            try:
                df = ak.currency_boc_safe()
                
                if df is not None and not df.empty:
                    latest = df.iloc[-1]
                    date_str = str(latest.iloc[0])
                    usd_100 = latest.get('美元', None)
                    
                    if pd.notna(usd_100) and usd_100 > 0:
                        price = float(usd_100) / 100.0
                        
                        change_pct = 0.0
                        if len(df) > 1:
                            prev_usd_100 = df.iloc[-2].get('美元', None)
                            if pd.notna(prev_usd_100) and prev_usd_100 > 0:
                                prev_price = float(prev_usd_100) / 100.0
                                change_pct = ((price - prev_price) / prev_price) * 100
                        
                        description = f"USD/CNY: {price:.4f} ({change_pct:+.2f}%)"
                        
                        return {
                            "currency_pair": "USD/CNY",
                            "price": price,
                            "change": f"{change_pct:+.2f}%",
                            "change_pct": change_pct,
                            "description": description,
                            "date": date_str
                        }
            except Exception:
                pass
            
            return {
                "currency_pair": "USD/CNY",
                "price": None,
                "change": "N/A",
                "change_pct": 0.0,
                "description": "USD/CNY: 数据获取失败（接口可能已变更）",
                "date": None
            }
            
        except Exception as e:
            return {
                "currency_pair": "USD/CNY",
                "price": None,
                "change": "N/A",
                "change_pct": 0.0,
                "description": f"汇率获取失败: {str(e)}",
                "date": None
            }
    
    # ==================== Markdown 格式化方法 ====================
    
    def _format_stock_news_markdown(self, symbol: str, df: pd.DataFrame, limit: int) -> str:
        """格式化个股新闻为 Markdown"""
        update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        markdown = f"# 个股新闻简报 - {symbol}\n\n"
        markdown += f"**更新时间**: {update_time}\n\n"
        markdown += f"## 数据概览\n\n"
        markdown += f"- **股票代码**: {symbol}\n"
        markdown += f"- **新闻数量**: {len(df)} 条\n"
        markdown += f"- **数据来源**: AkShare (东方财富)\n\n"
        markdown += f"## 新闻列表\n\n"
        
        # 处理列名容错
        time_col = None
        title_col = None
        url_col = None
        content_col = None
        source_col = None
        
        for col in df.columns:
            if '时间' in str(col) or 'time' in str(col).lower():
                time_col = col
            if '标题' in str(col) or 'title' in str(col).lower():
                title_col = col
            if '链接' in str(col) or 'url' in str(col).lower():
                url_col = col
            if '内容' in str(col) or 'content' in str(col).lower():
                content_col = col
            if '来源' in str(col) or 'source' in str(col).lower():
                source_col = col
        
        # 遍历新闻
        for idx, (_, row) in enumerate(df.iterrows(), 1):
            markdown += f"### {idx}. "
            
            # 标题
            if title_col and title_col in row:
                title = str(row[title_col]).strip()
                if url_col and url_col in row:
                    url = str(row[url_col]).strip()
                    if url:
                        markdown += f"[{title}]({url})\n\n"
                    else:
                        markdown += f"{title}\n\n"
                else:
                    markdown += f"{title}\n\n"
            else:
                markdown += f"（无标题）\n\n"
            
            # 详细信息
            markdown += f"- **发布时间**: "
            if time_col and time_col in row:
                markdown += f"{str(row[time_col])}\n"
            else:
                markdown += f"未知\n"
            
            if source_col and source_col in row:
                markdown += f"- **来源**: {str(row[source_col])}\n"
            
            if url_col and url_col in row and url_col != title_col:
                url = str(row[url_col]).strip()
                if url:
                    markdown += f"- **链接**: {url}\n"
            
            # 内容摘要（如果有且不太长）
            if content_col and content_col in row:
                content = str(row[content_col]).strip()
                if content and len(content) > 0:
                    # 限制摘要长度
                    summary = content[:200] + "..." if len(content) > 200 else content
                    markdown += f"- **摘要**: {summary}\n"
            
            markdown += "\n"
        
        markdown += f"*数据来源: AkShare (东方财富)*\n"
        
        return markdown
    
    def _format_stock_news_empty(self, symbol: str) -> str:
        """格式化空新闻结果"""
        update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        markdown = f"# 个股新闻简报 - {symbol}\n\n"
        markdown += f"**更新时间**: {update_time}\n\n"
        markdown += f"## ⚠️ 数据获取提示\n\n"
        markdown += f"未找到股票 {symbol} 的相关新闻数据。\n\n"
        markdown += f"可能原因：\n"
        markdown += f"- 该股票近期没有新闻\n"
        markdown += f"- 数据源暂时不可用\n"
        markdown += f"- 网络连接问题\n\n"
        markdown += f"建议：稍后重试或手动关注相关新闻。\n"
        return markdown
    
    def _format_stock_news_error(self, symbol: str, error_msg: str) -> str:
        """格式化错误信息"""
        update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        markdown = f"# 个股新闻简报 - {symbol}\n\n"
        markdown += f"**更新时间**: {update_time}\n\n"
        markdown += f"## ❌ 数据获取失败\n\n"
        markdown += f"**错误信息**: {error_msg}\n\n"
        markdown += f"建议：\n"
        markdown += f"- 检查网络连接\n"
        markdown += f"- 稍后重试\n"
        markdown += f"- 使用 Tushare 作为备选数据源\n"
        return markdown
    
    def _format_macro_news_section(self, df: pd.DataFrame) -> str:
        """格式化宏观新闻部分"""
        markdown = f"## 📰 宏观新闻 ({len(df)}条)\n\n"
        
        # 处理列名
        time_col = None
        title_col = None
        url_col = None
        content_col = None
        
        for col in df.columns:
            if '时间' in str(col) or 'time' in str(col).lower() or '日期' in str(col):
                time_col = col
            if '标题' in str(col) or 'title' in str(col).lower():
                title_col = col
            if '链接' in str(col) or 'url' in str(col).lower():
                url_col = col
            if '内容' in str(col) or 'content' in str(col).lower():
                content_col = col
        
        for idx, (_, row) in enumerate(df.iterrows(), 1):
            markdown += f"### {idx}. "
            
            if title_col and title_col in row:
                title = str(row[title_col]).strip()
                if url_col and url_col in row:
                    url = str(row[url_col]).strip()
                    if url:
                        markdown += f"[{title}]({url})\n\n"
                    else:
                        markdown += f"{title}\n\n"
                else:
                    markdown += f"{title}\n\n"
            else:
                markdown += f"（无标题）\n\n"
            
            if time_col and time_col in row:
                markdown += f"- **时间**: {str(row[time_col])}\n"
            
            if content_col and content_col in row:
                content = str(row[content_col]).strip()
                if content:
                    summary = content[:150] + "..." if len(content) > 150 else content
                    markdown += f"- **摘要**: {summary}\n"
            
            markdown += "\n"
        
        return markdown
    
    def _format_money_flow_section(self, money_flow: Dict) -> str:
        """格式化北向资金部分"""
        markdown = f"## 💰 北向资金流向\n\n"
        markdown += f"- **状态**: {money_flow.get('flow_status', '未知')}\n"
        markdown += f"- **金额**: {money_flow.get('value', 'N/A')}\n"
        markdown += f"- **日期**: {money_flow.get('date', 'N/A')}\n"
        markdown += f"- **数据来源**: {money_flow.get('source', 'N/A')}\n"
        return markdown
    
    def _format_indices_section(self, indices: List[Dict]) -> str:
        """格式化核心指数部分"""
        markdown = f"## 📊 核心指数表现\n\n"
        markdown += f"| 指数 | 代码 | 最新价 | 涨跌幅 |\n"
        markdown += f"|------|------|--------|--------|\n"
        
        for idx in indices:
            asset = idx.get('asset', 'N/A')
            code = idx.get('code', 'N/A')
            price = idx.get('price', 0)
            change = idx.get('change', 'N/A')
            
            # 格式化价格（大数字用千分位）
            if price >= 1000:
                price_str = f"{price:,.2f}"
            else:
                price_str = f"{price:.2f}"
            
            markdown += f"| {asset} | {code} | {price_str} | {change} |\n"
        
        return markdown
    
    def _format_currency_section(self, currency: Dict) -> str:
        """格式化汇率部分"""
        markdown = f"## 💱 汇率信息\n\n"
        markdown += f"- **货币对**: {currency.get('currency_pair', 'N/A')}\n"
        
        price = currency.get('price')
        if price is not None:
            markdown += f"- **汇率**: {price:.4f}\n"
        else:
            markdown += f"- **汇率**: N/A\n"
        
        markdown += f"- **涨跌幅**: {currency.get('change', 'N/A')}\n"
        markdown += f"- **日期**: {currency.get('date', 'N/A')}\n"
        
        return markdown
    
    # ==================== 基本面分析相关方法 ====================
    
    def get_company_info(self, symbol: str) -> dict:
        """
        获取公司基本信息
        
        Args:
            symbol: 股票代码（支持多种格式）
        
        Returns:
            包含公司基本信息的字典
        """
        clean_symbol = re.sub(r"\D", "", symbol)
        
        if not clean_symbol or len(clean_symbol) != 6:
            return {"error": f"无效的股票代码: {symbol}"}
        
        try:
            # 优先使用 stock_profile_cninfo
            try:
                df = ak.stock_profile_cninfo(symbol=clean_symbol)
                if df is not None and not df.empty:
                    return self._format_company_info(df, clean_symbol)
            except Exception:
                pass
            
            # Fallback: stock_individual_info_em
            try:
                df = ak.stock_individual_info_em(symbol=clean_symbol)
                if df is not None and not df.empty:
                    return self._format_company_info_em(df, clean_symbol)
            except Exception:
                pass
            
            return {"error": "无法获取公司基本信息"}
            
        except Exception as e:
            return {"error": f"获取公司信息失败: {str(e)}"}
    
    def get_financial_statements(
        self,
        symbol: str,
        report_type: str = "annual",
        periods: int = 4
    ) -> dict:
        """
        获取三大财务报表
        
        Args:
            symbol: 股票代码
            report_type: 'annual' 或 'quarter'
            periods: 获取最近 N 期数据（默认 4 期）
        
        Returns:
            包含利润表、资产负债表、现金流量表的字典
        """
        clean_symbol = re.sub(r"\D", "", symbol)
        
        if not clean_symbol or len(clean_symbol) != 6:
            return {"error": f"无效的股票代码: {symbol}"}
        
        result = {
            "symbol": clean_symbol,
            "report_type": report_type,
            "income": None,
            "balance": None,
            "cashflow": None,
            "errors": []
        }
        
        # 获取利润表
        try:
            income_df = self._get_profit_sheet(clean_symbol, report_type, periods)
            if income_df is not None and not income_df.empty:
                result["income"] = income_df.to_dict('records')
            else:
                result["errors"].append("利润表数据为空")
        except Exception as e:
            result["errors"].append(f"利润表获取失败: {str(e)}")
        
        # 获取资产负债表
        try:
            balance_df = self._get_balance_sheet(clean_symbol, report_type, periods)
            if balance_df is not None and not balance_df.empty:
                result["balance"] = balance_df.to_dict('records')
            else:
                result["errors"].append("资产负债表数据为空")
        except Exception as e:
            result["errors"].append(f"资产负债表获取失败: {str(e)}")
        
        # 获取现金流量表
        try:
            cashflow_df = self._get_cashflow_sheet(clean_symbol, report_type, periods)
            if cashflow_df is not None and not cashflow_df.empty:
                result["cashflow"] = cashflow_df.to_dict('records')
            else:
                result["errors"].append("现金流量表数据为空")
        except Exception as e:
            result["errors"].append(f"现金流量表获取失败: {str(e)}")
        
        # 如果三大报表均为空，则视为失败
        if result["income"] is None and result["balance"] is None and result["cashflow"] is None:
            result["errors"].append("AkShare 三大报表全部为空，可能接口失效或需要替代方案")
        return result
    
    def get_financial_indicators(
        self,
        symbol: str,
        report_type: str = "annual",
        periods: int = 4
    ) -> dict:
        """
        获取财务指标（ROE、ROA、毛利率、净利率等）
        
        Args:
            symbol: 股票代码
            report_type: 'annual' 或 'quarter'
            periods: 最近 N 期（默认 4 期）
        
        Returns:
            包含财务指标的字典
        """
        clean_symbol = re.sub(r"\D", "", symbol)
        
        if not clean_symbol or len(clean_symbol) != 6:
            return {"error": f"无效的股票代码: {symbol}"}
        
        try:
            df = ak.stock_financial_analysis_indicator_em(symbol=clean_symbol)
            
            if df is None:
                return {"error": "财务指标接口返回 None"}
            
            if df.empty:
                return {"error": "财务指标数据为空"}
            
            # 确保 df 有 columns 属性
            if not hasattr(df, 'columns'):
                return {"error": "返回数据格式不正确，缺少 columns 属性"}
            
            # 检查是否有 '报告期' 列
            date_col = None
            if '报告期' in df.columns:
                date_col = '报告期'
            else:
                # 尝试其他可能的列名
                for col in df.columns:
                    if '期' in str(col) or 'date' in str(col).lower() or 'period' in str(col).lower():
                        date_col = col
                        break
            
            # 根据 report_type 过滤数据（如果有日期列）
            if date_col:
                try:
                    if report_type == "quarter":
                        df = df[df[date_col].astype(str).str.contains('Q', na=False)]
                    else:
                        df = df[~df[date_col].astype(str).str.contains('Q', na=False)]
                except Exception as filter_error:
                    # 如果过滤失败，继续使用全部数据
                    pass
            
            # 取最近 N 期
            if periods > 0 and not df.empty:
                df = df.head(periods)
            
            if df.empty:
                return {"error": f"未找到 {report_type} 类型的财务指标数据"}
            
            return {
                "symbol": clean_symbol,
                "report_type": report_type,
                "data": df.to_dict('records')
            }
            
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            return {"error": f"获取财务指标失败: {str(e)}", "detail": error_detail[:200]}
    
    def get_valuation_indicators(
        self,
        symbol: str,
        include_market_comparison: bool = True
    ) -> dict:
        """
        获取估值指标（PE、PB、PS、股息率等）
        
        Args:
            symbol: 股票代码
            include_market_comparison: 是否包含市场/行业对比（默认 True）
        
        Returns:
            包含估值指标的字典
        """
        clean_symbol = re.sub(r"\D", "", symbol)
        
        if not clean_symbol or len(clean_symbol) != 6:
            return {"error": f"无效的股票代码: {symbol}"}
        
        result = {
            "symbol": clean_symbol,
            "pe_pb": None,
            "dividend": None,
            "market_comparison": None,
            "errors": []
        }
        
        # 获取 PE/PB
        # 注意：stock_a_ttm_lyr 不接受 symbol 参数，返回所有股票数据
        # 我们需要从返回的数据中筛选目标股票
        try:
            pe_pb_df = ak.stock_a_ttm_lyr()
            if pe_pb_df is not None and not pe_pb_df.empty:
                # 筛选目标股票（通过代码列）
                code_col = None
                for col in pe_pb_df.columns:
                    if '代码' in str(col) or 'code' in str(col).lower() or 'symbol' in str(col).lower():
                        code_col = col
                        break
                
                if code_col:
                    filtered_df = pe_pb_df[pe_pb_df[code_col].astype(str).str.contains(clean_symbol, na=False)]
                    if not filtered_df.empty:
                        result["pe_pb"] = filtered_df.to_dict('records')
                    else:
                        result["errors"].append(f"未找到股票 {clean_symbol} 的 PE/PB 数据")
                else:
                    # 如果没有代码列，返回前几条作为示例（不推荐）
                    result["errors"].append("PE/PB 数据中未找到代码列，无法筛选目标股票")
        except Exception as e:
            result["errors"].append(f"PE/PB获取失败: {str(e)}")
        
        # 获取分红数据
        try:
            dividend_df = ak.stock_dividend_cninfo(symbol=clean_symbol)
            if dividend_df is not None and not dividend_df.empty:
                result["dividend"] = dividend_df.to_dict('records')
        except Exception as e:
            result["errors"].append(f"分红数据获取失败: {str(e)}")
        
        # 获取市场/行业对比
        if include_market_comparison:
            try:
                market_pe = ak.stock_market_pe_lg()
                market_pb = ak.stock_market_pb_lg()
                result["market_comparison"] = {
                    "market_pe": market_pe.to_dict('records') if market_pe is not None and not market_pe.empty else None,
                    "market_pb": market_pb.to_dict('records') if market_pb is not None and not market_pb.empty else None
                }
            except Exception as e:
                result["errors"].append(f"市场对比数据获取失败: {str(e)}")
        
        return result
    
    def get_earnings_data(self, symbol: str, limit: int = 10) -> dict:
        """
        获取业绩预告、快报数据
        
        Args:
            symbol: 股票代码
            limit: 返回最近 N 条记录（默认 10 条）
        
        Returns:
            包含业绩预告和快报的字典
        """
        clean_symbol = re.sub(r"\D", "", symbol)
        
        if not clean_symbol or len(clean_symbol) != 6:
            return {"error": f"无效的股票代码: {symbol}"}
        
        result = {
            "symbol": clean_symbol,
            "forecast": None,
            "express": None,
            "errors": []
        }
        
        # 获取业绩预告
        # 注意：这些接口可能不接受 symbol 参数，需要先获取所有数据再筛选
        try:
            # 尝试使用 stock_profit_forecast_em（可能需要不同的参数）
            try:
                forecast_df = ak.stock_profit_forecast_em()
                if forecast_df is not None and not forecast_df.empty:
                    # 筛选目标股票
                    code_col = None
                    for col in forecast_df.columns:
                        if '代码' in str(col) or 'code' in str(col).lower() or 'symbol' in str(col).lower():
                            code_col = col
                            break
                    
                    if code_col:
                        filtered_df = forecast_df[forecast_df[code_col].astype(str).str.contains(clean_symbol, na=False)]
                        if not filtered_df.empty:
                            if limit > 0:
                                filtered_df = filtered_df.head(limit)
                            result["forecast"] = filtered_df.to_dict('records')
            except Exception:
                # 尝试其他接口
                try:
                    forecast_df = ak.stock_yjyg_em()
                    if forecast_df is not None and not forecast_df.empty:
                        code_col = None
                        for col in forecast_df.columns:
                            if '代码' in str(col) or 'code' in str(col).lower():
                                code_col = col
                                break
                        
                        if code_col:
                            filtered_df = forecast_df[forecast_df[code_col].astype(str).str.contains(clean_symbol, na=False)]
                            if not filtered_df.empty:
                                if limit > 0:
                                    filtered_df = filtered_df.head(limit)
                                result["forecast"] = filtered_df.to_dict('records')
                except Exception as e:
                    result["errors"].append(f"业绩预告获取失败: {str(e)}")
        except Exception as e:
            result["errors"].append(f"业绩预告获取失败: {str(e)}")
        
        # 获取业绩快报
        try:
            express_df = ak.stock_yjkb_em()
            if express_df is not None and not express_df.empty:
                # 筛选目标股票
                code_col = None
                for col in express_df.columns:
                    if '代码' in str(col) or 'code' in str(col).lower() or 'symbol' in str(col).lower():
                        code_col = col
                        break
                
                if code_col:
                    filtered_df = express_df[express_df[code_col].astype(str).str.contains(clean_symbol, na=False)]
                    if not filtered_df.empty:
                        if limit > 0:
                            filtered_df = filtered_df.head(limit)
                        result["express"] = filtered_df.to_dict('records')
                    else:
                        result["errors"].append(f"未找到股票 {clean_symbol} 的业绩快报数据")
                else:
                    result["errors"].append("业绩快报数据中未找到代码列，无法筛选目标股票")
        except Exception as e:
            result["errors"].append(f"业绩快报获取失败: {str(e)}")
        
        return result
    
    # ==================== fundamentals ====================
    
    def _get_profit_sheet(
        self,
        symbol: str,
        report_type: str,
        periods: int
    ) -> pd.DataFrame:
        """获取利润表"""
        try:
            if report_type == "quarter":
                df = ak.stock_profit_sheet_by_quarterly_em(symbol=symbol)
            else:
                df = ak.stock_profit_sheet_by_yearly_em(symbol=symbol)
            
            if df is not None and not df.empty and periods > 0:
                df = df.head(periods)
            
            return df
        except Exception:
            return pd.DataFrame()
    
    def _get_balance_sheet(
        self,
        symbol: str,
        report_type: str,
        periods: int
    ) -> pd.DataFrame:
        """获取资产负债表"""
        try:
            if report_type == "quarter":
                # 季度数据可能需要使用 report 接口
                df = ak.stock_balance_sheet_by_report_em(symbol=symbol)
            else:
                df = ak.stock_balance_sheet_by_yearly_em(symbol=symbol)
            
            if df is not None and not df.empty and periods > 0:
                df = df.head(periods)
            
            return df
        except Exception:
            return pd.DataFrame()
    
    def _get_cashflow_sheet(
        self,
        symbol: str,
        report_type: str,
        periods: int
    ) -> pd.DataFrame:
        """获取现金流量表"""
        try:
            if report_type == "quarter":
                df = ak.stock_cash_flow_sheet_by_quarterly_em(symbol=symbol)
            else:
                df = ak.stock_cash_flow_sheet_by_yearly_em(symbol=symbol)
            
            if df is not None and not df.empty and periods > 0:
                df = df.head(periods)
            
            return df
        except Exception:
            return pd.DataFrame()
    
    def _format_company_info(self, df: pd.DataFrame, symbol: str) -> dict:
        """格式化公司信息（来自 stock_profile_cninfo）"""
        try:
            row = df.iloc[0]
            return {
                "symbol": symbol,
                "name": str(row.get('公司名称', 'N/A')),
                "industry": str(row.get('所属行业', 'N/A')),
                "list_date": str(row.get('上市日期', 'N/A')),
                "data": row.to_dict()
            }
        except Exception:
            return {"symbol": symbol, "error": "数据格式化失败"}
    
    def _format_company_info_em(self, df: pd.DataFrame, symbol: str) -> dict:
        """格式化公司信息（来自 stock_individual_info_em）"""
        try:
            # 将 DataFrame 转换为字典
            info_dict = {}
            for _, row in df.iterrows():
                key = str(row.iloc[0]) if len(row) > 0 else ""
                value = str(row.iloc[1]) if len(row) > 1 else ""
                if key:
                    info_dict[key] = value
            
            return {
                "symbol": symbol,
                "data": info_dict
            }
        except Exception:
            return {"symbol": symbol, "error": "数据格式化失败"}
