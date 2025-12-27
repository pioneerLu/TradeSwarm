"""AkShare"""
import re
from typing import Any, Optional, List, Dict
import pandas as pd
import akshare as ak
from datetime import datetime


class AkshareProvider:
    """AkShare 数据提供者封装 - 主要获取新闻和宏观数据，具体tick数据延迟较大"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        初始化 AkShare Provider
        
        Args:
            config: 配置字典，可选。用于从配置中读取 data_sources 段的参数。
                   AkShare 本身无需 token，但为保持与其他 Provider 一致的初始化模式，
                   统一接收 config 参数。
        
        关键实现细节:
            - 第一阶段：保存配置引用（如有）
            - 第二阶段：从配置中提取 data_sources 段的超参数（如有）
        """
        # 第一阶段：保存配置引用
        self._config = config or {}
        
        # 第二阶段：提取 data_sources 配置段（预留扩展）
        data_sources_config = self._config.get("data_sources", {})
        
        # AkShare 无需 token，但预留超参数扩展点
        # 例如：未来可从配置读取默认的新闻数量限制、请求超时等
        self._default_news_limit = data_sources_config.get("akshare_default_news_limit", 10)
        self._request_timeout = data_sources_config.get("akshare_request_timeout", 30)
    
    # ==================== Public ==================
    

    
    def get_macro_news(
        self,
        source: str = "all",
        limit: int = 10
    ) -> dict:
        """
        获取宏观经济新闻
        
        支持多个数据源：
        - 'cctv': 央视财经数据源
        - 'baidu': 百度财经数据源
        - 'all': 依次尝试所有数据源（默认）
        
        Args:
            source: 数据源选择
            limit: 返回新闻数量限制
        
        Returns:
            包含宏观新闻的字典：
            - data: pandas.DataFrame，包含新闻数据
            - actual_sources: list，实际成功的数据源列表
            - errors: list，各数据源的错误信息
            - update_time: str，数据更新时间
        """
        # 第一阶段：初始化结果结构
        update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        result = {
            "data": pd.DataFrame(),
            "actual_sources": [],
            "errors": [],
            "update_time": update_time
        }
        
        # 第二阶段：定义数据源尝试顺序
        sources_order = []
        if source == "all":
            sources_order = ["cctv", "baidu"]
        else:
            sources_order = [source]
        
        # 第三阶段：依次尝试各个数据源
        for source_name in sources_order:
            try:
                news_df = self._get_macro_news_from_source(limit, source_name)
                if news_df is not None and not news_df.empty:
                    # 添加数据源标识列
                    news_df = news_df.copy()
                    news_df["data_source"] = source_name
                    
                    if result["data"].empty:
                        result["data"] = news_df
                    else:
                        result["data"] = pd.concat([result["data"], news_df], ignore_index=True)
                    
                    result["actual_sources"].append(source_name)
                    
                    # 如果不是 all 模式且已获取数据，停止尝试其他数据源
                    if source != "all":
                        break
            except Exception as e:
                result["errors"].append(f"{source_name} 数据源宏观新闻获取失败: {str(e)}")
        
        # 第四阶段：处理数据去重和限制数量
        if not result["data"].empty:
            result["data"] = self._deduplicate_news_dataframe(result["data"])
            
            # 限制返回数量
            if len(result["data"]) > limit:
                result["data"] = result["data"].head(limit)
        
        # 如果所有数据源都失败，添加错误信息
        if not result["actual_sources"]:
            result["errors"].append("所有数据源均无法获取宏观新闻")
        
        return result
    
    def get_northbound_money_flow(self) -> dict:
        """
        获取北向资金实时净流入情况
        
        Returns:
            包含北向资金流向信息的字典：
            - data: dict，包含北向资金流向信息
            - errors: list，错误信息
            - update_time: str，数据更新时间
        """
        update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        result = {
            "data": {},
            "errors": [],
            "update_time": update_time
        }
        
        try:
            money_flow = self._get_smart_money_flow()
            if money_flow and "error" not in money_flow:
                result["data"] = money_flow
            else:
                result["errors"].append("北向资金数据获取失败")
                if money_flow and "error" in money_flow:
                    result["errors"].append(money_flow["error"])
        except Exception as e:
            result["errors"].append(f"北向资金获取失败: {str(e)}")
        
        return result
    
    def get_global_indices_performance(self) -> dict:
        """
        获取关键外围指数涨跌幅表现
        
        Returns:
            包含核心指数表现的字典：
            - data: pandas.DataFrame，包含核心指数表现
            - errors: list，错误信息
            - update_time: str，数据更新时间
        """
        update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        result = {
            "data": pd.DataFrame(),
            "errors": [],
            "update_time": update_time
        }
        
        try:
            indices = self._get_global_indices_summary()
            if indices:
                indices_df = pd.DataFrame(indices)
                result["data"] = indices_df
            else:
                result["errors"].append("核心指数数据获取失败")
        except Exception as e:
            result["errors"].append(f"核心指数获取失败: {str(e)}")
        
        return result
    
    def get_currency_exchange_rate(self) -> dict:
        """
        获取美元/人民币汇率信息
        
        Returns:
            包含汇率信息的字典：
            - data: dict，包含汇率信息
            - errors: list，错误信息
            - update_time: str，数据更新时间
        """
        update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        result = {
            "data": {},
            "errors": [],
            "update_time": update_time
        }
        
        try:
            currency = self._get_currency_rate()
            if currency and currency.get("price") is not None:
                result["data"] = currency
            else:
                result["errors"].append("汇率数据获取失败")
        except Exception as e:
            result["errors"].append(f"汇率获取失败: {str(e)}")
        
        return result
    
    # ==================== Internal Methods ================
    
    def _fetch_stock_news_data(self, clean_symbol: str, limit: int) -> pd.DataFrame:
        """获取股票新闻原始数据（保持向后兼容）"""
        # 注意：stock_news_em 目前不可用，返回空DataFrame
        return pd.DataFrame()
    

    
    def _format_news_dataframe(self, df: pd.DataFrame, source: str) -> pd.DataFrame:
        """格式化新闻 DataFrame，统一列名"""
        if df is None or df.empty:
            return pd.DataFrame()
        
        # 复制 DataFrame 避免修改原始数据
        formatted_df = df.copy()
        
        # 获取列名映射
        column_mapping = self._get_news_column_mapping(df.columns)
        
        # 标准化列名
        standardized_columns = {}
        for key, original_col in column_mapping.items():
            if original_col in df.columns:
                standardized_columns[key] = original_col
        
        # 创建标准化 DataFrame
        result_df = pd.DataFrame()
        
        # 基础列
        if "title" in standardized_columns:
            result_df["title"] = df[standardized_columns["title"]]
        else:
            result_df["title"] = "无标题"
        
        if "content" in standardized_columns:
            result_df["content"] = df[standardized_columns["content"]]
        else:
            result_df["content"] = ""
        
        if "time" in standardized_columns:
            result_df["publish_time"] = df[standardized_columns["time"]]
        else:
            result_df["publish_time"] = pd.NaT
        
        if "url" in standardized_columns:
            result_df["url"] = df[standardized_columns["url"]]
        else:
            result_df["url"] = ""
        
        if "source" in standardized_columns:
            result_df["original_source"] = df[standardized_columns["source"]]
        else:
            result_df["original_source"] = source
        
        # 保留其他可能的有用列
        for col in df.columns:
            if col not in standardized_columns.values():
                result_df[f"extra_{col}"] = df[col]
        
        return result_df
    
    def _get_news_column_mapping(self, columns) -> Dict[str, str]:
        """获取新闻数据列名映射"""
        mapping = {}
        
        for col in columns:
            col_str = str(col).lower()
            
            if "标题" in str(col) or "title" in col_str or "公告标题" in str(col):
                mapping["title"] = col
            elif "内容" in str(col) or "content" in col_str or "摘要" in str(col) or "正文" in str(col):
                mapping["content"] = col
            elif "时间" in str(col) or "time" in col_str or "日期" in str(col) or "发布时间" in str(col) or "公告日期" in str(col):
                mapping["time"] = col
            elif "链接" in str(col) or "url" in col_str or "网址" in str(col):
                mapping["url"] = col
            elif "来源" in str(col) or "source" in col_str:
                mapping["source"] = col
            elif "名称" in str(col) or "name" in col_str:
                mapping["name"] = col
            elif "类型" in str(col) or "公告类型" in str(col):
                mapping["type"] = col
        
        return mapping
    
    def _deduplicate_news_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """新闻 DataFrame 去重（基于标题）"""
        if df is None or df.empty:
            return pd.DataFrame()
        
        # 按标题去重
        deduplicated_df = df.drop_duplicates(subset=["title"], keep="first", ignore_index=True)
        
        return deduplicated_df
    
    def _get_macro_news_from_source(self, limit: int, source: str) -> pd.DataFrame:
        """从指定数据源获取宏观新闻"""
        try:
            if source == "cctv":
                # 央视财经数据源 - 宏观新闻
                df = ak.news_cctv()
                
            elif source == "baidu":
                # 百度财经数据源 - 宏观新闻
                df = ak.news_economic_baidu()
                
            else:
                return pd.DataFrame()
            
            if df is not None and not df.empty:
                # 统一列名格式
                df = self._format_news_dataframe(df, source)
                
                # 限制数量
                if limit > 0 and len(df) > limit:
                    df = df.head(limit)
                
                return df
            
            return pd.DataFrame()
            
        except Exception:
            return pd.DataFrame()
    
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
    
    def get_profit_statement(
        self,
        symbol: str,
        report_type: str = "annual",
        periods: int = 4,
        source: str = "all"
    ) -> dict:
        """
        获取利润表（独立函数）
        
        Args:
            symbol: 股票代码
            report_type: 'annual' 或 'quarter'
            periods: 获取最近 N 期数据（默认 4 期）
            source: 数据源选择，可选值：
                   - 'all': 依次尝试所有数据源（默认）
                   - 'ths': 同花顺数据源
                   - 'em': 东方财富数据源  
                   - 'sina': 新浪数据源
        
        Returns:
            包含利润表数据的字典
        """
        clean_symbol = re.sub(r"\D", "", symbol)
        
        if not clean_symbol or len(clean_symbol) != 6:
            return {"error": f"无效的股票代码: {symbol}"}
        
        result = {
            "symbol": clean_symbol,
            "report_type": report_type,
            "periods": periods,
            "source": source,
            "data": None,
            "actual_source": None,
            "errors": []
        }
        
        # 定义数据源尝试顺序
        sources_order = []
        if source == "all":
            sources_order = ["ths", "em", "sina"]
        else:
            sources_order = [source]
        
        # 依次尝试各个数据源
        for source_name in sources_order:
            try:
                df = self._get_profit_sheet_from_source(clean_symbol, report_type, periods, source_name)
                if df is not None and not df.empty:
                    result["data"] = df.to_dict('records')
                    result["actual_source"] = source_name
                    break
                else:
                    result["errors"].append(f"{source_name} 数据源利润表为空")
            except Exception as e:
                result["errors"].append(f"{source_name} 数据源利润表获取失败: {str(e)}")
        
        if result["data"] is None:
            result["errors"].append("所有数据源均无法获取利润表数据")
        
        return result
    
    def get_balance_sheet(
        self,
        symbol: str,
        report_type: str = "annual",
        periods: int = 4,
        source: str = "all"
    ) -> dict:
        """
        获取资产负债表（独立函数）
        
        Args:
            symbol: 股票代码
            report_type: 'annual' 或 'quarter'
            periods: 获取最近 N 期数据（默认 4 期）
            source: 数据源选择，可选值：
                   - 'all': 依次尝试所有数据源（默认）
                   - 'ths': 同花顺数据源
                   - 'em': 东方财富数据源  
                   - 'sina': 新浪数据源
        
        Returns:
            包含资产负债表数据的字典
        """
        clean_symbol = re.sub(r"\D", "", symbol)
        
        if not clean_symbol or len(clean_symbol) != 6:
            return {"error": f"无效的股票代码: {symbol}"}
        
        result = {
            "symbol": clean_symbol,
            "report_type": report_type,
            "periods": periods,
            "source": source,
            "data": None,
            "actual_source": None,
            "errors": []
        }
        
        # 定义数据源尝试顺序
        sources_order = []
        if source == "all":
            sources_order = ["ths", "em", "sina"]
        else:
            sources_order = [source]
        
        # 依次尝试各个数据源
        for source_name in sources_order:
            try:
                df = self._get_balance_sheet_from_source(clean_symbol, report_type, periods, source_name)
                if df is not None and not df.empty:
                    result["data"] = df.to_dict('records')
                    result["actual_source"] = source_name
                    break
                else:
                    result["errors"].append(f"{source_name} 数据源资产负债表为空")
            except Exception as e:
                result["errors"].append(f"{source_name} 数据源资产负债表获取失败: {str(e)}")
        
        if result["data"] is None:
            result["errors"].append("所有数据源均无法获取资产负债表数据")
        
        return result
    
    def get_cash_flow_statement(
        self,
        symbol: str,
        report_type: str = "annual",
        periods: int = 4,
        source: str = "all"
    ) -> dict:
        """
        获取现金流量表（独立函数）
        
        Args:
            symbol: 股票代码
            report_type: 'annual' 或 'quarter'
            periods: 获取最近 N 期数据（默认 4 期）
            source: 数据源选择，可选值：
                   - 'all': 依次尝试所有数据源（默认）
                   - 'ths': 同花顺数据源
                   - 'em': 东方财富数据源  
                   - 'sina': 新浪数据源
        
        Returns:
            包含现金流量表数据的字典
        """
        clean_symbol = re.sub(r"\D", "", symbol)
        
        if not clean_symbol or len(clean_symbol) != 6:
            return {"error": f"无效的股票代码: {symbol}"}
        
        result = {
            "symbol": clean_symbol,
            "report_type": report_type,
            "periods": periods,
            "source": source,
            "data": None,
            "actual_source": None,
            "errors": []
        }
        
        # 定义数据源尝试顺序
        sources_order = []
        if source == "all":
            sources_order = ["ths", "em", "sina"]
        else:
            sources_order = [source]
        
        # 依次尝试各个数据源
        for source_name in sources_order:
            try:
                df = self._get_cash_flow_sheet_from_source(clean_symbol, report_type, periods, source_name)
                if df is not None and not df.empty:
                    result["data"] = df.to_dict('records')
                    result["actual_source"] = source_name
                    break
                else:
                    result["errors"].append(f"{source_name} 数据源现金流量表为空")
            except Exception as e:
                result["errors"].append(f"{source_name} 数据源现金流量表获取失败: {str(e)}")
        
        if result["data"] is None:
            result["errors"].append("所有数据源均无法获取现金流量表数据")
        
        return result
    
    def get_financial_statements(
        self,
        symbol: str,
        report_type: str = "annual",
        periods: int = 4
    ) -> dict:
        """
        获取三大财务报表（保持向后兼容的包装函数）
        
        Args:
            symbol: 股票代码
            report_type: 'annual' 或 'quarter'
            periods: 获取最近 N 期数据（默认 4 期）
        
        Returns:
            包含利润表、资产负债表、现金流量表的字典
        """
        result = {
            "symbol": re.sub(r"\D", "", symbol),
            "report_type": report_type,
            "income": None,
            "balance": None,
            "cashflow": None,
            "errors": []
        }
        
        # 获取利润表
        income_result = self.get_profit_statement(symbol, report_type, periods, "all")
        if income_result.get("data"):
            result["income"] = income_result["data"]
        else:
            result["errors"].extend(income_result.get("errors", []))
        
        # 获取资产负债表
        balance_result = self.get_balance_sheet(symbol, report_type, periods, "all")
        if balance_result.get("data"):
            result["balance"] = balance_result["data"]
        else:
            result["errors"].extend(balance_result.get("errors", []))
        
        # 获取现金流量表
        cashflow_result = self.get_cash_flow_statement(symbol, report_type, periods, "all")
        if cashflow_result.get("data"):
            result["cashflow"] = cashflow_result["data"]
        else:
            result["errors"].extend(cashflow_result.get("errors", []))
        
        # 如果三大报表均为空，则视为失败
        if result["income"] is None and result["balance"] is None and result["cashflow"] is None:
            result["errors"].append("AkShare 三大报表全部为空，可能接口失效或需要替代方案")
        
        return result
    
    
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
        
        # 获取 PE/PB (使用实时行情接口 stock_zh_a_spot_em)
        try:
            # stock_zh_a_spot_em 返回所有股票的实时数据，包含市盈率和市净率
            spot_df = ak.stock_zh_a_spot_em()
            
            if spot_df is not None and not spot_df.empty:
                # 筛选目标股票
                target_row = spot_df[spot_df['代码'] == clean_symbol]
                
                if not target_row.empty:
                    result["pe_pb"] = target_row.to_dict('records')
                else:
                    result["errors"].append(f"未找到股票 {clean_symbol} 的实时估值数据")
            else:
                 result["errors"].append("实时行情数据为空")
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
        try:
            forecast_df = ak.stock_profit_forecast_em()
            if forecast_df is not None and not forecast_df.empty:
                # 筛选目标股票 (列名通常为 "代码")
                code_cols = [col for col in forecast_df.columns if '代码' in str(col) or 'code' in str(col).lower()]
                
                if code_cols:
                    code_col = code_cols[0]
                    # 确保代码列是字符串类型
                    forecast_df[code_col] = forecast_df[code_col].astype(str)
                    filtered_df = forecast_df[forecast_df[code_col] == clean_symbol]
                    
                    if not filtered_df.empty:
                        if limit > 0:
                            filtered_df = filtered_df.head(limit)
                        result["forecast"] = filtered_df.to_dict('records')
                    else:
                        # 只是未找到数据，不报错
                        pass
                else:
                    result["errors"].append("业绩预告数据中未找到代码列")
        except Exception as e:
            result["errors"].append(f"业绩预告获取失败: {str(e)}")
        
        # 获取业绩快报
        try:
            express_df = ak.stock_yjkb_em()
            if express_df is not None and not express_df.empty:
                # 筛选目标股票 (列名通常为 "股票代码")
                code_cols = [col for col in express_df.columns if '代码' in str(col) or 'code' in str(col).lower()]
                
                if code_cols:
                    code_col = code_cols[0]
                    # 确保代码列是字符串类型
                    express_df[code_col] = express_df[code_col].astype(str)
                    filtered_df = express_df[express_df[code_col] == clean_symbol]
                    
                    if not filtered_df.empty:
                        if limit > 0:
                            filtered_df = filtered_df.head(limit)
                        result["express"] = filtered_df.to_dict('records')
                    else:
                         # 只是未找到数据，不报错
                        pass
                else:
                    result["errors"].append("业绩快报数据中未找到代码列")
        except Exception as e:
            result["errors"].append(f"业绩快报获取失败: {str(e)}")
        
        return result
    
    # ==================== fundamentals ====================
    
    def _get_profit_sheet_from_source(
        self,
        symbol: str,
        report_type: str,
        periods: int,
        source: str
    ) -> pd.DataFrame:
        """从指定数据源获取利润表"""
        try:
            if source == "ths":
                # 同花顺数据源
                indicator = "按单季度" if report_type == "quarter" else "按年度"
                df = ak.stock_financial_benefit_ths(symbol=symbol, indicator=indicator)
                
            elif source == "em":
                # 东方财富数据源
                if report_type == "quarter":
                    df = ak.stock_profit_sheet_by_quarterly_em(symbol=symbol)
                else:
                    df = ak.stock_profit_sheet_by_yearly_em(symbol=symbol)
                    
            elif source == "sina":
                # 新浪数据源（需要先获取所有数据再筛选）
                df = ak.stock_financial_report_sina(symbol=symbol)
                if df is not None and not df.empty:
                    # 新浪接口返回所有报表数据，需要筛选利润表
                    # 具体实现可能需要根据实际返回的数据结构调整
                    pass
                    
            else:
                return pd.DataFrame()
            
            if df is not None and not df.empty and periods > 0:
                df = df.head(periods)
            
            return df
        except Exception:
            return pd.DataFrame()
    
    def _get_balance_sheet_from_source(
        self,
        symbol: str,
        report_type: str,
        periods: int,
        source: str
    ) -> pd.DataFrame:
        """从指定数据源获取资产负债表"""
        try:
            if source == "ths":
                # 同花顺数据源
                indicator = "按单季度" if report_type == "quarter" else "按年度"
                df = ak.stock_financial_debt_ths(symbol=symbol, indicator=indicator)
                
            elif source == "em":
                # 东方财富数据源
                if report_type == "quarter":
                    df = ak.stock_balance_sheet_by_quarterly_em(symbol=symbol)
                else:
                    df = ak.stock_balance_sheet_by_yearly_em(symbol=symbol)
                    
            elif source == "sina":
                # 新浪数据源
                df = ak.stock_financial_report_sina(symbol=symbol)
                if df is not None and not df.empty:
                    # 新浪接口返回所有报表数据，需要筛选资产负债表
                    pass
                    
            else:
                return pd.DataFrame()
            
            if df is not None and not df.empty and periods > 0:
                df = df.head(periods)
            
            return df
        except Exception:
            return pd.DataFrame()
    
    def _get_cash_flow_sheet_from_source(
        self,
        symbol: str,
        report_type: str,
        periods: int,
        source: str
    ) -> pd.DataFrame:
        """从指定数据源获取现金流量表"""
        try:
            if source == "ths":
                # 同花顺数据源
                indicator = "按单季度" if report_type == "quarter" else "按年度"
                df = ak.stock_financial_cash_ths(symbol=symbol, indicator=indicator)
                
            elif source == "em":
                # 东方财富数据源
                if report_type == "quarter":
                    df = ak.stock_cash_flow_sheet_by_quarterly_em(symbol=symbol)
                else:
                    df = ak.stock_cash_flow_sheet_by_yearly_em(symbol=symbol)
                    
            elif source == "sina":
                # 新浪数据源
                df = ak.stock_financial_report_sina(symbol=symbol)
                if df is not None and not df.empty:
                    # 新浪接口返回所有报表数据，需要筛选现金流量表
                    pass
                    
            else:
                return pd.DataFrame()
            
            if df is not None and not df.empty and periods > 0:
                df = df.head(periods)
            
            return df
        except Exception:
            return pd.DataFrame()
    
    def _get_profit_sheet(
        self,
        symbol: str,
        report_type: str,
        periods: int
    ) -> pd.DataFrame:
        """获取利润表（保持向后兼容的包装函数）"""
        return self._get_profit_sheet_from_source(symbol, report_type, periods, "ths")
    
    def _get_balance_sheet(
        self,
        symbol: str,
        report_type: str,
        periods: int
    ) -> pd.DataFrame:
        """获取资产负债表（保持向后兼容的包装函数）"""
        return self._get_balance_sheet_from_source(symbol, report_type, periods, "ths")
    
    def _get_cashflow_sheet(
        self,
        symbol: str,
        report_type: str,
        periods: int
    ) -> pd.DataFrame:
        """获取现金流量表（保持向后兼容的包装函数）"""
        return self._get_cash_flow_sheet_from_source(symbol, report_type, periods, "ths")
    
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