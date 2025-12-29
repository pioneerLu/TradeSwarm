"""
数据管理模块：提供基于 SQLite 与 ChromaDB 的持久化管理能力。
"""

import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional

import chromadb
from chromadb.api import ClientAPI
from chromadb.api.models import Collection




class DataManager:
    """
    数据管理器，负责初始化SQLite连接与ChromaDB持久化客户端。

    设计遵循研究型代码规范：显式传入所有配置参数，避免使用隐式默认值，
    并在初始化阶段完成路径校验、目录创建及核心依赖的实例化。

    属性:
        sqlite_connection: SQLite 数据库连接
        chroma_client: ChromaDB 客户端
        chroma_collection: ChromaDB 集合
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """
        初始化数据管理器，基于完整配置构建 SQLite 连接与 ChromaDB 集合。

        参数:
            config: 总体配置字典，需包含 storage 段及必要字段。

        关键实现细节:
            - 第一阶段：验证传入配置结构并提取存储段
            - 第二阶段：目录创建，确保 SQLite 与 Chroma 持久化路径可用
            - 第三阶段：初始化 SQLite，启用外键约束与 WAL 模式
            - 第四阶段：初始化 ChromaDB 客户端与目标集合
        """

        # 第一阶段：配置校验与提取
        if not isinstance(config, dict):
            raise ValueError("config 必须为字典类型")

        storage_config = config.get("storage")
        if not isinstance(storage_config, dict):
            raise ValueError("storage 配置缺失或格式错误")

        required_storage_fields = (
            "sqlite_path",
            "chroma_persist_directory",
            "chroma_collection",
        )
        missing_fields = [field for field in required_storage_fields if not storage_config.get(field)]
        if missing_fields:
            raise ValueError(f"storage 配置缺少必要字段: {', '.join(missing_fields)}")

        sqlite_file_path = Path(storage_config["sqlite_path"])
        chroma_dir_path = Path(storage_config["chroma_persist_directory"])
        chroma_collection = storage_config["chroma_collection"]

        # 第二阶段：目录创建
        sqlite_file_path.parent.mkdir(parents=True, exist_ok=True)
        chroma_dir_path.mkdir(parents=True, exist_ok=True)

        # 第三阶段：初始化 SQLite
        self.sqlite_connection: sqlite3.Connection = sqlite3.connect(
            sqlite_file_path.as_posix(),
            check_same_thread=False,
        )
        self.sqlite_connection.execute("PRAGMA foreign_keys = ON;")
        self.sqlite_connection.execute("PRAGMA journal_mode = WAL;")

        # 第四阶段：初始化 ChromaDB
        self.chroma_client: ClientAPI = chromadb.PersistentClient(
            path=chroma_dir_path.as_posix()
        )
        self.chroma_collection: Collection = self.chroma_client.get_or_create_collection(
            name=chroma_collection,
            metadata={"source": "tradeswarm", "purpose": "vector_store"},
        )

    # ==================== 财务数据管理方法 ====================

    def create_tables(self) -> None:
        """
        创建所有财务数据表
        
        关键实现细节:
            - 第一阶段：导入表结构定义
            - 第二阶段：依次执行所有表的创建语句
        """
        # 第一阶段：导入表结构定义
        from .schemas import TABLE_SCHEMAS
        
        # 第二阶段：执行表创建
        cursor = self.sqlite_connection.cursor()
        for table_name, table_sql in TABLE_SCHEMAS.items():
            try:
                cursor.execute(table_sql)
                print(f"表 {table_name} 创建成功")
            except sqlite3.Error as e:
                print(f"表 {table_name} 创建失败: {e}")
        
        self.sqlite_connection.commit()
        cursor.close()

    def insert_financial_data(self, akshare_result: Dict[str, Any], table_name: str) -> bool:
        """
        插入数据到指定表（支持财务数据和宏观市场数据）
        
        Args:
            akshare_result: AkShare返回的结果数据
            table_name: 目标表名，可选值：
                        财务数据：
                        - "profit_statements": 利润表
                        - "balance_sheets": 资产负债表
                        - "cash_flow_statements": 现金流量表
                        宏观数据：
                        - "macro_news": 宏观新闻
                        - "northbound_money_flow": 北向资金流向
                        - "global_indices": 核心指数表现
                        - "currency_exchange_rates": 汇率信息
        
        Returns:
            插入是否成功
        
        关键实现细节:
            - 第一阶段：验证表名和结果数据
            - 第二阶段：区分财务数据和宏观数据处理逻辑
            - 第三阶段：使用对应的数据准备函数转换数据
            - 第四阶段：插入数据到数据库并处理异常
        """
        # 第一阶段：验证表名和结果数据
        supported_tables = [
            "profit_statements", "balance_sheets", "cash_flow_statements",
            "macro_news", "northbound_money_flow", "global_indices", "currency_exchange_rates"
        ]
        
        if table_name not in supported_tables:
            print(f"错误：不支持的表名 {table_name}")
            return False
        
        if not isinstance(akshare_result, dict):
            print(f"错误：插入的数据无效")
            return False
        
        data = akshare_result.get('data')
        if data is None:
            print(f"错误：插入的数据为空")
            return False
        
        # 检查DataFrame是否为空
        import pandas as pd
        if isinstance(data, pd.DataFrame) and data.empty:
            print(f"错误：DataFrame数据为空")
            return False
        
        try:
            # 第二阶段：区分处理逻辑
            # 财务数据需要确保股票存在，宏观数据不需要
            if table_name in ["profit_statements", "balance_sheets", "cash_flow_statements"]:
                symbol = akshare_result.get('symbol')
                if not symbol:
                    print(f"错误：股票代码缺失")
                    return False
                self._ensure_stock_exists(symbol)
            
            # 第三阶段：数据转换
            from .data_converter import DATA_PREPARERS
            
            data_preparer = DATA_PREPARERS.get(table_name)
            if not data_preparer:
                print(f"错误：找不到表 {table_name} 的数据准备函数")
                return False
            
            db_data = data_preparer(akshare_result)
            if not db_data:
                print(f"错误：数据转换失败")
                return False
            
            # 第四阶段：根据数据类型选择插入方法
            # 宏观数据中的新闻和指数返回列表（多条记录），其他返回单条记录
            multi_record_tables = ["macro_news", "global_indices"]
            
            if table_name in multi_record_tables:
                return self._insert_multiple_records(table_name, db_data)
            else:
                return self._insert_record(table_name, db_data)
            
        except Exception as e:
            print(f"插入数据时发生异常: {e}")
            return False

    def _ensure_stock_exists(self, symbol: str) -> bool:
        """
        确保股票在stocks表中存在，如不存在则插入
        
        Args:
            symbol: 股票代码
        
        Returns:
            是否确保成功
        """
        try:
            cursor = self.sqlite_connection.cursor()
            
            # 检查股票是否已存在
            cursor.execute("SELECT symbol FROM stocks WHERE symbol = ?", (symbol,))
            if cursor.fetchone():
                cursor.close()
                return True
            
            # 插入新的股票记录（基本信息暂时为空）
            cursor.execute(
                "INSERT INTO stocks (symbol, name, exchange, industry) VALUES (?, ?, ?, ?)",
                (symbol, None, None, None)
            )
            self.sqlite_connection.commit()
            cursor.close()
            
            print(f"已插入股票基础信息: {symbol}")
            return True
            
        except Exception as e:
            print(f"确保股票存在时出错: {e}")
            return False

    def _insert_record(self, table_name: str, data: Dict[str, Any]) -> bool:
        """
        内部方法：插入单条记录到数据库
        
        Args:
            table_name: 表名
            data: 要插入的数据字典
        
        Returns:
            插入是否成功
        """
        try:
            cursor = self.sqlite_connection.cursor()
            
            # 获取所有非None的字段
            valid_fields = {k: v for k, v in data.items() if v is not None}
            
            if not valid_fields:
                print(f"错误：没有有效数据可插入")
                cursor.close()
                return False
            
            # 构建INSERT语句
            columns = list(valid_fields.keys())
            placeholders = ['?' for _ in columns]
            values = list(valid_fields.values())
            
            sql = f"INSERT OR REPLACE INTO {table_name} ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
            
            cursor.execute(sql, values)
            self.sqlite_connection.commit()
            
            # 根据表类型显示不同的成功信息
            if table_name in ["profit_statements", "balance_sheets", "cash_flow_statements"]:
                print(f"成功插入数据到 {table_name}: {data.get('symbol', 'N/A')} - {data.get('report_period', 'N/A')}")
            else:
                print(f"成功插入数据到 {table_name}")
            
            cursor.close()
            return True
            
        except sqlite3.Error as e:
            print(f"数据库错误: {e}")
            return False
        except Exception as e:
            print(f"插入记录时发生异常: {e}")
            return False

    def _insert_multiple_records(self, table_name: str, data_list: list) -> bool:
        """
        内部方法：插入多条记录到数据库
        
        Args:
            table_name: 表名
            data_list: 要插入的数据字典列表
        
        Returns:
            插入是否成功
        """
        if not data_list or not isinstance(data_list, list):
            print(f"错误：数据列表无效或为空")
            return False
        
        try:
            cursor = self.sqlite_connection.cursor()
            success_count = 0
            error_count = 0
            
            for data in data_list:
                if not isinstance(data, dict):
                    error_count += 1
                    continue
                
                # 获取所有非None的字段
                valid_fields = {k: v for k, v in data.items() if v is not None}
                
                if not valid_fields:
                    error_count += 1
                    continue
                
                # 构建INSERT语句
                columns = list(valid_fields.keys())
                placeholders = ['?' for _ in columns]
                values = list(valid_fields.values())
                
                sql = f"INSERT OR REPLACE INTO {table_name} ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
                
                try:
                    cursor.execute(sql, values)
                    success_count += 1
                except sqlite3.Error as e:
                    print(f"插入单条记录失败: {e}")
                    error_count += 1
            
            # 提交所有成功的插入
            if success_count > 0:
                self.sqlite_connection.commit()
            
            cursor.close()
            
            print(f"成功插入 {success_count} 条记录到 {table_name}，失败 {error_count} 条")
            return success_count > 0
            
        except Exception as e:
            print(f"批量插入记录时发生异常: {e}")
            return False

    def query_financial_data(
        self,
        symbol: Optional[str] = None,
        table_name: Optional[str] = None,
        report_period: Optional[str] = None,
        limit: Optional[int] = None
    ) -> list:
        """
        查询数据（支持财务数据和宏观市场数据）
        
        Args:
            symbol: 股票代码，为空则查询所有（仅对财务数据有效）
            table_name: 表名，为空则查询所有表
            report_period: 报告期，为空则查询所有期数（仅对财务数据有效）
            limit: 限制返回记录数量，为空则返回所有记录
        
        Returns:
            查询结果列表
        """
        try:
            cursor = self.sqlite_connection.cursor()
            
            # 确定查询的表
            if table_name:
                tables = [table_name]
            else:
                tables = [
                    "profit_statements", "balance_sheets", "cash_flow_statements",
                    "macro_news", "northbound_money_flow", "global_indices", "currency_exchange_rates"
                ]
            
            results = []
            
            for table in tables:
                # 构建WHERE条件
                conditions = []
                params = []
                
                # 财务数据特有的查询条件
                if table in ["profit_statements", "balance_sheets", "cash_flow_statements"]:
                    if symbol:
                        conditions.append("symbol = ?")
                        params.append(symbol)
                    
                    if report_period:
                        conditions.append("report_period = ?")
                        params.append(report_period)
                
                where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
                
                # 构建排序和限制条件
                order_by = ""
                if table in ["northbound_money_flow", "currency_exchange_rates"]:
                    # 单条记录类型的表按创建时间倒序
                    order_by = " ORDER BY created_at DESC"
                elif table in ["macro_news", "global_indices"]:
                    # 多条记录类型的表也按创建时间倒序
                    order_by = " ORDER BY created_at DESC"
                else:
                    # 财务数据表按报告期倒序
                    order_by = " ORDER BY report_period DESC, created_at DESC"
                
                limit_clause = f" LIMIT {limit}" if limit else ""
                
                # 执行查询
                sql = f"SELECT *, '{table}' as table_name FROM {table}{where_clause}{order_by}{limit_clause}"
                cursor.execute(sql, params)
                
                # 获取列名
                columns = [description[0] for description in cursor.description]
                
                # 转换为字典列表
                for row in cursor.fetchall():
                    result_dict = dict(zip(columns, row))
                    results.append(result_dict)
            
            cursor.close()
            return results
            
        except Exception as e:
            print(f"查询数据时发生异常: {e}")
            return []

        
