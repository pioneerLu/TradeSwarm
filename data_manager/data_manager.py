"""
数据管理模块：提供基于 SQLite 与 ChromaDB 的持久化管理能力。
"""

import sqlite3
from pathlib import Path
from typing import Any, Dict

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

        
