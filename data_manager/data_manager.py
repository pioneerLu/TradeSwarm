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
        插入财务数据到指定表
        
        Args:
            akshare_result: AkShare返回的财务报表结果
            table_name: 目标表名，可选值：
                        - "profit_statements": 利润表
                        - "balance_sheets": 资产负债表
                        - "cash_flow_statements": 现金流量表
        
        Returns:
            插入是否成功
        
        关键实现细节:
            - 第一阶段：验证表名和结果数据
            - 第二阶段：确保股票信息存在（满足外键约束）
            - 第三阶段：使用对应的数据准备函数转换数据
            - 第四阶段：插入数据到数据库并处理异常
        """
        # 第一阶段：验证表名和结果数据
        if table_name not in ["profit_statements", "balance_sheets", "cash_flow_statements"]:
            print(f"错误：不支持的表名 {table_name}")
            return False
        
        if not isinstance(akshare_result, dict) or not akshare_result.get('data'):
            print(f"错误：插入的数据无效或为空")
            return False
        
        try:
            # 第二阶段：确保股票信息存在
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
            
            # 第四阶段：插入数据库
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
            
            print(f"成功插入数据到 {table_name}: {data.get('symbol', 'N/A')} - {data.get('report_period', 'N/A')}")
            cursor.close()
            return True
            
        except sqlite3.Error as e:
            print(f"数据库错误: {e}")
            return False
        except Exception as e:
            print(f"插入记录时发生异常: {e}")
            return False

    def query_financial_data(
        self,
        symbol: Optional[str] = None,
        table_name: Optional[str] = None,
        report_period: Optional[str] = None
    ) -> list:
        """
        查询财务数据
        
        Args:
            symbol: 股票代码，为空则查询所有
            table_name: 表名，为空则查询所有财务表
            report_period: 报告期，为空则查询所有期数
        
        Returns:
            查询结果列表
        """
        try:
            cursor = self.sqlite_connection.cursor()
            
            # 确定查询的表
            if table_name:
                tables = [table_name]
            else:
                tables = ["profit_statements", "balance_sheets", "cash_flow_statements"]
            
            results = []
            
            for table in tables:
                # 构建WHERE条件
                conditions = []
                params = []
                
                if symbol:
                    conditions.append("symbol = ?")
                    params.append(symbol)
                
                if report_period:
                    conditions.append("report_period = ?")
                    params.append(report_period)
                
                where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
                
                # 执行查询
                sql = f"SELECT *, '{table}' as table_name FROM {table}{where_clause} ORDER BY report_period DESC"
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

        
